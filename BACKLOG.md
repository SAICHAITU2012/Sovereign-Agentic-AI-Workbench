# BACKLOG — Sovereign Workbench execution plan (v1.1, revised per external review)

**Date:** 2026-11-13 · **v1.0:** 2026-11-06 (43 issues) · **v1.1:** one controlled revision applying all 14 findings from the BACKLOG technical review — issue IDs preserved, two issues added (M1.0, M2.5), priorities/dependencies/gates reconciled. Revision log: §7.
**Sources:** `PRODUCTION_PLAN.md` v2.0 · `ARCHITECTURE.md` · `SECURITY_MODEL.md` · external BACKLOG review (2026-11-13).
**Status:** revised draft → approval → commit → push → GitHub issues.

## 0. How to read this backlog

**Priority (within a milestone)**
- **P0** — the milestone gate cannot pass without it.
- **P1** — required for the gate's promised quality; may slip within the milestone, never past the next one.
- **P2** — valuable; defer without guilt unless capacity appears.

**Gate rule (v1.1):** within-milestone priority ≠ gate membership. A P1/P2 issue can still be a **hard prerequisite of a later milestone's gate** (e.g., M2.5 → M7 gate). What blocks is the gate's own list, not the priority label alone. Conversely, P0 never means "implement immediately" — it means "gate-defining".

**Owners** (roles from `ARCHITECTURE.md` §7): **Lead** · **Backend** · **Security** · **AI/RAG** · **DevOps** · **QA**.

**Standard DoD — applies to every issue, stated once:** merged to `main`; tests green (or committed manual test script); the matching rows in `ARCHITECTURE.md`/`SECURITY_MODEL.md` updated in the same commit series; no unpinned dependency; evidence artifact committed. Per-issue DoD lists only *additional* requirements.

**Issue ID scheme:** `M<n>.<seq>` — 1:1 to future GitHub issues labelled `milestone-M<n>`, `P0/P1/P2`, owner-role.

---

## 1. Milestone dependency overview

```
M0 docs ✅ ──▶ M1 auth ──────────┐
   │        (M1.0 contract ──┐)  │
   ├──▶ M2 linux-gap ────────┼──▶ M6 enterprise alpha ──▶ M7 hardening ──▶ M8 first customer ──▶ M9 commercial
   ├──▶ M3 appliance ────────┤        ▲                     ▲
   └──▶ M4 backend ──────────┘        │                     │
        M5 evals (starts early) ──────┴─────────────────────┘
   contracts: M1.0 = DATA_CONTRACT.md shared by M1 (auth) and M4 (persistence) — parallel work, one schema
   late prereqs: M2.5 (RHEL battery) gates M7; M5 baseline gates M6 acceptance
```

| Milestone | Objective (one line) | Blocked by | Issues | P0 |
|---|---|---|---|---|
| **M0** — definition & freeze | Docs that describe reality | — | ✅ **DONE** (`4febc63`) + fixes F.1–F.3 | 2 |
| **M1** — security & access foundation | Nobody uses the workbench without a login; DB contract fixed first | M0 | 5 | 5 |
| **M2** — provable Linux sovereignty | The flagship claim works on the deployment OS, with topology stated honestly | M0 | 5 | 2 |
| **M3** — deployable appliance | One-command install on a clean machine | M0 | 4 | 2 |
| **M4** — reliable backend | Restart-safe, concurrent, retryable tasks | M1.0 (contract) | 4 | 4 |
| **M5** — measurable AI quality | Every AI change is a measured decision | M0 (starts early) | 4 | 1 |
| **M6** — enterprise alpha | Real users do real work; outputs get human sign-off | M1, M3, M4 (M5 baseline for acceptance) | 5 | 4 |
| **M7** — production hardening | Passes an enterprise security review | M5, M6, M2.5 | 7 | 5 |
| **M8** — first real customer | One organization deploys and accepts it | M7 + Track-B evidence | 3 | 2 |
| **M9** — commercialisation | Repeatable deployments, revenue, channel | M8 | 5 | 0 |

M1/M2/M3/M4 run **in parallel** after M0 — but M1 and M4 both implement against the **M1.0 data contract** (review finding 2), not against independently invented schemas.

---

## 2. Immediate fixes (this week, before M1 starts)

| ID | Fix | P | Owner | Acceptance |
|---|---|---|---|---|
| **F.1** | Derive the header air-gap pill from real state (read `SOVEREIGN_AIRGAP_KERNEL` + latest `sandbox_escape_test` verdict) instead of the hardcoded `AIR-GAP: ENFORCED` at `index.html:20` | P0 | QA | Pill shows `KERNEL: SEATBELT` / `KERNEL: NETNS` / `APP GUARD ONLY` / `UNVERIFIED`; manual check in all launch modes |
| **F.2** | Comment the load-bearing import order in `main.py:21` (`egress.install_egress_guard()` before any module that can open sockets) + a unit test asserting the patch is installed at import time | P0 | Backend | Comment block present; test fails if the guard call is moved below other imports |
| **F.3** | Choose and apply a `LICENSE` | **P1** *(v1.1: demoted from P0 — administrative, blocks no gate; do it before DPIIT/GeM/public distribution)* | Lead | LICENSE committed; README license section added |

---

## 3. Track separation (prototype vs enterprise vs commercial)

| Track | Milestones | Nature | Exit criterion |
|---|---|---|---|
| **Prototype-correctness** | M1–M4 + F.1–F.2 | Makes the prototype trustworthy, safe, reproducible. No enterprise features. | v0.5.0 tagged; ARCHITECTURE §6 items 1–4, 11–12 closed |
| **Enterprise-production** | M5–M7 | What an enterprise security review and a paying pilot demand | v1.0 Production; VAPT rules (M7.7) met; compliance mapping delivered |
| **Commercial** | M8–M9 | Turning a validated product into a business | Signed pilot → 2–3 sites, AMC |

**What already exists — do not rebuild (from `ARCHITECTURE.md`, all ✅):** agentic loop with self-heal · model gateway + registry · task router with auditable evidence · 8 local tools · RAG with offline fallback embedder · egress guard + escape battery + committed evidence · upload sanitization · path containment · 5 demo flows + self-test. Every issue below changes or extends these; none re-creates them.

---

## 4. Milestones M1–M9

### M1 — Security & access foundation (closes T3/T12; C10)

**Objective:** the workbench cannot be used by anyone without an account; sessions hardened; every route protected; the persistence **contract** fixed so M1 and M4 never diverge. Single-org scope — no enterprise identity yet.
**Baseline today:** ⛔ no auth anywhere; ⛔ C10.

**M1.0 — Persistence & interface contract (P0 · Backend+Lead · deps: none) *(new in v1.1 — review finding 2)***
- Scope: `docs/DATA_CONTRACT.md` — the single SQLite schema for `users`, `sessions`, `tasks`, `egress_events` (column definitions, owners per table), the session-store and task-store interface signatures both M1 and M4 code against, migration-runner ownership (M4.1 owns the runner; M1 owns the users/sessions table definitions), integration owner = Backend.
- Acceptance: contract committed; M1.1 and M4.1 both implement against it; a **schema-drift test** asserts the live DB schema matches the contract (fails on divergence).
- DoD/Evidence: `docs/DATA_CONTRACT.md`; drift test.

**M1.1 — Auth core (P0 · Backend · deps: M1.0)** *(v1.1: F.3 dependency removed)*
- Scope: user store via the M1.0 contract (no standalone table), bcrypt hashing, login/logout endpoints, server-side sessions, admin bootstrap on first run (credentials printed once to console, never logged again), password-reset-by-admin procedure.
- Acceptance: `POST /api/auth/login` issues a session; wrong password → 401 + rate-limit counter; `GET /api/auth/me` returns the user; no plaintext or recoverable passwords (verify: DB dump).
- DoD/Evidence: auth module; test-user fixture; `evidence/auth_core_check.md`.

**M1.2 — Route protection & authz skeleton (P0 · Backend · deps: M1.0, M1.1)** *(v1.1: route classes separated; isolation claim moved to M6.2)*
- Scope: protection on **every** route, enumerated by class: HTTP `/api/*` (dynamic enumeration test), **WebSocket handshake** (token via first message), **static frontend assets** (stay public — they contain no data; `app.js` gates on `/api/auth/me` and shows the login view), **intentionally-public endpoints: an explicit exception list, default = `/api/auth/login` only** (`/api/health` becomes protected; a redacted public variant is an implementation-time decision, documented either way). Ownership key (`user_id`) recorded on tasks and sessions — **this enables M6.2 to prove isolation; M1 does not claim user-to-user isolation** (review finding 6).
- Acceptance: enumeration test fails when a new route is added unprotected; WS without auth closed by server; exception list asserted in the test, not implicit.
- DoD/Evidence: route-inventory test; SECURITY_MODEL C10 → 🟡.

**M1.3 — Session hardening (P0 · Backend · deps: M1.1)**
- Scope: `Secure`/`HttpOnly`/`SameSite=Lax` cookies, expiry + sliding window, logout revokes server-side, login rate limiting (per-IP + per-user lockout), CSRF strategy for cookie auth on state-changing routes, secrets via env (`SESSION_SECRET`), no credentials in logs (log-scrub test).
- Acceptance: expired session → 401; revoked → 401 immediately; 5 failed logins → lockout with retry-after; CSRF-less cross-site POST → rejected.
- DoD/Evidence: SECURITY_MODEL C10 ✅ (in-proc sessions; persistence lands via M4.1/contract).

**M1.4 — Auth security test suite (P0 · Security · deps: M1.2, M1.3)**
- Scope: pytest suite covering M1.1–M1.3 acceptance criteria + session fixation + cookie-flag assertions; runs in CI from M2.3.
- Acceptance: `pytest tests/test_auth.py` exit 0; suite red if any route is made unprotected (mutation check).
- DoD/Evidence: suite committed.

**M1 gate (all P0):** every endpoint rejects unauthenticated requests per the route-class rules; ownership key present (isolation *proved* later at M6.2); expiry/revocation/lockout work; suite green; contract test green.

---

### M2 — Provable Linux sovereignty (closes T1-Linux; C2-Linux; tests T8)

**Objective:** kernel-enforced no-egress, adversarially verified, on Ubuntu and RHEL-class — with the namespace topology and its residual limits stated as honestly as the macOS one.
**Baseline today:** ✅ macOS Seatbelt + battery + evidence; ⛔ nothing on Linux.

**M2.1 — Linux network-namespace isolation (P0 · Security · deps: none)** *(v1.1: topology + honest-boundary requirements added — review finding 3)*
- Scope: `scripts/airgap/linux/run_airgapped.sh` + `docs/NAMESPACE_TOPOLOGY.md`. **Topology decision (explicit, not assumed):** default = **Ollama runs inside the same namespace** (it needs no external network — this keeps the entire inference stack within one isolated boundary; a fresh netns's loopback does *not* reach a host Ollama on `127.0.0.1:11434`). Alternative topologies (veth pair + allow rule) must be documented with justification and their weaker boundary stated. Set `SOVEREIGN_AIRGAP_KERNEL=linux-netns`.
- Acceptance: on clean Ubuntu 22.04 VM — backend + **Ollama** + sandbox children inside the namespace; external IPv4 **and IPv6** from any process in the tree fails; loopback inference works; `ip link` inside the ns shows no unintended interfaces; child-process inheritance verified (battery runs through the real `run_python` path); residual-limitations section written (netns constrains *network only* — capabilities, filesystem, privileges assessed separately, per SECURITY_MODEL).
- DoD/Evidence: `docs/NAMESPACE_TOPOLOGY.md`; `evidence/airgap_report_<linux-date>.*`; SECURITY_MODEL §6 Linux row stays ⛔ until this evidence exists.
- **Standing caveat (every M2/M7 document):** network isolation evidence ≠ complete system security evidence.

**M2.2 — Expanded adversarial battery, both OSes (P0 · Security · deps: M2.1)**
- Scope: extend `verify_airgap.py`: DNS attempt, IPv6 target, host-network access, simultaneous children, UNIX-socket abuse; exfil-marker verdicts; per-probe `enforced_by` for Linux.
- Acceptance: battery (~10 probes) exit 0 on macOS+Seatbelt **and** Ubuntu+netns; positive control passes (local inference + local I/O under policy).
- DoD/Evidence: battery report per OS; SECURITY_MODEL §8 Linux reproduce commands.

**M2.3 — Evidence automation in CI (P1 · DevOps · deps: M2.2, M3.1)** *(v1.1: CI tests the deployed boundary, not a bare probe container)*
- Scope: GitHub Action per push: build the M3.1 compose stack, run the battery **inside the deployed stack** (the actual deployment security boundary, including the sandbox path tasks take), publish report artifact; run the auth + drift + concurrency pytest suites.
- Acceptance: deliberately-broken probe → CI red; revert → green; artifact history public.
- DoD/Evidence: CI badge; artifact stream.

**M2.4 — Physical air-gap operations guide (P2 · Security · deps: M2.1)** *(v1.1: guide only — validation split out)*
- Scope: `docs/AIRGAP_OPERATIONS.md`: no-network install, transfer procedures (signed bundles at M7.6), PF/Wi-Fi-off belt-and-braces for strictest demos.
- Acceptance: guide reviewed by Lead; matches actual scripts.
- DoD/Evidence: the guide.

**M2.5 — RHEL-class battery validation (P1 within M2 · Security · deps: M2.1, M2.2) *(new in v1.1 — review finding 4)*** · **hard prerequisite of the M7 gate** (listed in M7.7 deps; M7 cannot pass without it)
- Scope: validate netns + battery on a RHEL-family VM (PSU reality).
- Acceptance: battery green on RHEL-class; report committed.
- DoD/Evidence: third OS row in the evidence matrix.

**M2 gate:** battery green on Ubuntu with committed Linux evidence (M2.5 is *not* required for the M2 gate — it is required for M7's).

---

### M3 — Deployable appliance (closes gap #4)

**Objective:** a clean Ubuntu machine runs the full stack from a supplied offline bundle — no pip, no debugging, restart-safe.
**Baseline today:** dev-run only; 11 pinned deps; constants-only config.

**M3.1 — Dockerfile + Compose stack (P0 · DevOps · deps: none)** *(v1.1: canonical demo inventory defined — review finding 7)*
- Scope: app image (python + tesseract + deps), Ollama sidecar, persistent volumes (`workspace/` + model store), healthchecks, startup ordering, graceful shutdown. **Canonical demo inventory = whatever `tests/ws_smoke.py` DEMOS enumerates (today: 5 — doc, code, vision, qa, office — plus the air-gap self-test).** The acceptance test enumerates that inventory programmatically; no hardcoded count. README's stale "four required demos" section is corrected in this issue's DoD.
- Acceptance: `docker compose up` on clean VM → all enumerated demo flows pass via `ws_smoke.py`; container restart → KB intact.
- DoD/Evidence: `deployment/Dockerfile`, `docker-compose.yml`; smoke transcript; README fix.

**M3.2 — Offline install bundle (P0 · DevOps · deps: M3.1)** *(v1.1: absence-of-communication ≠ absence-of-internet)*
- Scope: `offline-export.sh` (images + vendored wheels + model blobs + checksums) and `install.sh` (verify → `docker load` → up → health); model import procedure (no registry pulls on site).
- Acceptance: on an air-gapped clean VM: bundle → healthy stack ≤30 min; **two distinct proofs recorded: (a) no internet access, (b) no unintended network communication** — battery green inside the stack + listening-socket/interface audit showing only expected endpoints.
- DoD/Evidence: bundle manifest; both proofs in the install transcript; `deployment/docs/OFFLINE_DEPLOYMENT.md`.

**M3.3 — Ops scripts + installation docs (P1 · DevOps · deps: M3.1; DB backup/restore portion also depends on M4.1)** *(v1.1: dependency added — review finding 8)*
- Scope: `health-check.sh`, `backup.sh`/`restore.sh` (workspace + vector store; DB round-trip testable only after M4.1), `INSTALLATION.md`, `TROUBLESHOOTING.md`.
- Acceptance: backup→wipe→restore reproduces KB stats (+ task list once M4.1 lands).
- DoD/Evidence: scripts + docs + restore transcript.

**M3.4 — Env-based config + SBOM (P1 · Backend+DevOps · deps: M3.1)**
- Scope: env overrides (port, paths, registry overrides, `STRICT_AIRGAP` dev toggle) with safe defaults; SBOM (syft or pip-licenses) into the bundle; hash-pinned wheels.
- Acceptance: `SOVEREIGN_PORT=9000 docker compose up` serves on 9000; SBOM committed; no secret defaults into the image (grep test).
- DoD/Evidence: config diff + SBOM; ARCHITECTURE §2.2 🟡 cleared.

**M3 gate:** clean-VM checklist (load → configure → up → enumerated demos → restart-keeps-data) passes, zero manual pip.

---

### M4 — Reliable backend (closes gaps #2, #10; tech-debt 2, 3, 12)

**Objective:** tasks, egress events, sessions survive restarts; concurrency queues; failures visible, retryable, and cancellable.
**Baseline today:** in-memory write-only TaskManager; in-memory egress deque; no queue/cancellation/retry.

**M4.1 — SQLite persistence layer (P0 · Backend · deps: M1.0)** *(v1.1: implements the contract, owns the migration runner)*
- Scope: SQLite (WAL) via SQLModel implementing the M1.0 contract: `tasks` (full TaskContext incl. actions/deliverables JSON), `egress_events` (+ hosts `users`/`sessions` tables per contract); write-through from the orchestrator; migration runner.
- Acceptance: demo → `kill -9` → restart → history + egress events queryable; two writers don't corrupt (WAL check); live schema passes the M1.0 drift test.
- DoD/Evidence: schema doc; `evidence/restart_recovery_transcript.txt`.

**M4.2 — Task lifecycle API incl. retry (P0 · Backend · deps: M4.1)** *(v1.1: retry semantics defined — review finding 9)*
- Scope: `GET /api/tasks` (own; admin all), `GET /api/tasks/{id}` (full timeline), states `running/completed/failed/cancelled/interrupted` (startup reconciliation marks orphans). **Retry semantics (explicit):** retryable = sandbox/tool errors, model-unavailable, timeout; not retryable = completed tasks (resubmit instead). Retry creates a **new task linked to the original** (audit preserves both); resume-from-step is out of scope for v0.5 and recorded in the deferred register. UI "Past tasks" list (minimal, with QA).
- Acceptance: kill mid-task → `interrupted` with partial actions; retryable failure → retry → new linked task runs; UI list renders.
- DoD/Evidence: endpoint tests; UI screenshot; tech-debt 3 closed.

**M4.3 — GPU queue & cancellation (P0 · Backend · deps: M4.1)**
- Scope: asyncio semaphore (configurable, default 1) around inference-bound sections; cooperative cancellation at step boundary; queue position in WS events.
- Acceptance: 3 concurrent tasks → serialized, no corruption, 3rd shows "queued (2 ahead)"; cancel → stops ≤5 s, status `cancelled`.
- DoD/Evidence: concurrency test + transcript; ARCHITECTURE §4 updated.

**M4.4 — Concurrency & recovery test suite (P0 · QA · deps: M4.1–M4.3)** *(v1.1: P1→P0 — the M4 gate and the M6 pilot depend on this evidence; review finding, §4 table)*
- Scope: automated suite: parallel WS tasks, kill/restart matrix, DB-lock stress, event-stream integrity (exactly-once delivery per connection).
- Acceptance: suite green locally and in CI (M2.3); red = M4 gate blocker.
- DoD/Evidence: `tests/test_concurrency.py`, `tests/test_recovery.py`.

**M4 gate:** restart preserves history; concurrent tasks queue; retry + cancellation semantics work per M4.2; M4.4 suite green.

---

### M5 — Measurable AI quality (closes gap #6; tech-debt 7)

**Objective:** AI/model/ingestion changes become measured decisions against a frozen baseline.
**Baseline today:** zero evals; 732-chunk JSON store; no scanned-PDF/office ingestion.

**M5.1 — Eval dataset + harness (P0 · AI/RAG · deps: none)**
- Scope: 50–100 Q/A pairs over the demo KB **plus** ≥10 over realistic messy documents (tables, scanned images); metrics: Hit@5, MRR, groundedness, citation accuracy, latency, failure rate; offline runners (Ragas/DeepEval); `scripts/eval_retrieval.py` + report generator → `evidence/`.
- Acceptance: harness runs offline; baseline committed; re-run reproduces ±2%.
- DoD/Evidence: `evidence/eval_baseline_<date>.md` — the anchor for every future change.

**M5.2 — Model benchmark & registry decision (P1 · AI/RAG · deps: M5.1)**
- Scope: incumbents (qwen2.5:1.5b/coder) vs candidates (qwen3.5:4b/9b, bge-m3) on the suite + tool-calling checks; adopt/reject per candidate; swap only on measured win without latency/security regression.
- Acceptance: comparison report with per-metric deltas; explicit decision per candidate.
- DoD/Evidence: `evidence/model_benchmark_<date>.md`; registry diff if adopted.

**M5.3 — Layout-aware ingestion + format coverage (P1 · AI/RAG · deps: M5.1)** *(v1.1: acceptance criteria corrected — review finding 10)*
- Scope: Docling (Apache-2.0, offline) for PDF structure (headings/tables) into chunking; `.xlsx/.pptx` ingestion (tech-debt 7's format gap); structure-preserving chunk metadata; delta reindex (skip unchanged files).
- Acceptance: **(a)** structure-fidelity check — headings/tables from the messy subset extracted and located (manual-auditable samples committed); **(b)** retrieval target on the messy-doc subset (e.g., ≥80% of those questions retrieve the containing chunk in top-5 — target set in the issue); **(c)** no regression beyond ±2% on the existing eval set; **(d)** processing time + resource consumption reported. *Aggregate-metric improvement is reported, not required — a format-coverage feature is not rejected because a blended average doesn't rise.*
- DoD/Evidence: before/after report incl. (a)–(d); ARCHITECTURE §2.8 updated.

**M5.4 — Scanned-PDF OCR at ingestion (P1 · AI/RAG · deps: M5.1)** *(v1.1: decoupled from M5.3 — reuses the existing `ocr_image` tool, no Docling dependency)*
- Scope: low-text pages route through `ocr_image` at KB ingest; OCR provenance marked; per-document time budget.
- Acceptance: scanned SOP demo doc indexes with full text (today: near-empty); scanned-doc eval subset defined and passing.
- DoD/Evidence: ingestion transcript + eval delta; tech-debt 7 closed.

**M5 gate:** baseline eval committed; every subsequent AI change shows a before/after report (enforced in review).

---

### M6 — Enterprise alpha (closes gap #5; first real users)

**Objective:** 10–20 people outside the team use it for real work for two weeks; deliverables get human sign-off; nothing lost between sessions.
**Baseline today:** single-user; no sign-off; no observability.

**M6.1 — Postgres + pgvector migration (P0 · Backend · deps: M1.0, M4.1, M3.1)**
- Scope: Postgres service in compose; migration script from SQLite; vectors → pgvector (HNSW) with TF-IDF fallback retained; one DB for users+sessions+tasks+audit+vectors.
- Acceptance: 10k-chunk KB search p95 < 100 ms; migration round-trips the KB losslessly; SQLite kept as dev fallback.
- DoD/Evidence: migration script + round-trip transcript; ARCHITECTURE §2.8 updated.

**M6.2 — Multi-user accounts, workspaces, quotas (P0 · Backend · deps: M1, M6.1)** — **this issue *proves* user-to-user isolation** (M1 only enabled it)
- Scope: admin-created users; per-user workspace roots (extend `_safe_path` base per user); per-user task filtering (join on the M1.2 ownership key); daily quotas; user/admin roles enforced server-side.
- Acceptance: negative matrix — user A cannot list/download/see user B's tasks or files; quota breach → 429 with reset time; admin sees all.
- DoD/Evidence: isolation test matrix; SECURITY_MODEL T3/T12 updated.

**M6.3 — Human-in-the-loop deliverable workflow (P0 · Backend+QA · deps: M6.2)**
- Scope: deliverable states `draft → in_review → approved/changes_requested`; diff view (docx→text diff acceptable for alpha); approver comment + immutable approval record (who/when/what hash); download centre with status badges. **An AI draft is never auto-approved.**
- Acceptance: full state machine covered by tests; approval record survives restart and is tamper-evident (hash chain).
- DoD/Evidence: workflow UI screenshots; state-machine test.

**M6.4 — Observability v1 (P1 · DevOps · deps: M3.1)**
- Scope: structured JSON logs with request/task IDs; task timeline from persisted events; optional self-hosted Langfuse; log rotation.
- Acceptance: any task's event trace reconstructable from logs alone; no secrets/PII in log lines (scrub test).
- DoD/Evidence: log sample + reconstruction transcript.

**M6.5 — Pilot protocol execution (P0 · Lead+QA · deps: M6.1–M6.4, M5 baseline)** *(v1.1: acceptance wording aligned to the plan; BITS ≠ organizational pilot — review finding 11)*
- Scope: recruit 10–20 pilot users; onboarding doc; 2-week window; weekly task-completion + feedback capture; failure-case log; exit interviews.
- Acceptance: **≥50 real tasks; ≥1 deliverable accepted without edits per external user per week** (v1.1: restored the plan's original wording — "without edits"; the charter defines precisely what counts as an edit, and formatting-only tweaks are recorded separately). **The gate counts only users external to the team; a BITS dress rehearsal may precede the pilot but its evidence is labelled rehearsal and does not satisfy this gate** — a successful rehearsal does not establish organizational acceptance.
- DoD/Evidence: `evidence/pilot_alpha_report.md` — the first *user* evidence in the repo.

**M6 gate:** pilot report shows repeated real usage + accepted outputs (per the restored criterion); eval numbers stable under multi-user load.

---

### M7 — Enterprise production hardening (closes T6, T7, T10, T11; C11–C14)

**Objective:** pass an enterprise security review; be chargeable. Start only after M6 proves the product solves a real problem.

**Gate (v1.1, review findings 4+5):** **C11–C14 all ✅ regardless of within-milestone priority** (M7.5 and M7.6 are P1 internally but gate-required); battery green on Ubuntu **and RHEL-class (M2.5)**; VAPT closure per the M7.7 rules; compliance mapping delivered.

**M7.1 — RBAC, LDAP/AD, TLS-on-LAN (P0 · Backend · deps: M6.2)**
- Scope: roles (admin/dept-lead/analyst/viewer) + department membership; LDAP/AD connector (config-driven, tested against a local LDAP container); TLS-on-LAN deployment doc. *(SAML/SSO beyond LDAP: deferred — see register §5.)*
- Acceptance: LDAP login + group→role mapping works against the test container; non-admin → 403 on admin API; HTTPS-on-LAN guide validated.
- DoD/Evidence: RBAC matrix test; LDAP transcript; deployment doc.

**M7.2 — Permission-aware RAG (P0 · Backend+AI/RAG · deps: M7.1, M6.1)**
- Scope: per-department KB scopes; permission tags at **ingestion**, filter at **retrieval**, re-check at **document access** — never delegated to the model; admin-visible retrieval audit (what was retrieved per answer, and why filtered).
- Acceptance: negative matrix — a user without dept X never receives X chunks even when topically best, across 20 crafted queries; audit log shows each filter decision.
- DoD/Evidence: isolation eval report (marketing-grade evidence).

**M7.3 — Audit & compliance pack (P0 · Backend+Lead · deps: M4.1, M6.3, M6.4, M7.1, M7.2)** *(v1.1: dependencies completed — audit covers events from all producers, not just logs — review finding 12)*
- Scope: append-only, hash-chained audit log spanning **every event class with a named producer**: logins (M1), task lifecycle incl. retries/cancellations (M4), approvals (M6.3), egress verdicts (egress module), admin actions (M6.2/M7.1), permission + retrieval decisions (M7.1/M7.2); 180-day retention + rotation; admin export (JSON/CSV) per CERT-In expectations; `docs/COMPLIANCE_MAPPING.md` mapping DPDP + CERT-In → control + evidence artifact.
- Acceptance: **audit-coverage checklist** — every event class mapped to its producing issue, verified by test; tamper attempt (DB edit) → chain verification fails loudly; export contains all mandated classes.
- DoD/Evidence: `docs/COMPLIANCE_MAPPING.md`; chain-verification test; export sample. **Caveat (stated in the doc): the hash chain provides tamper *evidence* under its assumptions — it does not by itself establish complete coverage (the checklist does), trusted timestamps (deferred, §5), or regulatory compliance by itself.**

**M7.4 — Hardened sandbox with explicit security tiers (P0 · Security · deps: M2, M3.1)** *(v1.1: silent fallback removed — review finding 13)*
- Scope: `SOVEREIGN_SANDBOX_TIER`: `container` (production — no network, read-only rootfs, tmpfs workdir, seccomp default, dropped capabilities, CPU/memory rlimits, wall+CPU timeouts) | `subprocess` (**dev only** — current mode). `SOVEREIGN_PROFILE=production` **refuses to execute untrusted generated code unless tier=container** (hard fail with explicit error); degraded mode shows a persistent UI warning + `/api/health` flag; tests assert production profile cannot start with the subprocess tier.
- Acceptance: escape battery (M2.2 set) green against the container tier on Linux; fork/memory bombs killed by rlimits within budget; positive control passes; **negative test: production profile + subprocess tier → refuses to run generated code**.
- DoD/Evidence: container-tier battery report; tier-test; SECURITY_MODEL C11 ✅, T6 closed.

**M7.5 — Guardrails & PII handling (P1 · AI/RAG+Security · deps: M5, M6.1)** *(v1.1: metrics defined — review §4)*
- Scope: prompt-injection heuristics + local classifier on ingested docs and tool outputs (quarantine+flag, never silent); per-KB optional PII redaction (Presidio, offline); decisions audited (M7.3). **Metric definitions:** injection corpus ≥20 vectors across named categories (direct override, encoded payload, multi-step, context-switching, exfil-in-code); *detection* = flagged or quarantined **before tool execution**; *false positive* = clean KB doc or benign tool output flagged, measured against the demo KB + M5.1 clean set. Report per-category and overall.
- Acceptance: ≥90% detection on the corpus (with per-category breakdown); FP rate <2% on the clean set; eval suite green with redaction on.
- DoD/Evidence: corpus + definitions + results report; T7 updated with residual-risk note (heuristics ≠ complete defense).

**M7.6 — Signed offline update bundles (P1 · DevOps+Security · deps: M3.2)** — gate-required (see M7 gate)
- Scope: release bundle = images + migrations + changelog, ed25519-signed; `apply-update.sh`: verify → backup → apply → health+battery → rollback support.
- Acceptance: tampered bundle refused; failed apply rolls back; update applied end-to-end on a network-isolated VM.
- DoD/Evidence: signing/verification transcript; T11 closed.

**M7.7 — Security validation & VAPT (P0 · Security+Lead · deps: M7.1–M7.6, **M2.5**)*** *(v1.1: RHEL dep explicit; risk-acceptance rules defined — review finding 14)*
- Scope: threat-model refresh (SECURITY_MODEL v2), OWASP ASVS L1 self-assessment, dependency scanning in CI, external VAPT, fuzz the path-containment surfaces (C6).
- Acceptance: **closure rules: critical findings must be fixed (no risk-acceptance); high findings may be formally risk-accepted only in writing by the Lead with a named remediation date, recorded in the remediation log; medium/lower tracked.** Gate metric: zero unresolved criticals, zero unaccepted highs. C6 fuzzed clean.
- DoD/Evidence: `evidence/vapt_report_<date>.md` + remediation log; procurement prerequisite.

---

### M8 — First real customer

**Objective:** one organization deploys, evaluates against agreed criteria, and formally accepts the pilot. MRPL via the SIH channel is the priority intro — **an introduction, not a sale**.

**M8.1 — Discovery → pilot agreement (P0 · Lead · deps: Track-B evidence artifact)** *(v1.1: discovery is an ongoing track — its output must exist as evidence, review §4)*
- Scope: one department, one document-heavy workflow; **evidence of ≥2 user interviews with named roles** (`evidence/discovery_log.md`: workflows, sensitive-data boundaries, security constraints); non-sensitive test dataset agreed in writing; measurable acceptance criteria; signed pilot agreement (scope, duration, data handling, exit terms).
- Acceptance: discovery log committed; signed agreement + written criteria; dataset delivered into the pilot environment.
- DoD/Evidence: `docs/PILOT_CHARTER_TEMPLATE.md` + signed charter.

**M8.2 — Pilot deployment & acceptance run (P0 · DevOps+QA · deps: M8.1, M7)**
- Scope: install via M3.2 bundle in the approved environment; onboard users (M6.2); run the agreed workflow for the pilot window; weekly triage; acceptance vs charter criteria.
- Acceptance: every charter criterion recorded pass/fail with evidence; issues resolved or customer-accepted.
- DoD/Evidence: install transcript on customer hardware; acceptance scorecard.

**M8.3 — Pilot results → commercial pack (P1 · Lead+QA · deps: M8.2)**
- Scope: results report (metrics, quotes, honest failures per claim policy); pricing proposal (POC ₹2–10 L anchor); reference-usable summary if the customer agrees; lessons → backlog.
- Acceptance: customer reviews and (target) accepts; commercial discussion scheduled with a named buyer.
- DoD/Evidence: `evidence/pilot_results_<customer>.md` (sanitized); pricing section updated with real data.

**M8 gate:** a real organization has deployed, evaluated against agreed criteria, and formally accepted the pilot. Paid conversion is the objective; the authorized successful pilot is the necessary first proof.

---

### M9 — Commercialisation & multi-site

**Objective:** stop selling custom projects; sell a repeatable appliance. **Build only what actual pilot customers demanded** (anti-goal §7.7 of the plan).

**M9.1 — Ansible deployment automation (P1 · DevOps · deps: M3.2)**
- Scope: playbook: bare VM → appliance (install, config, users, KB import, health+battery verification); idempotent.
- Acceptance: site #2 installed from the playbook by someone who didn't write it; time-to-live recorded.
- DoD/Evidence: playbook + two-site install transcripts.

**M9.2 — Fleet monitoring, customer-controlled (P2 · DevOps+Backend · deps: M9.1)**
- Scope: per-site status **off by default**; air-gap-safe manual export bundle aggregating health/usage/battery results.
- Acceptance: telemetry off = zero egress (battery proves it); on = customer-controlled export.
- DoD/Evidence: fleet report sample; battery runs both modes.

**M9.3 — Connector framework + first connector (P2 · Backend · deps: M8 pilot demand)**
- Scope: thin interface (auth, fetch, ingest-to-KB, schedule); build exactly the one connector a pilot customer needs. No speculative connectors.
- Acceptance: chosen connector pulls real documents into scoped KB on schedule, permissions intact (M7.2 tags preserved).
- DoD/Evidence: connector doc + customer-site transcript.

**M9.4 — Vertical workflow template pack #1 (P1 · QA+AI/RAG · deps: M8.3)**
- Scope: package the proven pilot workflow as a configurable template (prompts, KB schema, deliverable templates, criteria); 2-week packaging budget, not R&D.
- Acceptance: template reproduces the workflow on a fresh site with config changes only.
- DoD/Evidence: template pack + fresh-site repro transcript.

**M9.5 — Business/institutional track (P1 · Lead · deps: M8.3)** *(v1.1: GeM listing explicitly after customer validation, per the plan's sequencing)*
- Scope: DPIIT recognition (if not already done) → GeM Startup Runway listing with the M7.7 VAPT + compliance pack; IndiaAI compute application if needed; 1–2 SI-partner conversations; support/AMC process definition.
- Acceptance: GeM listing live; `docs/SUPPORT_PROCESS.md`; first AMC quote issued.
- DoD/Evidence: listing URL; support doc; AMC quote template.

**M9 gate:** ≥2 independent deployments via repeatable install; documented support process; pipeline ≥₹1 Cr.

---

## 5. Coverage & deferred register (v1.1 — review §5)

**Tech-debt register (ARCHITECTURE §6) → issue coverage (12/12, explicit):**

| Gap | Covered by |
|---|---|
| 1. No auth | M1.0–M1.4 |
| 2. No persistence | M1.0 contract + M4.1 |
| 3. TaskManager write-only | M4.2 |
| 4. macOS-only isolation | M2.1–M2.3 (+M2.5 for RHEL) |
| 5. Sandbox resource limits | M7.4 |
| 6. Whole-file JSON vector store | M6.1 (pgvector) |
| 7. Scanned PDF ingestion | M5.4 (+formats in M5.3) |
| 8. No structured logs | M6.4 |
| 9. Hardcoded air-gap pill | F.1 |
| 10. No unit tests/CI | M1.4 + M2.3 |
| 11. Constants-only config | M3.4 |
| 12. No queue/cancellation | M4.3 |

**Deferred — acknowledged, no issue, with trigger conditions (explicitly not forgotten):**

| Deferred item | Why deferred | Trigger to open an issue |
|---|---|---|
| SAML/OIDC SSO beyond LDAP | PSU first ask is LDAP/AD; SSO adds an identity-provider dependency | A pilot customer requires SSO in writing |
| Trusted timestamps (RFC 3161) for audit | Hash chain + local clock adequate for first audits; TSA adds external dependency | A buyer's audit spec demands them |
| Encryption-at-rest for workspace/DB | Threat model assumes physical control of the host; adds key-management burden | Customer security review requires it |
| Resume-from-step task retry | Retry-as-new-linked-task is simpler and audit-clean | Pilot users report repeated long-task failures |
| HA/failover, multi-node inference | Appliance is single-node by design (anti-goal) | A site needs >100 concurrent users |
| UI framework rewrite | Vanilla JS is fine until Phase 3 (anti-goal) | v2 fleet UI work |

## 6. Count summary (v1.1)

| | F | M1 | M2 | M3 | M4 | M5 | M6 | M7 | M8 | M9 | Total |
|---|---|---|---|---|---|---|---|---|---|---|---|
| Issues | 3 | 5 | 5 | 4 | 4 | 4 | 5 | 7 | 3 | 5 | **45** |
| P0 | 2 | 5 | 2 | 2 | 4 | 1 | 4 | 5 | 2 | 0 | **27** |

(v1.0: 43 issues / 26 P0 → v1.1: +M1.0, +M2.5; F.3 → P1; M4.4 → P0.) All 45 are independently testable and traceable to a documented gap. Still excluded by design: UI rewrite, speculative connectors, microservices, eval fine-tuning beyond the suite.

## 7. v1.1 revision log (external review, 2026-11-13 — all 14 findings applied)

| # | Finding | Resolution |
|---|---|---|
| 1 | F.3 misprioritized + artificial M1.1 dep | F.3 → P1; M1.1 depends on M1.0 only |
| 2 | M1/M4 circular persistence assumption | New **M1.0** data contract (schema, interfaces, migration ownership, drift test); both implement against it |
| 3 | M2.1 netns overstatement + Ollama connectivity | Topology decision explicit (Ollama **inside** the netns by default); IPv4/v6, interfaces, child-inheritance checks; residual-limitations doc; standing caveat retained |
| 4 | M2.4 (P2) vs M7 RHEL gate contradiction | Split: M2.4 = guide (P2); new **M2.5** = RHEL validation, explicit M7.7 dep + M7 gate item |
| 5 | M7 gate vs P1 controls (C12/C14) | M7 gate states C11–C14 all required regardless of within-milestone priority |
| 6 | M1.2 route classes + ownership ≠ isolation | Route classes enumerated (HTTP/WS/static/exception-list); isolation claim moved to M6.2, M1 only records the ownership key |
| 7 | 4-vs-5 demo discrepancy | Verified in code: **5 demos** (README stale); canonical inventory = `ws_smoke.py` DEMOS enumerated programmatically; README fixed in M3.1 |
| 8 | M3.3 missing M4.1 dep for DB backup | Dependency added |
| 9 | M4 retry undefined | M4.2 defines retryable classes, retry-as-new-linked-task, resume deferred |
| 10 | M5.3 "must improve" criterion | Replaced with structure-fidelity + messy-subset target + no-regression(±2%) + perf report; aggregate improvement reported, not required |
| 11 | M6.5 wording drift + BITS ≠ pilot | Plan's "accepted without edits" restored (charter defines "edit"); gate counts only external users; BITS labelled rehearsal |
| 12 | M7.3 incomplete audit deps | Deps = M4.1, M6.3, M6.4, M7.1, M7.2; audit-coverage checklist maps every event class → producer; tamper-evidence caveat stated |
| 13 | M7.4 silent fallback danger | Explicit tier model; production profile refuses subprocess tier for generated code; visible degraded warning; negative test |
| 14 | M7.7 risk-acceptance ambiguity | Criticals fixed, never accepted; highs only with written Lead risk-acceptance + remediation date; log kept |

Structural items (§4 of the review) applied throughout: CI tests the deployed boundary (M2.3) · absence-of-communication proof (M3.2) · M4.4 → P0 · M5.4 decoupled from M5.3 · M7.5 metrics defined · M8.1 discovery evidence artifact · M9.5 GeM sequencing · deferred register added (§5).

## 8. Next steps once approved

1. Commit `BACKLOG.md` v1.1 → push **together with** `4febc63` (M0 docs).
2. Create GitHub issues: labels `milestone-M1…M9` / `P0/P1/P2` / `backend` `security` `ai-rag` `devops` `qa` `lead`; F.1–F.3 as milestone-M0 issues.
3. Start parallel workstreams: **F.1+F.2+M1.0 first** (they unblock or protect everything else), then M1.1 (Backend), M2.1 (Security), M3.1 (DevOps), M5.1 (AI/RAG) concurrently.
4. Gates tracked by committed evidence, not by checkbox.
