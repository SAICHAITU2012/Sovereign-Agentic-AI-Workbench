# Sovereign Workbench — Prototype → Production Plan (v2.0)

**Date:** 2026-11-06 · **Repo state:** `main @ a71b5b1` (6 commits) · **Supersedes:** roadmap sections of `DEEP_ANALYSIS_REPORT.md` (2026-09-06); **v2.0 merges an external review** (2026-11-06) — adoption log in §12.

**One-line thesis:** the differentiator was never the software — every component exists free in open source. It is **provable sovereignty (verifiable no-egress, with committed evidence) + deliverable-shaped agents + India compliance packaging**, sold as a single appliance to organizations that *legally cannot* use cloud AI.

**Reframe adopted in v2.0:** this is not a feature-addition project — it is a product that must **progressively earn the trust of an enterprise customer**. Every maturity level below is *earned through evidence*, never declared. We do not call anything production-ready before its gate passes.

---

## 1. Where we stand today — exact status

### 1.1 What exists and works (verified in repo @ a71b5b1)

| Capability | Evidence |
|---|---|
| Agentic loop (plan → tool → observe → iterate) w/ self-healing code repair | `backend/app/agent/orchestrator.py` (673 lines), 5/5 demo flows pass |
| 4 local models via Ollama + capability router + TF-IDF fallback | `models/provider.py` (`NUM_CTX=8192`), `models/router.py` |
| RAG over local SOPs (732 chunks, JSON+numpy store) | `rag/store.py`, 19.7 ms retrieval |
| Sandboxed Python exec w/ repair loop, docx/xlsx/pptx deliverables, OCR/vision | `tools/local_tools.py` (383 lines) |
| **Kernel-enforced air-gap (macOS Seatbelt), whole process tree** + adversarial escape battery (plain socket / raw `_socket` / child curl / ctypes → all EPERM) + committed evidence report | `scripts/airgap/`, `evidence/airgap_report_20261101T125329Z.md` — ALL PASSED |
| Upload path sanitization, pinned deps, egress guard w/ IP-literal fast path | commit `bfefeb9` |
| Benchmarks: 66 tok/s gen, 57.5 s full doc flow, 92% of wall time = LLM | `PERFORMANCE_REPORT.md` |
| 2:48 demo video + script, viva prep, deep analysis docs | `SIH2026_*_Demo.mp4`, `DEMO_VIDEO_SCRIPT.md`, `VIVA_PREP.md` |

**Honest classification: a top-decile hackathon artifact ≈ v0.4 of a product.**

Two different achievements, deliberately kept separate:
1. ✅ **Demonstrated:** the core concept works — agent loop, local models, deliverables, isolation evidence.
2. ⛔ **Not yet demonstrated:** it can safely support multiple employees, protect organizational information, survive operational failures, and be maintained by an enterprise IT team. Everything below exists to convert (1) into (2).

### 1.2 Maturity ladder (each level earned by evidence, not declared)

| Level | Meaning | Gate to advance |
|---|---|---|
| **v0.4** | Working technical prototype | — (current) |
| **v0.5** | Hardened, reproducible prototype | §3 Phase 0 checklist (10/10) |
| **v1 Alpha** | Usable by a controlled pilot team | 10–20 external users, ≥50 real tasks, ≥1 accepted deliverable/user/week |
| **v1 Production** | Security-reviewed, deployable enterprise appliance | VAPT zero criticals, escape battery green on Ubuntu + RHEL-class, compliance mapping delivered |
| **v2** | Repeatable multi-site product | ≥2 independent deployments, repeatable install, signed-update roll-out on site |

### 1.3 The production gap (ranked by pilot-killing severity)

| # | Gap | Current state | Why it kills a pilot |
|---|---|---|---|
| 1 | **No authentication / users** | single-tenant, localhost | No IT dept sanctions an unauthenticated tool |
| 2 | **No persistence** | in-memory sessions; restart = amnesia | Users lose work; no history, no audit |
| 3 | **Air-gap kernel enforcement is macOS-only** | Seatbelt profile; no Linux equivalent | Real deployments are Ubuntu/RHEL servers — the flagship feature can't ship on them yet |
| 4 | **No packaging** | pip + manual Ollama + Tesseract | On-prem buyers cannot debug pip; install must be one command |
| 5 | **JSON+numpy vector store** | fine at 732 chunks, degrades ~10k+ | KB growth is the lock-in moat; it must scale |
| 6 | **No evals** | none | Can't prove (or improve) retrieval/answer quality; changes are vibes |
| 7 | **No audit/observability** | egress events only | CERT-In requires 180-day in-India log retention |
| 8 | **Sandbox is one Python subprocess** | rlimits missing; no OS jail | Generated-code risk on multi-user machines |
| 9 | **No SSO/RBAC/quotas, no TLS-on-LAN story** | — | Every enterprise checklist item |
| 10 | **TaskManager dead code, no concurrency control on GPU** | `orchestrator.py:663` unused; Ollama serializes | breaks at ~5–15 concurrent users |

### 1.4 The market window is open *right now* (researched Nov 2026, sources §13)

- **DPDP Rules 2025** (notified 14 Nov 2025) phase in over 12–18 months → **main operational deadline ≈ May 2027**. SDF duties: 72-h breach reporting, DPIAs, audits, algorithmic due diligence. Buyers are shopping for compliant infrastructure *this year*.
- **CERT-In Directions 2022 fully in force in 2026**: 6-hr incident reporting, **180-day rolling log retention stored in India**, NTP sync → audit-log retention/export is a *feature*, not overhead.
- **IndiaAI Mission 2.0**: 38–45k GPUs empanelled, subsidized compute at ~₹65/hr, 20 sovereign models funded (EKA-1, Dhīr launched Feb 2026) → a student startup can legitimately apply for compute + acceleration.
- **Sarvam-30B (MoE, 2.4B active) / Sarvam-M 24B are Apache-2.0** → true offline use with no license server. *Open weights ≠ air-gap-legal; permissive license is what makes it legal.*
- **Qwen3.5-4B scores 79.9 on TAU2-Bench** (agent/tool-use); Qwen3.5-9B strongest at its size; Qwen3 & Granite 4 explicitly trained for tool-calling → candidates to *benchmark*, not auto-adopt (§5).
- **Open WebUI's 2025–26 CVE record** (CVE-2025-64496, CVE-2026-70491, CVE-2026-87996 — access control, SSRF/DNS-rebinding) → this is *internal objection-handling knowledge*, not public marketing (§4): we lead with **our own independently verified evidence**, never with competitor attacks.
- **Procurement door for startups**: DPIIT recognition + **GeM Startup Runway** = sell to gov/PSUs with no prior-turnover criteria; PPP-MII Order 2017 (rev. 2022) purchase preference; EMD exemptions.

---

## 2. Product definition — and the three deployment modes (v2.0 correction)

An **appliance**, not a SaaS, not a library. And we never conflate three things the market treats differently:

| Mode | Definition | What the product claims |
|---|---|---|
| **On-premise** | Runs inside customer infrastructure | Baseline: always |
| **Offline-capable** | Operates with no internet connectivity | Documented + tested install/update path |
| **Air-gapped** | Physically/logically separated environment with controlled transfer mechanisms | Kernel-enforced no-egress + re-runnable escape battery + signed evidence, on Linux *and* macOS |

Every customer-facing document (deck, whitepaper, tender response) must state which mode is being claimed. The brand word is **verifiable isolation**, not a blanket "air-gapped" — the claim must always match the evidence attached to the release.

```
┌─────────────────────────────────────────────────────────────┐
│  SOVEREIGN WORKBENCH APPLIANCE (one docker-compose stack)   │
│                                                             │
│  UI (LAN, TLS) ── auth/SSO ── per-user workspaces           │
│        │                                                    │
│  Orchestrator ── Model Router (vLLM/Ollama, multi-model)    │
│        │            reasoning · coding · vision · embedding │
│  Tool Layer:  sandbox (container, no-network, seccomp)      │
│        │        office docs · OCR · vision · connectors     │
│  RAG: pgvector (Postgres) + layout-aware ingestion          │
│  Data: Postgres (users, tasks, audit) + object store        │
│  Trust: egress guard + netns/no-network + signed evidence   │
│  Ops: metrics · structured logs (180-day) · update bundles  │
└─────────────────────────────────────────────────────────────┘
```

Three pillars to harden each phase:
1. **Provable sovereignty** — every release ships a re-runnable escape battery + signed evidence pack, now on Linux too.
2. **Deliverable-shaped agents** — real industrial workflows with **human sign-off** (review → approve/reject → immutable record). An AI-generated document never automatically becomes an approved organizational record.
3. **Enterprise trust & governance** — access control, auditability, precise compliance *mapping*, deployment support.

---

## 3. The plan — 4 phases (business rhythm) executed as 9 milestones (engineering order)

> Effort units: 1 unit ≈ one member-month of focused student work. Total to first paid pilot ≈ **20–24 units over ~9 months** — retained as an **ambitious planning hypothesis, not a deadline**: procurement, security reviews, and academic calendars can slip it; the gates below are slip-tolerant (a slipped phase slips revenue, not the architecture).

| Milestone | What | Phase |
|---|---|---|
| **M0** Product & architecture freeze (docs sprint) | 0 |
| **M1** Security & access foundation (auth) | 0 |
| **M2** Provable Linux sovereignty (netns + escape suite) | 0 |
| **M3** Deployable appliance (Docker + offline install) | 0–1 |
| **M4** Reliable backend (SQLite, tasks, GPU queue) | 0 |
| **M5** Measurable AI/RAG quality (eval framework) | 0–1 |
| **M6** Enterprise alpha (multi-user, approvals, pilot) | 1 |
| **M7** Production hardening (RBAC/SSO, audit, sandbox, VAPT) | 2 |
| **M8** First real customer deployment | 2 |
| **M9** Commercialisation & multi-site | 3 |

Milestones 0–6 → trustworthy alpha. 7–8 → credible production offering. 9 → repeatable business.

### Phase 0 — "Seal v0" (now → mid-Dec 2026) · ~6 units
*Goal: survive SIH Grand Finale + close the trivial gaps. No architecture changes.*

| Item | Owner-type | Done-when |
|---|---|---|
| **M0 (compressed — 2 days, not a milestone):** `ARCHITECTURE.md`, `SECURITY_MODEL.md`, `PRODUCT_REQUIREMENTS.md`, `CONTRIBUTING.md`, team ownership table (§10) | lead | every member can explain the security boundary; each subsystem has one accountable owner |
| Basic auth (bcrypt, session cookie, middleware on all routes; rate limiting, secure/HttpOnly/SameSite, expiry + logout; CSRF where cookie-based auth needs it; no secrets in logs) | backend-1 | `curl` without cookie → 401 everywhere; session tests pass |
| **M2** Linux air-gap: network-namespace wrapper for Ubuntu (`scripts/airgap/linux/`) + expanded escape suite (alt APIs, children, DNS, IPv4/v6, host-net) | air-gap | battery passes in clean Ubuntu VM; **documented caveat: a netns is not by itself a complete security boundary — assessed together with capabilities, filesystem, privileges, container config** |
| **M3** Dockerfile + `docker-compose.yml` (app + Ollama sidecar) + offline-image export + `deployment/` tree with install/health-check/backup scripts + `INSTALLATION.md`, `TROUBLESHOOTING.md` | packaging | `docker load` + `up` on clean VM, 4 demos pass, restart preserves data, **zero manual pip on customer machine** |
| **M4** SQLite task/session persistence; resurrect TaskManager → `GET /api/tasks`; GPU queue (asyncio semaphore); timeouts + cancellation | backend-2 | restart preserves history; 3 concurrent tasks queue; failures identifiable/retryable |
| **M5** Eval harness v0: 50–100 Q/A pairs over the demo KB; metrics: Hit@5, MRR, groundedness, citation accuracy, latency, failure rate (Ragas/DeepEval, offline) | RAG | `scripts/eval_retrieval.py` prints the suite; baseline numbers committed under `evidence/` |
| Repo hygiene: delete dead code, split `main.py` routers, choose `LICENSE` (SIH repo stays public as reference implementation; product core goes private later) | lead | clean `ruff` + tests green |

**v0.5.0 release checklist (the gate):**
☐ Architecture/scope frozen (M0) ☐ Auth + protected routes ☐ Linux isolation tested ☐ Docker Compose up ☐ Offline image export/install ☐ SQLite persistence ☐ Task manager + GPU queue ☐ Retrieval eval harness ☐ All demo flows passing in Ubuntu container ☐ README + security evidence + release docs updated

### Phase 1 — v1 Alpha "single-team edition" (Jan → Mar 2027) · ~8 units
*Goal: 10–20 real pilot users inside one friendly org (MRPL engineer group via SIH channel, or a BITS department as dress rehearsal).*

| Item | Notes |
|---|---|
| Multi-user: admin-created accounts, individual workspaces, task history, user/admin roles, usage quotas | Postgres + SQLModel; one compose service |
| **pgvector** replaces JSON store (keep TF-IDF fallback); migration script for old KBs | one Postgres does users+tasks+audit+vectors: appliance stays single-stack |
| **M5 continued:** model candidates *benchmarked against current models* via the eval suite before any swap (Qwen3.5:4b/9b, bge-m3 embeddings, qwen2.5-vl vision) — upgrade only on measurable win without latency/security regression | registry entries only; the router makes swaps cheap, evals make them safe |
| Layout-aware ingestion: Docling (Apache-2.0, CPU, offline) for structure; Tesseract fallback; table/heading preservation; metadata + version tracking; **test on real industrial documents, not just demo files** | retrieval quality is the #1 enterprise RAG failure mode |
| Human-in-the-loop deliverables: draft → diff view → approve/request-changes → signed record; approval history; download centre | this is what PSUs actually buy |
| Observability v1: structured JSON logs, request IDs, task timeline in UI; optional Langfuse container (self-hosted) | feeds CERT-In 180-day retention in Phase 2 |
| **Linux escape battery in CI** (GitHub Action runs it per push) + evidence report per release | evidence becomes automated, not ceremonial |
| Hit@5/MRR targets are **engineering baselines, not enterprise acceptance guarantees** — pilot user feedback is the acceptance test | honesty rule from v2.0 review |

**Gate:** 10 external users × 2 weeks, ≥50 real tasks, ≥1 deliverable accepted-without-edits per user per week; eval numbers published in `evidence/`.

### Phase 2 — v1 Production "pilot you can charge for" (Apr → Jul 2027) · ~8 units
*Goal: first paid pilot (₹2–10 L POC pricing at a refinery PSU / heavy industry site) — timed to land as the DPDP deadline (~May 2027) bites.*

| Item | Why it's the sale |
|---|---|
| RBAC + **LDAP/AD integration**, SSO where required, department-level permissions, TLS-on-LAN | IT security checklist |
| **Permission-aware RAG**: per-department KBs; permission checks enforced at **ingestion, retrieval, and document access** — never left to the LLM to respect | #1 enterprise RAG failure mode |
| **Audit & compliance pack**: structured logs, user activity, task history, approval records, security events, egress feed, admin export, 180-day retention + backup; **precise DPDP/CERT-In mapping document — not a blanket compliance claim** (on-prem ≠ automatically compliant; obligations depend on data, roles, deployment) | procurement paperwork pre-done |
| Guardrails: prompt-injection heuristics + classifier on tool outputs; PII redaction (Presidio) on ingestion | SDF "algorithmic due diligence" |
| Hardened sandbox on Linux: dedicated container, `--network=none`, read-only fs, seccomp, rlimits, no capabilities, execution timeouts, strict file boundaries | the multi-user risk item |
| **Signed offline update bundles** (tar + ed25519, verified apply) | air-gapped upgrade path — nobody else packages this |
| Security validation: threat model → OWASP ASVS L1 self-assessment → dependency scanning → external VAPT (student-friendly auditor acceptable) → remediate | zero unresolved criticals |
| Scale profile: vLLM on a single 24–48 GB GPU (batching for 20–100 users), same API | 10× concurrency, measured |

**Gate:** signed pilot contract/LOI; escape battery green on Ubuntu 22.04 & RHEL-class; zero critical VAPT findings; compliance mapping delivered to buyer.

### Phase 3 — v2 "site → fleet" (Aug → Dec 2027) · ongoing
*Goal: 2–3 paying sites, AMC revenue, procurement channel live.*

- Multi-site appliance fleet: tenant = site; customer-controlled fleet monitoring; **Ansible** deployment automation (Helm later only if a customer demands K8s).
- Connector framework — **built only for what actual pilot customers demand** (candidates: SAP PM, IBM Maximo, EDRMS, approved internal mail).
- Workflow template library per vertical (refinery → pharma QC → power) — each vertical is a 2-week packaging, not an R&D project.
- DPIIT → GeM Startup Runway listing live **after** the first customer validates (§4); SI-partner conversations; IndiaAI compute application if training/eval load demands.
- Team: recruit/retain 2 members full-time post-graduation — plan for the academic-calendar risk, don't ignore it.

**Gate:** ≥2 independent deployments, repeatable install, documented support process, AMC signed.

---

## 4. Go-to-market — four parallel tracks (v2.0: discovery starts *now*, not after the build)

| Track | Starts | Content |
|---|---|---|
| **A — Product engineering** | now | the milestones above (majority share of team attention) |
| **B — Customer discovery** | **now** | interview 2–3 MRPL/plant engineers *this month*: actual workflows, sensitive-data boundaries, security restrictions, willingness to pilot. You should not spend nine months building before learning whether the target organization wants it |
| **C — Security & compliance** | now (docs) | threat model, SECURITY_MODEL.md, compliance mapping drafts, VAPT in Phase 2 |
| **D — Business & institutional** | now (forms) | DPIIT recognition (~1 hr, free) + Startup India; SIH/MRPL relationship; IndiaAI compute when needed; SI partnerships in Phase 3 |

**MRPL approach (M8 prep, starts Track B):** one specific department → one document-heavy workflow → interview users → identify a non-sensitive test dataset → demonstrate one complete workflow → agree measurable pilot acceptance criteria in writing → pilot agreement → deploy → iterate → present results. **Do not assume MRPL automatically becomes a customer — the SIH connection is an introduction, not a sale.**

**First workflows to offer (in order):** maintenance/inspection report summarization → SOP knowledge assistant (grounded Q&A with citations) → HSE documentation drafting (human-reviewed). Build nothing else until one of these is accepted.

**Positioning sentence (v2.0 — no competitor attacks, no blanket claims):**
*"Private AI. Verifiable isolation. Enterprise workflows. An offline-capable, on-premise agentic AI appliance for sensitive organizations — with independently verifiable network-isolation evidence, human-approved deliverables, and a precise compliance mapping (DPDP/CERT-In) for your deployment."*

**Pricing (anchor):** POC ₹2–10 L · site license ₹15–40 L + 15–20% AMC · price per site + documents processed, **never per seat** (usage is episodic: approvals, inspections).

**Segments in order:** refinery PSUs (exact fit) → private heavy industry (faster sale) → defence/strategic (highest value, longest cycle) → **never** SMBs/developers.

---

## 5. Model strategy — benchmark first, swap only on evidence

| Tier | Hardware | Candidates (all open-weight, offline-legal) |
|---|---|---|
| Laptop/demo (16 GB Mac) | M4 unified memory | qwen3.5:4b (reason+tools) · qwen2.5-coder:7b (code) · qwen2.5-vl:3b/7b (vision) · bge-m3 (embed) |
| Site server (RTX 4090 24 GB) | vLLM | qwen3.5:9b/14b · qwen3-coder:30b-A3B (MoE) · qwen2.5-vl:7b · bge-m3 |
| High / Indic tier (48–80 GB, or IndiaAI compute @ ₹65/hr) | vLLM | Sarvam-30B (MoE, 2.4B active, Apache-2.0) for Indic reasoning; Sarvam-M 24B fallback |

**Decision rule (v2.0):** candidates are *evaluated* against incumbent models on the §3 eval suite (quality, latency, license, hardware fit, offline compatibility) before any registry change. Availability and benchmark claims must be re-verified at selection time — published numbers age fast. Keep the `MODEL_REGISTRY` pattern: every model change stays a config entry.

Vision is evaluated as its own category (OCR vs document understanding vs VQA), not lumped with reasoning.

## 6. Compliance matrix — mapping, not claims (v2.0)

| Requirement | Feature in product | Phase |
|---|---|---|
| DPDP Act/Rules: purpose limitation, breach reporting, SDF duties | 72-h breach-report runbook template; audit export; DPIA support doc | 2 |
| CERT-In: 180-day in-India logs, 6-hr reporting | immutable audit log + retention + export; incident runbook | 2 |
| CII/NCIIPC posture (defence/strategic later) | no-egress evidence pack, physical air-gap guide, signed updates | 2–3 |
| STQC testing (gov buyers) | ASVS self-assessment + VAPT report first; STQC submission when a tender demands | 3 |

**Rule:** every compliance sentence in customer documents names the specific control and its evidence artifact. "DPDP-ready" as a blanket claim is banned in our own material.

## 7. Anti-goals

1. **No Kubernetes/microservices before multi-site.** The single docker-compose appliance is a *selling point* for this market.
2. **No cloud-hosted SaaS version.** It contradicts the brand and creates DPDP surface for zero upside.
3. **No SMB/developer self-serve.** Free alternatives own it; you cannot win on price against free.
4. **No model-chasing.** Eval-gated swaps only (§5).
5. **No UI rewrite.** Vanilla JS is fine until Phase 3.
6. **No premature claims.** Never say "production-ready", "fully air-gapped", or "DPDP-compliant" without the matching evidence artifact (v2.0).
7. **No speculative connectors/features.** Build only what the first pilot requires (v2.0).

## 8. Top risks

| Risk | Mitigation |
|---|---|
| Student time (exams, placements — all 6 of you) | phase gates sized in units; a slipped phase slips revenue, not the architecture. Recruit 1–2 juniors by Phase 2. |
| "Why not free Open WebUI/Dify?" | §1.4 as internal objection-handling; publicly we lead with our own verified evidence + compliance pack |
| Procurement cycles (6–18 months) | Track B discovery starts now; LOI conversations in Phase 1 |
| **Isolation ≠ security**: netns/Seatbelt block egress but identity, authorization, sandboxing, secrets, backups, supply-chain and ops controls all matter separately | SECURITY_MODEL.md (M0) enumerates the full boundary; escape battery is one layer of the evidence, not the whole story |
| Hardware gap (1.5B demo vs 9B+ production quality) | eval harness quantifies it; vLLM profile + IndiaAI compute covers it |
| Single-leader dependency (you) | ownership table (§10): every subsystem has docs, tests, and a second maintainer. The lead must not become the implementer of every hard subsystem |

## 9. First 14 days — do exactly this

1. **D1–2:** DPIIT recognition application (leader; ~1 hr) + decide `LICENSE` + **schedule the first 2–3 customer-discovery interviews (Track B)**.
2. **D3–4:** M0 doc sprint: `ARCHITECTURE.md`, `SECURITY_MODEL.md`, ownership table.
3. **D5–7:** auth skeleton (bcrypt + cookie + middleware + rate limiting + session tests); every route 401s without login.
4. **D8–10:** Ubuntu VM → `ip netns` wrapper → expanded escape battery → first Linux evidence file in `evidence/`.
5. **D11–12:** Dockerfile + compose (app + Ollama) → 4 demos pass in container; offline export script.
6. **D13:** SQLite persistence for tasks/sessions; eval harness v0 (50 questions, Hit@5 + MRR).
7. **D14:** commit, tag `v0.5.0` if checklist is green, update README with Linux evidence screenshot; SIH portal submission if the SIH email has arrived.

Execution order if time is short: **freeze → auth → Linux isolation → containerize → persistence → evals → validate in new environment → tag.** Linux isolation and auth are the two most important early priorities.

## 10. Team ownership (6 members, subsystems — not job titles)

| Role | Primary responsibility |
|---|---|
| Technical lead (you) | architecture, integration, releases, technical decisions |
| Backend engineer | auth, APIs, database, task manager |
| Security engineer | Linux isolation, sandbox, security testing |
| AI/RAG engineer | models, ingestion, retrieval, evaluations |
| DevOps engineer | Docker, offline deployment, monitoring |
| Product/QA engineer | UI, workflow validation, testing, documentation |

Every subsystem needs documentation, tests, and a second person capable of maintaining it.

## 11. Evidence scorecard (how progress is measured — not commits, not LOC)

| Area | Measurement |
|---|---|
| Security | auth test pass, isolation test pass, unresolved vulnerabilities |
| Deployment | successful clean-machine installs |
| Reliability | task success rate, restart recovery |
| AI quality | Hit@5/MRR, groundedness, citation accuracy |
| Performance | latency, throughput, concurrency |
| Usability | real-user task completion |
| Business | discovery interviews → pilots → customer acceptance |
| Operations | backup recovery, update/rollback success |

Each milestone gets: owner · scope · implementation · automated tests · evidence · documentation · a formal acceptance decision. **If a milestone fails its criteria, fix it before building on top of it.**

## 12. v2.0 adoption log (external review, 2026-11-06)

**Adopted:** trust-earned maturity ladder (§1.2); three deployment modes (§2); compliance mapping-not-claims (§6, §7.6); benchmark-before-model-swap (§5); broader eval suite (§3); customer discovery starts immediately (§4); own-evidence marketing discipline, no CVE-based attacks (§1.4, §4); connectors only on demand (§7.7); team ownership table (§10); evidence scorecard (§11); v0.5.0 release checklist (§3); 9-month timeline demoted to hypothesis; netns-is-not-a-boundary caveat (§8).
**Already in v1.0 (review re-derived them):** SQLite→Postgres sequencing; no-K8s appliance; per-release evidence; human sign-off; permission checks at all three layers; one-customer-before-multi-site.
**Nuanced, not adopted verbatim:** M0 kept but compressed to a 2-day doc sprint (a full "architecture freeze" milestone is heavyweight for 6 students); the market-window facts (DPDP May 2027, IndiaAI) retained — they are sales tailwinds, not decoration; dated phase windows kept as targets with slip-tolerant gates.

## 13. Sources (researched 2026-11-06)

- DPDP Rules 2025 phased timeline & SDF duties — MeitY notification 14 Nov 2025 (dpdpa.com/DPDP_Rules_2025_English_only.pdf; PIB docs Nov 2025)
- CERT-In Directions under Sec 70B(6) IT Act, 28 Apr 2022 — cert-in.org.in/PDF/CERT-In_Directions_70B_28.04.2022.pdf (confirmed in force Sep–Oct 2026)
- IndiaAI Mission 2.0, GPU empanelment, sovereign models (EKA-1, Dhīr), ₹65/hr compute — IndiaAI Impact Summit Feb 2026 coverage; Oct 2026 policy reporting
- Sarvam-M 24B / Sarvam-30B MoE Apache-2.0 open weights — HuggingFace `sarvamai/sarvam-m`; Sarvam 2026 releases
- Qwen3.5-4B TAU2-Bench 79.9; Qwen3.5-9B agentic lead; Qwen3/Granite-4 tool-calling — HF blog "open-source LLMs to run locally"; 2026 Ollama/agentic benchmark guides
- Open WebUI CVE-2025-64496, CVE-2026-70491, CVE-2026-87996; "Exposed AI Infrastructure: Self-Hosted Services Under Attack" (May 2026) — NVD/Open WebUI security advisories
- GeM Startup Runway; PPP-MII Order 2017 (rev 2022) purchase preference; EMD exemptions — startupindia.gov.in/public_procurement; GeM portal
- pgvector vs Qdrant vs LanceDB for on-prem/air-gapped RAG (2026 benchmarks) — iotdigitaltwinplm.com (Aug 2026), VDF.AI (Oct 2026)
- Prior internal anchors: `DEEP_ANALYSIS_REPORT.md` §6–§14 (market sizing, personas, pricing), `PERFORMANCE_REPORT.md`
