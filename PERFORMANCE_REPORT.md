# Sovereign Workbench — Performance & Test Report

**Test date:** 2026-09-05 · **All numbers measured live on the running system**
**Reproducible with:** `python3 scripts/benchmark.py` (components) and `python3 scripts/benchmark_e2e.py` (demo flows)

---

## 1. Test environment

| Item | Value |
|---|---|
| Hardware | Apple M4 (arm64), 10 cores, 16 GB unified memory |
| OS / Python | macOS 26.6.2 · Python 3.13.11 |
| Inference engine | Ollama 0.20.4, loopback-only (`127.0.0.1:11434`) |
| Models installed | qwen2.5:1.5b · qwen2.5-coder:1.5b · moondream · nomic-embed-text (≈4 GB total) |
| Knowledge base | 732 chunks × 768-dim vectors from 6 source documents |
| Air-gap | ENFORCED at socket level during all tests |

> These are 1.5B-class models per the PS mid-range-hardware allowance. Every number below scales up with a larger model; the architecture is unchanged.

---

## 2. Model throughput (the headline numbers)

| Model | Generation speed | Prompt processing | Cold-load time | Typical response |
|---|---|---|---|---|
| qwen2.5:1.5b (reasoning) | **66.8 tok/s** | 2 933 tok/s | 0.09 s | ~78 tok in 1.3 s |
| qwen2.5-coder:1.5b (coding) | **66.5 tok/s** | 2 933 tok/s | 1.29 s | ~75 tok in 1.3 s |
| moondream (vision) | **57.4 tok/s** | 19 946 tok/s (image tokens) | 2.45 s | 13 tok in 3.2 s |

**What this means in practice:** a one-paragraph agent answer takes ~1–2 s of model time; a drafted one-page approval note (~900 tokens) takes ~15–25 s. Reading a page image (P&ID or scanned page) costs ~2–3 s. All well inside a live-demo comfort zone.

---

## 3. KV / prompt cache behaviour

Ollama keeps the KV cache of recent requests (our client sets `keep_alive: 10m`). Repeating an identical 1 012-token prompt:

| Call | Prompt processing time | Speed-up |
|---|---|---|
| 1st (cold) | 3.512 s | — |
| 2nd (cache hit) | **0.017 s** | **≈ 207× faster** |

- The reported *token count* stays the same (Ollama still counts the prompt), but the *compute* collapses — this is the KV cache serving prefill from memory.
- **Where it matters in this project:** the agent loop re-sends the system prompt + task + observations every turn; in a multi-step task, every turn after the first gets cheaper prefill. Same for the four one-click demos run back-to-back.
- Tuning knob: `keep_alive` in `backend/app/models/provider.py` (currently `"30m"` in the app path). For a shared multi-user deployment, a longer keep_alive trades RAM (KV cache ≈ context size) for speed.

---

## 4. Embeddings & RAG retrieval

| Metric | Value |
|---|---|
| Single embedding latency (nomic-embed-text) | **avg 72.9 ms** (min 15.9, max 458.9 — first-call load) |
| Vector store | 732 chunks × 768 dims, persisted in `workspace/vector_store.json` (~10 MB) |
| Semantic search (full 732-chunk scan) | **avg 19.7 ms · p50 18.2 ms · p95 23.0 ms** |
| Retrieval correctness (control query "maximum allowed storage tank temperature") | ✅ top hit = OPS-MAN-07 tank manual |
| Re-index time (full corpus, 732 chunks) | ~32 s (≈ 45 ms/chunk incl. embed + write) |
| Fallback embedder (zero-model mode) | hashed char-trigram TF-IDF, pure numpy/hashlib, fully offline |

Search is exhaustive cosine similarity in one numpy multiply — no DB service. p95 of 23 ms means retrieval is effectively free next to any LLM call; it only becomes a design question past ~10⁵ chunks (swap point for FAISS/pgvector, isolated in `rag/store.py`).

---

## 5. Python sandbox (generated-code execution)

| Metric | Value |
|---|---|
| Trivial run end-to-end (spawn + interpreter boot + network-block prelude + print) | **21.8 ms avg** (min 18.3) |
| Real computation (sieve of primes < 20 000, with step-printed outputs) | 27.3 ms |

The full security envelope — subprocess isolation (`python -I`), socket blocking inside the generated code, scrubbed environment, 30 s hard timeout — costs ~20 ms. Sandbox overhead is negligible; the 30 s timeout is the only realistic ceiling, and it exists to kill runaway loops.

## 6. OCR (on-device Tesseract 5.5)

| Page | Time | Characters extracted | Throughput |
|---|---|---|---|
| inspection_report_p1.png | 673 ms | 1 636 | **2 430 chars/s** |
| inspection_report_p2.png | 387 ms | 811 | **2 098 chars/s** |

~0.4–0.7 s per scanned A4 page. A 20-page scanned report ≈ 8–14 s of OCR. Fallback path (moondream VLM OCR) is slower (~2–3 s/page) but requires nothing but the local models.

## 7. Deliverable generation

| Artifact | Time |
|---|---|
| Word document (multi-section approval note) | **65.8 ms** |
| Excel workbook (500 rows) | **54.5 ms** |
| PowerPoint (8 slides) | **48.5 ms** |

Document generation is two orders of magnitude cheaper than the reasoning that produces the content — the "real deliverables" requirement costs nothing at runtime.

## 8. Egress guard (sovereignty enforcement) overhead

| Path | Cost per connect |
|---|---|
| Loopback connect (allowed — Ollama calls) | **49 µs** |
| External connect (blocked + logged) | 416 µs (dominated by DNS resolution attempt before the verdict) |

The guard's overhead per LLM call is ~0.005 % of the call itself. During all benchmark runs the counters read: external attempts **blocked: 2, allowed loopback: 5+, cloud API calls: 0**.

---

## 9. End-to-end demo flows (measured via the real WebSocket protocol)

| Flow | Total wall time | Deliverables | Notes |
|---|---|---|---|
| Knowledge QA (tank temperature) | **16.7 s** | answer + verbatim sources | fastest; 3 KB searches |
| Multimodal (P&ID analysis) | **31.3 s** | findings .docx | vision + OCR + KB + doc |
| Coding (boiler efficiency, sandbox-verified) | **40.2 s** | verified .py | sandbox run itself: 0.05 s |
| Document (scanned report → approval note) | **57.5 s** | approval_note .docx | 2-page OCR + SOP check + drafted note |
| Office (Excel + PowerPoint) | **83.6 s** | .xlsx + .pptx | most LLM turns (plan + 2 tools + long answer) |

### Where the time actually goes (document flow, 57.5 s)

| Component | Time | Share |
|---|---|---|
| LLM inference (planning, thinking, drafting, final answer) | ~53 s | **~92 %** |
| OCR (2 pages) | 1.1 s | 2 % |
| RAG searches | 0.3 s | 0.5 % |
| PDF extraction | 0.15 s | 0.3 % |
| docx creation | <0.1 s | 0.2 % |
| Everything else (routing, event streaming) | ~3 s | 5 % |

**The system's own tooling is effectively free — 90 %+ of wall time is model inference.** That is exactly the right profile: it means speed improvements come from model choice/quantisation, not from re-engineering the plumbing.

---

## 10. Capacity planning (order-of-magnitude, for the deck's Q&A)

- One 1.5B stream sustains ~67 tok/s on a 10-core laptop-class chip. A typical task = 8–12 LLM turns ≈ 17–84 s wall.
- On the "single mid-range GPU server" the PS specifies (e.g., RTX 4090/5090-class, or A100): 1.5B models at bf16/fp8 sustain several hundred tok/s per stream and Ollama batches concurrent requests, so **5–15 simultaneous users** per box at this model size is a defensible engineering estimate (state it as an estimate; a load test on the target hardware replaces it with a fact).
- RAM per user is dominated by the KV cache of shared model instances (small at 1.5B; the 4 GB model store fits in a 16 GB machine 4× over).

## 11. Tuning knobs (all in code, no re-architecture)

| Knob | Where | Effect |
|---|---|---|
| `keep_alive` | `models/provider.py` | Longer = more KV-cache hits across turns/users, costs RAM |
| `num_ctx` (context window) | `options` in `provider.generate` | Longer document context per call; more RAM per stream |
| `num_predict` caps | orchestrator (`temperature`, `num_predict`) | Directly bounds each LLM phase's wall time |
| Quantisation | Ollama tag choice (q4 → q8) | Bigger/slower-but-sharper models on same GPU |
| `AGENT_MAX_STEPS` / sandbox timeout | `config.py` | Safety ceilings on worst-case task duration |

## 12. Correctness re-verified during this test run

- All 5 demo flows: **completed = True**, 5 deliverable files produced, zero errors.
- RAG control query retrieved the correct source (OPS-MAN-07) as top hit.
- Air-gap: every benchmark's external-connect probe was **blocked**; counters stayed clean.
- Sandbox: exit code 0 on all runs, network-block prelude active.

## 13. Weak spots the numbers reveal (honest list)

1. **Final-answer generation is the single largest phase** (5–29 s). A larger model would be *slower* per token; the fix is streaming the answer to the UI (currently it arrives as one event) or trimming `num_predict`.
2. **Embedding max latency 459 ms** — first-call model load; a `keep_alive` on the embedding model (already set to 30 m in-app) hides it after the first query.
3. **Egress-blocked path costs 416 µs** due to DNS resolution inside the verdict; a hosts-file-free fast path could skip DNS for obvious IPs — cosmetic, only matters at absurd QPS.
4. **Ollama counts cached prefill tokens as processed** — when quoting tok/s externally, quote *generation* tok/s (66), not prompt tok/s.

---

*Benchmarks: `scripts/benchmark.py` (components, ~2 min) and `scripts/benchmark_e2e.py` (flows, ~4 min). Raw JSON: `/tmp/wb_bench.json`, `/tmp/wb_e2e.json`.*
