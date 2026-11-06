# SECURITY_MODEL — Sovereign Workbench (current state, honest)

**Written against code** (`main @ a71b5b1`), 2026-11-06. Companion to `ARCHITECTURE.md` (component facts) — this document covers **assets, boundaries, threats, controls, and what we are allowed to claim**.

Status labels: ✅ implemented & verified · 🟡 partial (gap stated) · ⛔ absent · 🔜 proposed (milestone in `PRODUCTION_PLAN.md`).

---

## 1. The claim policy (read this before any customer conversation)

The product sells **verifiable isolation**. Therefore:

1. **Three deployment modes are distinct and always named** — on-premise (runs in customer infra), offline-capable (operates without internet), air-gapped (physically/logically separated, controlled transfer). Never blur them.
2. **Labels are not proof.** `SOVEREIGN_AIRGAP_KERNEL=seatbelt` is a *label*; the proof is the escape-battery probe results. Every UI/docs statement must be backed by a named evidence artifact.
3. **Never claim** "unhackable", "guaranteed air-gap", "DPDP-compliant" (blanket), or "production-ready" without the matching gate passed. Approved phrasing: *"kernel-enforced network isolation, verified by a re-runnable adversarial battery; evidence attached to release X."*
4. Every release ships its **own re-run evidence pack** (report + environment info). Old evidence describes old code.

## 2. Assets to protect

| Asset | Where | Sensitivity |
|---|---|---|
| Confidential documents (uploads, KB: SOPs, manuals, correspondence) | `workspace/uploads/`, `workspace/kb/` | **Core** — the reason the product exists |
| Deliverables (drafts, computed artifacts) | `workspace/outputs/` | High |
| Generated code + sandbox run dirs | `workspace/sandbox/run_<id>/` | Medium (may embed document excerpts) |
| Vector store (embedded KB text) | `workspace/vector_store.json` | High (whole-KB text is recoverable from it) |
| Egress/audit events | in-memory `deque` (500) | High for trust; ⛔ not persisted |
| Model weights | Ollama store (system) | Low (open weights) |
| Credentials | — | ⛔ none exist anywhere in the codebase (verified: no API keys, no secrets files; Ollama is local and unauthenticated) |

## 3. Trust boundaries (as-built)

```
┌──────────────────────────────────────────────────────────────┐
│ HOST (macOS today; Linux = target)                           │
│  ┌─────────────────────────────┐   ┌───────────────────────┐ │
│  │ uvicorn process             │   │ Ollama 127.0.0.1:11434│ │
│  │  [egress monkey-patch]      │──▶│ (no auth, loopback)   │ │
│  │  orchestrator · tools · RAG │   └───────────────────────┘ │
│  │        │ subprocess.run -I  │                             │
│  │  ┌───────────────────┐      │                             │
│  │  │ sandbox child     │      │   [ Seatbelt wraps ALL of   │ │
│  │  │ (prelude blocks   │      │     it — macOS only — when  │ │
│  │  │  socket.socket)   │      │     run_airgapped.sh used ] │ │
│  │  └───────────────────┘      │                             │
│  └─────────────────────────────┘                             │
│   ▲ loopback :8000                                           │
│   browser (same machine)                                     │
└──────────────────────────────────────────────────────────────┘
        ⇅ the boundary that matters: HOST ↔ external network
```

Boundaries B1–B5:
- **B1 Browser → backend** (loopback HTTP/WS). ⛔ No auth, no CSRF, no rate limit. Anyone/something on the machine can drive every API.
- **B2 Backend → Ollama** (loopback HTTP). Unauthenticated by Ollama's design; acceptable inside B1's host.
- **B3 Backend → sandbox child** (`python -I`, minimal env, cwd=run dir, 30 s). Python-level prelude blocks `socket.socket` only.
- **B4 Sandbox → host** (filesystem/syscalls). ⛔ No OS jail, no rlimits; the child runs as the same user with a scrubbed env. Kernel layer (when active) constrains *network* only.
- **B5 Host → external network** — the sovereignty boundary. Two controls, below.

## 4. Control inventory

| # | Control | Layer | Status | Verified by |
|---|---|---|---|---|
| C1 | Egress guard: `socket.socket.connect` monkey-patch, loopback-only, raises + logs | app (in-proc) | ✅ with documented bypass class (`_socket`/ctypes/children) | selftest endpoint; escape probe 1 |
| C2 | Kernel policy: Seatbelt `(deny network*)` + loopback/AF_UNIX allows, whole process tree | OS (macOS only) | ✅ macOS / ⛔ Linux | escape probes 2–4 EPERM; `verify_airgap.py` T1–T4 |
| C3 | Sandbox prelude: `socket.socket` subclass raising `ConnectionError`; cwd/HOME confined to run dir | app | ✅ Python-level only (see C1 limits) | probe 1 verdict "app: sandbox prelude" |
| C4 | Sandbox runtime hygiene: `python -I` (no user site), minimal env, fresh `run_<id>` cwd, 30 s timeout | app | ✅ | battery positive control; demo flows |
| C5 | Upload filename sanitization `_safe_filename`: basename flatten, dotfiles/empty rejected | app | ✅ | verified over raw multipart (commit `bfefeb9`) |
| C6 | Workspace path containment `_safe_path` (tools) + download containment (resolve + parents check) | app | ✅ | code review; not adversarially fuzzed 🟡 |
| C7 | Egress event log (attempts, verdicts) | app | 🟡 in-memory only, 500 events, no export/persistence | `/api/network` |
| C8 | Dependency pinning (11 exact versions, no cloud SDKs) | supply chain | ✅ | `requirements.txt` |
| C9 | Evidence battery + committed signed-off report per verification run | verification | ✅ manual / 🔜 CI-automated (M2) | `evidence/airgap_report_*.md/.json` |
| C10 | Authentication / sessions / authorization | — | ⛔ **absent** | — |
| C11 | CPU/memory rlimits, OS jail for sandbox | — | ⛔ absent | — |
| C12 | Prompt-injection defense / output classification / PII redaction | — | ⛔ absent | — |
| C13 | Audit log (immutable, 180-day, exportable) | — | ⛔ absent (C7 is a UI feed, not audit) | — |
| C14 | Signed offline update bundles | — | ⛔ absent | — |

## 5. Threat model

| ID | Threat | Vector | Current control | Status |
|---|---|---|---|---|
| T1 | Exfiltration via **generated code** (the primary adversarial case) | `socket`, raw `_socket`, child `curl`, `ctypes` | C3 stops probe 1; C1 stops Python-API use; **C2 (kernel) is the only control that stops all four** | ✅ macOS+kernel / ⛔ Linux until M2 |
| T2 | Exfiltration via **backend process compromise** (SSRF-style, malicious doc triggers a request) | any code path in uvicorn | C1 guards Python sockets in-proc; C2 kernel | 🟡 (same layering as T1) |
| T3 | **Unauthorized use** of the workbench (local multi-user future) | open API on :8000 | none — C10 absent. Mitigated today only by localhost binding | ⛔ → M1 (highest priority) |
| T4 | **Path traversal** on upload | `../../.zprofile`, absolute paths, dotfiles | C5 | ✅ verified |
| T5 | Workspace escape via **download/tool paths** | crafted `path` params | C6 (`resolve` + containment) | ✅ code-verified; fuzz-pending |
| T6 | **Resource exhaustion** by generated code | fork bombs, memory hogs, infinite loops | 30 s wall-clock only; ⛔ no rlimits → kernel CPU/mem unlimited | ⛔ → M7 |
| T7 | **Prompt injection** via document content (malicious KB doc/upload steers the agent to exfil or destructive tool calls) | ingested text → system/observation prompts | tools are loopback-only + workspace-contained (limits blast radius); ⛔ no classifier, no output guard | ⛔ → M7 guardrails |
| T8 | **DNS leak** under Seatbelt | hostname resolution via mDNSResponder (AF_UNIX allowed) | documented limitation; app uses 127.0.0.1 literals exclusively; strict mode adds PF/Wi-Fi-off | 🟡 honest limitation, M2 must test DNS on Linux netns |
| T9 | **Supply chain** (pypdfium2/pypdf native parsing of hostile PDFs; pip compromise) | crafted documents, dependency installs | pinned versions; 🔜 vendor wheels for air-gap installs; 🔜 SBOM + hash pinning (M3/M7) | 🟡 |
| T10 | **Audit integrity / incident response** (CERT-In 180-day logs, 6-hr reporting) | — | ⛔ C7 in-memory only | ⛔ → M7 |
| T11 | **Malicious update** (air-gapped upgrade path) | tampered bundle | ⛔ no update mechanism exists → M7 signed bundles | ⛔ |
| T12 | Local attacker on the same host (reads workspace, hits API) | filesystem/API access | single-user premise; ⛔ no auth, no encryption-at-rest | ⛔ → M1/M7 (document single-user assumption until M1) |

**Honest summary:** against its *primary advertised threat* (T1, generated-code exfiltration) the system is verified-strong **on macOS under the kernel launcher** and weak elsewhere. Against *conventional enterprise threats* (T3, T6, T7, T10–T12) it is a prototype. Both statements are true simultaneously, and this document exists so neither gets overstated.

## 6. Deployment-mode honesty matrix

| Claim | Allowed today? | Evidence artifact |
|---|---|---|
| "On-premise, loopback-only, zero cloud APIs in codebase" | ✅ yes | code audit (`DEEP_ANALYSIS_REPORT.md` §5), config literal `127.0.0.1` |
| "Offline-capable install" | 🟡 dev-only (needs Tesseract + Ollama preinstalled; pip not vendorable yet) | — → M3 makes it ✅ |
| "Air-gapped: kernel-enforced no-egress, adversarially verified" | ✅ **macOS only**, with launcher | `evidence/airgap_report_20261101T125329Z.*` |
| Same claim on Linux (the deployment OS) | ⛔ not yet — never claim before M2 evidence exists | pending |
| "DPDP-ready" | ⛔ never as a blanket claim; only "compliance mapping available" after M7 | pending |

## 7. Proposed controls → milestones (summary)

| Milestone | Security deltas |
|---|---|
| **M1** | Auth (bcrypt + secure cookies + rate limit + expiry/revocation), authz skeleton, security tests for all routes; fix T3/T12 partially |
| **M2** | Linux netns isolation + expanded battery (DNS, IPv6, host-net, children); CI-automated evidence; DNS-leak test; Sec profile review incl. `(allow default)` scope |
| **M3** | Container deployment (reduces host-blast-radius), vendored wheels, SBOM, config-without-secrets-in-image |
| **M4** | Persisted task/egress history (basis for audit), restart-safe state |
| **M7** | Containerized sandbox (no-network, read-only fs, seccomp, rlimits, no-caps) → T6; guardrails/PII → T7; immutable audit + retention → T10; signed update bundles → T11; VAPT closure of T5 fuzz + web checks |

## 8. Verification & evidence (how to reproduce)

```bash
# 1. start under kernel policy (macOS)
./scripts/run_airgapped.sh 8000
# 2. run the 6-check auditor — exit 0 required
python3 scripts/airgap/verify_airgap.py
# 3. live UI proof: "Air-gap self-test" button + sandbox_escape_test endpoint
# 4. evidence lands in evidence/ — commit it with the release tag
```

Artifacts: `evidence/airgap_report_20261101T125329Z.md` + `.json` (ALL PASSED, 2026-11-01, includes real inference under policy). Probe design notes: verdicts derive from exfil markers, never exit codes; positive control proves the sandbox still performs local work while everything external fails.

## 9. Ownership & review cadence

- **Security engineer** owns this document + the air-gap/sandbox code; technical lead reviews.
- Trigger-based review: any new tool, any new endpoint, any dependency change, any kernel-profile edit → re-run battery + update this file + fresh evidence.
- The escape battery must pass **on every supported OS** before any release claiming air-gap support for that OS.
- This document is part of M0's definition of done: every team member can state the five boundaries and the current honest posture from memory.
