# ARCHITECTURE — Sovereign Workbench (current implementation)

**Written against code, not intention.** Repo state: `main @ a71b5b1` · 2026-11-06.
Every component below carries an honest status:

| Label | Meaning |
|---|---|
| ✅ | Exists, works, verified |
| 🟡 | Partially implemented (described precisely what's missing) |
| ⛔ | Missing |
| 🔜 | Proposed — mapped to a milestone in `PRODUCTION_PLAN.md` |

Scope rule (M0): this document describes **what is**, not what we plan. Plans live in `PRODUCTION_PLAN.md`; the delta is always cross-referenced.

---

## 1. System overview (as-built)

```
Browser UI (vanilla JS, served by FastAPI at 127.0.0.1:8000)
   │  WebSocket /ws/task          HTTP /api/*
   ▼
FastAPI backend (single uvicorn process)          macOS only, optional:
   │  egress guard installed at import time        scripts/run_airgapped.sh
   ▼                                               wraps the WHOLE tree in a
Orchestrator (agentic loop, in-process)            Seatbelt kernel policy
   ├── Model Router ── classify task → capability → model
   ├── ModelGateway ──→ Ollama HTTP API (127.0.0.1:11434)
   ├── Tools ── filesystem · python sandbox · docx/xlsx/pptx · PDF/OCR/vision · KB search
   └── RAG store ── JSON + numpy vectors on disk (workspace/vector_store.json)
```

Everything runs in **one process** plus spawned sandbox children. There is no database, no queue, no second service.

## 2. Backend modules

### 2.1 `app/main.py` — API surface (291 lines) ✅

| Endpoint | Method | What it does | Status |
|---|---|---|---|
| `/api/health` | GET | status + engine + egress snapshot + KB stats | ✅ |
| `/api/models` | GET | gateway status: installed models, per-capability resolution | ✅ |
| `/api/network` | GET | egress counters + last 50 events (in-memory) | ✅ |
| `/api/network/selftest` | POST | attempts `httpx` GET to example.com; guard must block | ✅ |
| `/api/network/sandbox_escape_test` | POST | 4 adversarial probes + positive control through the **real** `run_python` tool; verdicts decided by exfil markers, not exit codes | ✅ |
| `/api/upload` | POST | saves to `workspace/uploads/` via `_safe_filename` (basename flatten, dotfiles rejected) | ✅ |
| `/api/files` | GET | lists uploads/outputs/kb | ✅ |
| `/api/download?path=` | GET | path resolved; refused unless inside workspace root (`400 path escapes workspace`) | ✅ |
| `/api/kb/upload`, `/api/kb/reindex` | POST | KB ingestion + vector rebuild | ✅ |
| `/ws/task` | WS | accepts `{task, attachments}`; orchestrator runs **in a thread-pool executor**, events streamed via `asyncio.Queue` bridge (`call_soon_threadsafe`) | ✅ |
| `/` (static mount) | GET | `index.html`, `app.js`, `style.css` | ✅ |

Key implementation facts:
- `egress.install_egress_guard()` runs at **import time, before any other app import** (`main.py:21`) so no module can connect first.
- One `Orchestrator` per WebSocket task; `task_manager.register(ctx)` is called after completion.
- 🟡 **Task history is write-only**: `TaskManager` stores finished `TaskContext` objects in an in-memory dict, but **no endpoint reads it** (no `GET /api/tasks`). Registered at `orchestrator.py:673`, consumed nowhere. 🔜 `M4` resurrects it.
- ⛔ No authentication, no sessions, no rate limiting on any route. 🔜 `M1`.
- ⛔ No persistence layer. All state (egress events, task contexts, RAG store) lives in process memory or JSON files; restart loses history. 🔜 `M4`.

### 2.2 `app/config.py` — configuration (54 lines) ✅ with 🟡

- Paths: everything under `PROJECT_ROOT/workspace/` — `kb/`, `uploads/`, `outputs/`, `sandbox/`, `vector_store.json`. Directories auto-created on import.
- `OLLAMA_BASE_URL = http://127.0.0.1:11434` — literal, loopback-only.
- `NUM_CTX = 8192` — set explicitly on every `generate()` call (fixes Ollama's silent ~2–4k default truncation).
- `MODEL_REGISTRY`: capability → model + fallbacks.
  - reasoning: `qwen2.5:1.5b` (fb `qwen2.5:0.5b`) · coding: `qwen2.5-coder:1.5b` (fb `qwen2.5:1.5b`) · vision: `moondream` · embedding: `nomic-embed-text`.
- `STRICT_AIRGAP = True`, `ALLOWED_HOSTS` = loopback set, `AGENT_MAX_STEPS = 12`, `SANDBOX_TIMEOUT_S = 30`.
- 🟡 Constants-only module: **no environment-variable overrides** (except `SOVEREIGN_AIRGAP_KERNEL` read in `main.py` as a label), no secrets handling (nothing to hide yet — zero secrets exist in the codebase), no per-deployment config. 🔜 `M3` adds config via env/file for containerized deploys.

### 2.3 `app/security/egress.py` — app-layer air-gap (112 lines) ✅ with documented limits

- Monkey-patches `socket.socket.connect`. Tuple destinations inspected; `AF_UNIX` passed through untouched.
- `is_local()`: **IP-literal fast path** via `ipaddress` (no DNS on the verdict path — resolving a hostname would itself leak a query). Loopback/link-local/allowlist → allowed.
- Hostnames fall through to `socket.getaddrinfo` → checks resolved addresses (⛔ this is a **documented DNS leak window** for hostname traffic; the app itself only ever uses `127.0.0.1` literals, so the common path never resolves).
- Every attempt recorded: `deque(maxlen=500)` + counters, guarded by a lock. ⛔ **In-memory only** — not persisted, not exportable. 🔜 `M7` audit log.
- Raises `ConnectionBlocked(ConnectionError)` on non-loopback under `STRICT_AIRGAP`.
- **Honest limits (by design, proven by the escape battery):** a Python monkey-patch does not cover raw `_socket`, `ctypes` libc calls, or child processes. Those vectors are only stopped by the kernel layer (`run_airgapped.sh`). This is exactly what `/api/network/sandbox_escape_test` demonstrates.

### 2.4 `app/models/provider.py` — the only module that talks to an LLM (174 lines) ✅

- `OllamaProvider`: `httpx.Client` (base 127.0.0.1:11434, timeout 300 s, `keep_alive="30m"`, `num_ctx=NUM_CTX`), `generate()` (non-streaming) + `embed()`.
- `ModelGateway`: `refresh()` hits `/api/tags`; `resolve(capability)` walks primary → fallbacks, tolerant of `:latest` tagging; `generate_for()`, `embed_text()` (returns `None` on failure → caller falls back).
- `extract_json()`: brace-depth scanner, tolerant of ```json fences.
- 🔜 `M3/M7`: this module is the single point to add a vLLM/OpenAI-compatible endpoint — the interface (`generate`, `embed`) is already provider-shaped.

### 2.5 `app/models/router.py` — task classification (113 lines) ✅

- Two-stage: deterministic keyword/extension scoring (`.py`→coding +3, images→vision +3, `.pdf`→document_analysis +3, regex keyword lists) then **local-LLM override only when heuristic confidence < 0.5** (strong attachment evidence wins over the model).
- Output `RoutingDecision(task_type, confidence, evidence[], models{})` — evidence list is rendered in the UI routing panel (auditable).
- Confidence floored at 0.5; no signals → `general`.

### 2.6 `app/agent/orchestrator.py` — agentic loop (673 lines) ✅

Flow: `route → plan → loop (≤12 steps) → final answer`.

- **Plan**: LLM-generated (max 6 steps, JSON) with deterministic per-task-type fallback plans when offline/malformed.
- **Decision loop**: the reasoning model returns `{tool, args}` or `{final}` as JSON. `_normalize_decision` guards: unknown tools are rejected; **premature `finalize` is vetoed** by the state controller if useful work remains.
- **State controller** (`_next_strategic_action`): deterministic per-task-type step ladders computed from *what actually happened* (not the plan). E.g. document_analysis: `extract_pdf` → OCR up to 2 scanned pages → KB search → explicitly-requested deliverable (regex-detected "excel/pptx/word") → default `create_docx` approval note.
- **Self-healing code loop**: `run_python` gets up to 3 attempts; failures feed stderr back to the coding model for repair; verified code is written to `outputs/verified_code_<id>.py`.
- **Small-model armor** (what makes 1.5B viable): `_conform_args` maps invented arg names to schema aliases, auto-fills `path`/`query`, defaults deliverable filenames/content from grounded observations; duplicate `(tool, args)` signatures are deduped and re-routed to the state controller.
- **Grounding**: final answer is generated against a **verbatim citation block** (best KB hits + OCR text, deduped, ≤6 sources) with an explicit do-not-invent prompt; deterministic action-log summary as fallback.
- 🟡 Task history: in-memory only (see 2.1). 🔜 `M4` persists `TaskContext` to SQLite; 🔜 `M6` per-user history.

### 2.7 `app/tools/local_tools.py` — tool registry (383 lines) ✅

Decorator-registered `Tool(name, description, json-schema, fn)`; schemas are what the system prompt advertises to the model.

| Tool | Implementation | Status |
|---|---|---|
| `list_files`, `read_file` (20k-char cap), `write_file` | via `_safe_path()` — resolves under workspace root, refuses escapes | ✅ |
| `run_python` | per-run dir `sandbox/run_<id>/`; prelude blocks `socket.socket` (subclass raising `ConnectionError`), `chdir`+`HOME` confined to run dir; `subprocess.run([sys.executable, "-I", script], cwd=workdir, minimal env, 30 s timeout)` | ✅ with ⛔ gaps: **no CPU/memory rlimits, no OS jail; child processes not blocked at Python level** (kernel layer covers when active). 🔜 `M7` containerized sandbox |
| `create_docx` | markdown-ish → headings/bullets/numbered/bold runs | ✅ |
| `create_xlsx`, `create_pptx` | JSON `Sheets`/`Slides` | ✅ |
| `extract_pdf` | pypdf text layer + pypdfium2 page renders (scale 2.0); scanned detection = <20 chars/page | ✅ |
| `ocr_image` | pytesseract → fallback to vision model (base64) — degradation is explicit in result `engine` field | ✅ |
| `analyze_image` | vision model, base64 image + question | ✅ |
| `search_knowledge_base` | → RAG store, `top_k=4` | ✅ |

### 2.8 `app/rag/store.py` — RAG (183 lines) ✅ with known scale limits

- Ingestion: walks `workspace/kb/` — `.txt/.md/.pdf/.docx` only. ⛔ No `.xlsx/.pptx` ingestion, **no OCR of scanned PDFs at ingestion time** (scanned KB docs silently index as near-empty), no layout awareness. 🔜 `M5` Docling.
- Chunking: 900 chars / 120 overlap, sentence-boundary breaks.
- Embedding: local `nomic-embed-text` via gateway; **fallback** `_hash_embed` = hashed char-trigram TF-IDF (dim 512) — fully offline.
- Storage: single `vector_store.json` (chunks + full float vectors inline). ✅ at 732 chunks; ⛔ rewrites whole file per reindex, loads everything into RAM — fine to ~10⁴ chunks, then must move. 🔜 `M6` pgvector.
- Search: numpy cosine, top_k, min-score 0.01, thread-locked.
- ⛔ Single namespace: no per-user/per-department scopes, no permissions on retrieval. 🔜 `M7` permission-aware RAG.

### 2.9 `app/static/` — frontend (index 90 / app.js 287 / style.css) ✅

- Three panels: Task Console (5 one-click demos + air-gap self-test + uploads + KB management + deliverables), Agent Activity timeline (WS events), Model Router + **Network Sovereignty Monitor** (live egress counters/events, 4 s polling) + Local Engine.
- Vanilla JS, no framework, no build step — deliberate (air-gap-friendly, zero supply chain).
- ✅ Air-gap pill is **derived, never hardcoded** (closed by F.1): `/api/network` exposes `kernel_policy` (`SOVEREIGN_AIRGAP_KERNEL`) + `last_escape_test` (latest battery verdict, recorded by the escape-test endpoint); the pill renders `KERNEL: SEATBELT` / `KERNEL: NETNS` / `APP GUARD ONLY` / `AIR-GAP: UNVERIFIED` (a failed battery outranks any label). A unit test guards against the hardcoded claim regressing.

## 3. Air-gap enforcement (two layers)

1. **App layer (always on)** — egress monkey-patch (§2.3): blocks + logs loopback-only policy in-process.
2. **Kernel layer (macOS, opt-in)** — `scripts/run_airgapped.sh`: `sandbox-exec -f scripts/airgap/sovereign-airgap.sb` wraps the **entire process tree** (uvicorn, sandbox children, tesseract, anything generated code spawns). Profile: `(deny network*)` then allow loopback TCP (`localhost:*` outbound/bind/inbound — Seatbelt requires the `localhost` token, IP literals are rejected) + `unix-socket` for local IPC. Sets `SOVEREIGN_AIRGAP_KERNEL=seatbelt`.
   - ⛔ **macOS-only.** No Linux equivalent yet — the target deployment OS. 🔜 `M2` (netns wrapper + expanded battery).
   - 🟡 **Documented DNS quirk**: mDNSResponder is reachable via allowed AF_UNIX outside the profile, so hostname *resolution* still works under Seatbelt (no connection is possible). App uses literals only; strictest demo adds PF/Wi-Fi-off.

**Verification (committed evidence)** — `scripts/airgap/verify_airgap.py`, 6 checks: health, kernel-deny external, loopback OK (Ollama reachable), app selftest, 4-probe escape battery, **real qwen2.5:1.5b inference under policy**. Exit 0 iff all pass; report written to `evidence/` (`airgap_report_20261101T125329Z.md/.json` — ALL PASSED). Escape probes: plain `socket`, raw `_socket`, child `curl`, `ctypes`/libc — all EPERM/blocked under kernel policy; probe 1 stopped by sandbox prelude at app layer. Verdicts are decided by exfil-marker output, not exit codes (probes 3–4 exit 0 by design).

## 4. Cross-cutting properties

- **Concurrency**: single uvicorn event loop; orchestrator runs in the default executor; Ollama serializes inference. No queue, no GPU scheduler. ⛔ → 🔜 `M4`.
- **Failure handling**: every gateway/LLM call is try/except-wrapped with deterministic fallbacks (offline mode still completes tasks). Sandbox timeout → clean `TimeoutExpired` result.
- **Logging**: none structured (print/uvicorn default). ⛔ → 🔜 `M6` structured JSON logs w/ request IDs.
- **Packaging**: none. Dev-run only: `uvicorn app.main:app`. 11 pinned deps (`backend/requirements.txt`); Tesseract is an OS-binary prerequisite outside pip. ⛔ → 🔜 `M3`.
- **Testing**: `tests/ws_smoke.py` (manual, drives the 5 demos over WS) + `verify_airgap.py`. No unit tests, no CI. ⛔ → 🔜 `M0-continue`/CI in `M2`.
- **Tenancy**: single-user, localhost. ⛔ auth/users entirely → 🔜 `M1`.

## 5. Data flows (as-built)

1. **Task**: UI → WS `{task, attachments}` → orchestrator (executor thread) → events stream back; final `TaskContext` registered in memory. Nothing persisted.
2. **Upload**: browser multipart → `_safe_filename` → `workspace/uploads/`. KB upload same into `kb/` + manual re-index.
3. **Deliverable**: tool writes into `workspace/outputs/` → listed in UI → `/api/download` (workspace-contained).
4. **RAG**: `kb/` files → chunk → embed (Ollama or hash fallback) → `vector_store.json` → cosine search at query time.
5. **Generated code**: model → `_conform_args` → prelude + code written to `sandbox/run_<id>/main.py` → `python -I` child → stdout/stderr back into the loop (→ repair or verified artifact).

## 6. Known technical debt (register for the backlog)

| # | Item | Where | Milestone |
|---|---|---|---|
| 1 | No auth on any route | all of `main.py` | M1 |
| 2 | No persistence (tasks, egress events, sessions) | `TaskManager`, `egress._events` | M4 |
| 3 | TaskManager write-only (no read API) | `orchestrator.py:663–673` | M4 |
| 4 | macOS-only kernel air-gap | `scripts/airgap/` | M2 |
| 5 | Sandbox: no rlimits/jail; child procs not Python-blocked | `local_tools.py` `_SANDBOX_PRELUDE`, `run_python` | M7 |
| 6 | Whole-file JSON vector store; no incremental index | `rag/store.py` | M6 |
| 7 | Scanned-PDF KB ingestion ignores images (no OCR at ingest) | `rag/store.py` `_iter_documents` | M5 |
| 8 | No structured logs / request IDs / metrics | everywhere | M6 |
| 9 | ~~Hardcoded AIR-GAP pill~~ **closed (F.1)** — pill derived from `kernel_policy` + `last_escape_test` | `egress.py` · `app.js` · `index.html` | ✅ |
| 10 | No unit tests / CI; smoke test is manual | `tests/` | M2 |
| 11 | Constants-only config; no env/deployment config | `config.py` | M3 |
| 12 | Single in-proc orchestrator; no task queue/cancellation | `main.py` `run_task_and_stream` | M4 |

## 7. M0 team ownership (subsystems, from PRODUCTION_PLAN §10)

| Subsystem | Owner slot |
|---|---|
| Architecture/integration/releases | Technical lead |
| Auth, API, database, task manager | Backend engineer |
| Air-gap (Linux), sandbox, security testing | Security engineer |
| Models, ingestion, RAG, evals | AI/RAG engineer |
| Docker, offline deployment, monitoring | DevOps engineer |
| UI, workflow validation, QA, docs | Product/QA engineer |

*Ownership is accountability, not exclusivity: every subsystem needs docs, tests, and a second maintainer before v1.0.*
