# SIH Demo Video — 75-Second Shot List
**Purpose:** the YouTube link on the SIH portal submission. Judges decide in the first 10 seconds — lead with the working system, not the problem statement.

**Target length:** 70–80 s · **Style:** screen recording + voiceover (record voice live; no music needed)

---

## Before recording (10 min setup)

1. `brew services` off — quit every app except the browser; **turn on Do Not Disturb** (System Settings → Notifications).
2. Terminal: `cd backend && uvicorn app.main:app --port 8000` — leave it running.
3. Browser at `http://127.0.0.1:8000`, viewport ~1600×1000, zoom 100%.
4. **Warm the models**: click the "📚 Ask the local knowledge base" demo once and let it finish. (First call after a cold start pays model-load + KV warm-up; the recorded run will then be smooth and faster.)
5. Clear `workspace/uploads/` and `workspace/outputs/` of old test files so the demo folders look clean.
6. QuickTime → File → New Screen Recording → record the browser window only (not the whole desktop).
7. Do ONE unrecorded dry run of the flagship demo so you know the exact click timing.

## Shot list

| # | Time | On screen | Narration (speak naturally, don't read) |
|---|---|---|---|
| 1 | 0:00–0:07 | The Workbench UI, whole window | "This is our entry for SIH 26117 — an agentic AI workbench that runs **entirely on-premise**. Everything you're about to see happens on this one machine, with zero internet." |
| 2 | 0:07–0:15 | Right panel: Network Sovereignty Monitor ("0 external blocked") + Local Engine (4 models) | "Four open-weight models — Qwen for reasoning, Qwen-Coder for code, Moondream for vision, Nomic for retrieval — all served locally. And this monitor proves the sovereignty claim: watch the counter all video." |
| 3 | 0:15–0:20 | Left panel: click **"📄 Scanned report → approval note"** | "The problem it solves: this scanned inspection report has **no text layer at all** — it's pure image. Today an engineer reads it manually for days. Watch this." |
| 4 | 0:20–0:45 | Center timeline as it fills: routing → extract_pdf → OCR → knowledge base hits with scores → create_docx. **If the run takes >30 s, speed the footage 2× here in editing.** | "The agent routes the task, extracts the pages, detects the scan, and OCRs it — locally. Then it searches the company's own SOP knowledge base, finds the acceptance criteria, and drafts an approval note — as an actual Word file, grounded in the retrieved text." |
| 5 | 0:45–0:55 | Deliverables panel: click the .docx link → it opens/preview shows the note | "There's the deliverable — not a chat reply, a real document an engineer can review and sign." |
| 6 | 0:55–1:05 | Right panel: click **"🛰️ Air-gap self-test"** → monitor shows external attempt BLOCKED | "And the part MRPL's security team cares about: we deliberately try to reach the internet — and the workbench **blocks itself**, and logs it. That's provable sovereignty, not a slide claim." |
| 7 | 1:05–1:15 | Back to full UI, zoom out | "Team Cybernetics, BITS Pilani Goa — PS 26117. Working prototype, every flow benchmarked. Thank you." |

## After recording

- Trim dead air; optionally speed up shot 4 (the agent run) — the timeline events flying by at 2× looks *good*.
- Export 1080p, upload **unlisted**, paste the link in the SIH portal field.
- Title: `SIH 2026 – PS 26117 – Sovereign On-Premise Agentic AI Workbench (Team Cybernetics, BITS Pilani Goa)`
- Description: 2 lines — what it is + "All inference, RAG, OCR and tooling run locally (Ollama, qwen2.5 1.5B-class models). Zero cloud calls — demonstrated live." + GitHub link.

## Fallbacks while recording

- Demo stalls → don't narrate panic; say "while this completes —" and move the mouse to point at the routing panel / model list (real content fills the pause).
- Run fails → stop recording, rerun (tasks are independent), or fall back to the QA demo (16 s, most reliable) and the self-test.
- If moondream/vision is slow that day, the QA + code demos also satisfy "all four flows" — mention them verbally over their one-click runs.
