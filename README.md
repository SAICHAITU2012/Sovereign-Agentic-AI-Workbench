# Sovereign On-Premise Agentic AI Workbench (SIH26117)

A working reference implementation of **SIH26117 — "Sovereign On-Premise Agentic
AI Workbench using Open-Weight Multimodal LLMs for Confidential Industrial
Work"** (problem origin: Mangalore Refinery and Petrochemicals Limited).

Everything — inference, embeddings, retrieval, tools, document generation and
the UI — runs **on the local machine**. The air-gap is enforced in two layers:

1. **App layer (always on)** — `socket.connect()` is guarded in the backend:
   non-loopback attempts are blocked *and logged* (UI Network Sovereignty
   Monitor). A Python-level guard can be bypassed by hostile generated code.
2. **Kernel layer (macOS, recommended)** — launched via
   `scripts/run_airgapped.sh`, the whole process tree runs under a Seatbelt
   profile that refuses every non-loopback socket operation *at the syscall
   level* — including raw `_socket`, child processes spawned by generated
   code, and ctypes/libc syscalls. `POST /api/network/sandbox_escape_test`
   proves this empirically; `evidence/` holds a signed-off verification run.

## Architecture

```
Workbench UI (localhost)
   │  WebSocket: live agent events
   ▼
Agent Orchestrator ──── plan → choose tool → observe → iterate → deliverable
   │
   ├── Model Router ─── task classification + per-capability model selection
   │      reasoning: qwen2.5:1.5b · coding: qwen2.5-coder:1.5b
   │      vision: moondream · embedding: nomic-embed-text   (all local, Ollama)
   ├── Local Tools ──── file I/O · sandboxed Python · docx/xlsx/pptx
   │                    PDF extraction · OCR · vision analysis · KB search
   └── Local RAG KB ─── nomic-embed-text vectors (hashed TF-IDF fallback)
        workspace/kb — SOPs, manuals, past correspondence

socket.connect() is monkey-patched: loopback only, everything else blocked.
Under run_airgapped.sh the kernel additionally refuses all non-loopback
syscalls for the entire process tree (Seatbelt profile scripts/airgap/).
```


## Run

```bash
# 0. system dependency (one-time) — pytesseract needs the Tesseract OS binary;
#    pip alone will NOT install it, and OCR silently falls back to the VLM without it
#    macOS:          brew install tesseract
#    Debian/Ubuntu:  sudo apt install tesseract-ocr

# 1. models (one-time)
ollama pull qwen2.5:1.5b qwen2.5-coder:1.5b moondream nomic-embed-text

# 2. python deps
pip install -r backend/requirements.txt

# 3. demo assets (one-time)
python3 scripts/make_demo_assets.py

# 4. start — recommended: kernel-enforced air-gap (macOS)
./scripts/run_airgapped.sh            # same app on http://127.0.0.1:8000,
                                      # whole process tree: loopback only
#    … or plain (app-layer guard only):
cd backend && uvicorn app.main:app --port 8000
# open http://127.0.0.1:8000
```

## Verify the air-gap (adversarial battery)

With the workbench running under `run_airgapped.sh`:

```bash
python3 scripts/airgap/verify_airgap.py
```

Six checks, exit code 0 iff all pass, report written to `evidence/`:
the kernel refuses external HTTPS from any process in the tree (T1a) while
loopback/Ollama still works (T1b); the app guard blocks and logs an outbound
attempt (T2); four escape attempts run through the *real* sandbox tool —
plain `socket`, raw `_socket`, an unguarded `curl` child, raw
`ctypes`/libc syscalls — and all fail (T3); and a real local LLM inference
completes while the policy is active (T4). A passing run is committed under
`evidence/` as the audit trail.

## Run

```bash
# 0. system dependency (one-time) — pytesseract needs the Tesseract OS binary;
#    pip alone will NOT install it, and OCR silently falls back to the VLM without it
#    macOS:          brew install tesseract
#    Debian/Ubuntu:  sudo apt install tesseract-ocr

# 1. models (one-time)
ollama pull qwen2.5:1.5b qwen2.5-coder:1.5b moondream nomic-embed-text

# 2. python deps
pip install -r backend/requirements.txt

# 3. demo assets (one-time)
python3 scripts/make_demo_assets.py

# 4. start
cd backend && uvicorn app.main:app --port 8000
# open http://127.0.0.1:8000
```

## The four required demos (one-click buttons in the UI)

1. **Scanned inspection report → approval note** — image-only PDF (no text
   layer) → pypdfium2 page renders → OCR/vision → RAG lookup of
   EMP-SOP-014/PV-MAN-02 → grounded Word deliverable.
2. **Coding task, sandbox-verified** — the coding model writes Python, the
   sandbox executes it (no network, no subprocess, 30 s timeout), errors are
   fed back for repair and the code is re-run until it passes.
3. **Multimodal** — a P&ID drawing is analysed by the local vision model.
4. **Knowledge QA** — answered strictly from the local knowledge base.

## Key properties judges look for

- **Sovereign**: zero cloud APIs in the codebase; the air-gap is kernel-
  enforced (macOS Seatbelt) for the whole process tree, with the app-level
  guard as a logged second layer — and a committed adversarial evidence
  report under `evidence/`.
- **Model-agnostic**: adding an open-weight model = one entry in
  `backend/app/config.py` `MODEL_REGISTRY`.
- **Agentic, not chatbot**: plan → tool calls → observations → iteration, with
  a self-healing execute→repair→re-run loop for code.
- **Real deliverables**: .docx/.xlsx/.pptx/.py files in `workspace/outputs/`,
  downloadable from the UI.
- **Small-hardware friendly**: 1.5B-class models fit a mid-range GPU; the
  router falls back across the registry, and RAG falls back to a hashed
  TF-IDF local embedder if the embedding model is missing.
