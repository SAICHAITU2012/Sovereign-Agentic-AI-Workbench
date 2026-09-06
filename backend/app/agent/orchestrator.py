"""Agentic orchestrator.

Implements the behaviour the problem statement demands: the assistant
    plans multi-step work,
    decides which LOCAL tool to use at each step,
    observes the result,
    re-plans / repairs when something fails,
    and produces real deliverables instead of chat-only answers.

The loop is LLM-driven (the local model picks the next tool + arguments as
JSON) with deterministic scaffolding around it: if the small local model
emits malformed JSON or an unknown tool, the orchestrator falls back to the
plan's next step using heuristic tool mapping. This keeps a 1.5B-parameter
local model reliable while preserving genuine agentic behaviour.

Special-case self-healing for coding: when `run_python` exits non-zero, the
error is fed back to the coding model, which rewrites the code; the loop
re-executes until success or attempt budget exhausted (generate → run →
observe → fix → run again).
"""
import json
import re
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from ..config import AGENT_MAX_STEPS, UPLOADS_DIR, OUTPUTS_DIR, SANDBOX_DIR
from ..models.provider import gateway, extract_json
from ..models.router import classify_task
from ..tools.local_tools import get_tools
from ..rag import store as rag_store

TOOLS = get_tools()

SYSTEM_PROMPT = """You are the reasoning core of a fully on-premise agentic AI workbench for \
confidential industrial work. You operate ONLY through local tools and local knowledge; \
nothing may leave this machine.

At each turn you receive: the overall task, the plan, and the observed results of actions \
taken so far. Choose exactly ONE next action.

Reply with ONLY a JSON object, no prose, in one of these forms:

{{"thought": "...", "tool": "<tool_name>", "args": {{<tool arguments>}}}}

when you want to run a tool, or

{{"thought": "...", "final": "<complete answer for the user>"}}

when the task is complete.

Available tools:
{tool_docs}

Rules:
- Use search_knowledge_base before answering questions about procedures, SOPs or manuals.
- For any calculation, use run_python and have the code print every intermediate step.
- For documents, first extract_pdf; if the PDF is scanned use ocr_image or analyze_image on its page images.
- Create real files (create_docx/create_xlsx/create_pptx/write_file) when the user needs a deliverable.
- Do not repeat an action that already succeeded. Move toward completion."""


@dataclass
class TaskContext:
    id: str
    task: str
    attachments: list[str]
    routing: dict = field(default_factory=dict)
    plan: list[str] = field(default_factory=list)
    actions: list[dict] = field(default_factory=list)
    deliverables: list[str] = field(default_factory=list)
    started_at: str = ""
    finished_at: str = ""
    answer: str = ""
    status: str = "running"


class Orchestrator:
    def __init__(self, emit):
        self.emit = emit

    # ------------------------------------------------------------- utils --
    def _event(self, etype: str, **data):
        self.emit({"type": etype, "ts": datetime.now(timezone.utc).isoformat(), **data})

    def _tool_docs(self) -> str:
        return "\n".join(
            f"- {t.name}: {t.description} args={json.dumps(t.schema.get('properties', {}))}"
            for t in TOOLS.values()
        )

    # ------------------------------------------------------------ entry ---
    def run(self, task: str, attachments: list[str] | None = None) -> TaskContext:
        ctx = TaskContext(
            id=uuid.uuid4().hex[:10],
            task=task,
            attachments=attachments or [],
            started_at=datetime.now(timezone.utc).isoformat(),
        )
        gateway.refresh()
        self._event("task_started", task_id=ctx.id, task=task, attachments=ctx.attachments)

        # 1. Route: classify the task and pick local models per capability.
        routing = classify_task(
            task, ctx.attachments,
            llm_classifier=self._llm_classify,
        )
        models = {
            cap: gateway.resolve(cap)
            for cap in ("reasoning", "coding", "vision", "embedding")
        }
        routing.models = {k: v for k, v in models.items() if v}
        ctx.routing = routing.to_dict()
        self._event("routing", task_id=ctx.id, **ctx.routing)

        # 2. Plan.
        ctx.plan = self._make_plan(task, ctx.attachments, routing.task_type)
        self._event("plan", task_id=ctx.id, steps=ctx.plan)

        # 3. Agentic loop.
        system = SYSTEM_PROMPT.format(tool_docs=self._tool_docs())
        steps_done = 0
        code_attempts = 0
        last_code = ""
        seen_calls: set = set()  # (tool, signature) already executed

        while steps_done < AGENT_MAX_STEPS:
            obs_summary = self._observations_block(ctx)
            user_turn = (
                f"TASK: {task}\n"
                f"ATTACHMENTS: {', '.join(ctx.attachments) or 'none'}\n"
                f"PLAN:\n" + "\n".join(f"  {i+1}. {s}" for i, s in enumerate(ctx.plan)) + "\n"
                f"ACTIONS TAKEN SO FAR:\n{obs_summary or '  (none yet)'}\n\n"
                "Choose the next action as JSON."
            )
            decision = None
            if gateway.online:
                try:
                    raw = gateway.generate_for("reasoning", user_turn, system=system,
                                               temperature=0.1, num_predict=350)
                    decision = extract_json(raw)
                except Exception as e:
                    self._event("agent_thought", task_id=ctx.id,
                                thought=f"(local LLM unavailable: {e}; using deterministic step)")

            tool_name, tool_args, thought, from_llm = self._normalize_decision(
                decision, self._done_sigs(ctx), ctx)
            if tool_name is None:
                break  # strategy controller says the task is complete

            if tool_name in TOOLS:
                # small local models often invent argument names — keep only
                # what the tool schema declares (plus common aliases)
                tool_args = self._conform_args(tool_name, tool_args, ctx)

            sig = (tool_name, str(sorted((k, str(v)[:60]) for k, v in tool_args.items())))
            if sig in seen_calls:
                # LLM repeated itself — let the strategy controller decide
                tool_name, tool_args = self._next_strategic_action(self._done_sigs(ctx), ctx)
                if tool_name is None:
                    break
                if tool_name in TOOLS:
                    tool_args = self._conform_args(tool_name, tool_args, ctx)
                sig = (tool_name, str(sorted((k, str(v)[:60]) for k, v in tool_args.items())))
                if sig in seen_calls:
                    break  # nothing new left to do
                thought, from_llm = "State controller: next useful local action given results so far.", False
                self._event("agent_thought", task_id=ctx.id, thought=thought,
                            source="deterministic-scaffold")
            else:
                self._event("agent_thought", task_id=ctx.id, thought=thought,
                            source="local-llm" if from_llm else "deterministic-scaffold")
            seen_calls.add(sig)
            # --- coding self-heal loop -------------------------------
            if tool_name == "run_python":
                generated_code = tool_args.get("code") or last_code \
                    or self._generate_code(task, obs_summary)
                attempt_cap = 3
                while code_attempts < attempt_cap:
                    code_attempts += 1
                    self._event("tool_call", task_id=ctx.id, tool="run_python",
                                args={"purpose": tool_args.get("purpose", ""),
                                      "attempt": code_attempts,
                                      "code": generated_code})
                    summary, result = TOOLS["run_python"].run(code=generated_code,
                                                              purpose=tool_args.get("purpose", ""))
                    ok = result.get("exit_code") == 0
                    self._event("tool_result", task_id=ctx.id, tool="run_python",
                                ok=ok, summary=summary, result=result)
                    ctx.actions.append({"tool": "run_python", "ok": ok, "_code": generated_code,
                                        "summary": summary, "result": result})
                    if ok:
                        generated_code = ""
                        break
                    # failure → ask the coding model to fix, then rerun
                    self._event("agent_thought", task_id=ctx.id,
                                thought="Execution failed — asking the local coding model to repair the code and re-running in the sandbox.",
                                source="self-heal")
                    fixed = self._fix_code(task, generated_code, result)
                    if fixed:
                        generated_code = fixed
                    else:
                        break
                last_code = generated_code or ""
                steps_done += 1
                continue

            # --- normal tool call ------------------------------------
            if tool_name not in TOOLS:
                self._event("agent_thought", task_id=ctx.id,
                            thought=f"Unknown tool '{tool_name}' — stopping.",
                            source="guard")
                break

            self._event("tool_call", task_id=ctx.id, tool=tool_name, args=tool_args)
            try:
                summary, result = TOOLS[tool_name].run(**tool_args)
                ok = True
            except Exception as e:
                summary, result, ok = f"Tool error: {e}", {"error": str(e)}, False
            self._event("tool_result", task_id=ctx.id, tool=tool_name,
                        ok=ok, summary=summary, result=result)
            ctx.actions.append({"tool": tool_name, "ok": ok,
                                "summary": summary, "result": result})

            # collect deliverables
            if isinstance(result, dict) and result.get("deliverable"):
                ctx.deliverables.append(result["deliverable"])

            steps_done += 1

            if tool_name == "finalize":
                break

        # 4. Final answer.
        ctx.answer = self._final_answer(task, ctx)
        ctx.status = "complete"
        ctx.finished_at = datetime.now(timezone.utc).isoformat()
        self._event("final", task_id=ctx.id, answer=ctx.answer,
                    deliverables=ctx.deliverables, actions=len(ctx.actions))
        return ctx

    # ------------------------------------------------------- components ---
    _ARG_ALIASES = {
        "path": ("path", "file", "file_path", "filepath", "input_file", "input_file_path",
                 "image", "image_path", "pdf", "document"),
        "code": ("code", "script", "python", "python_code", "source"),
        "content": ("content", "text", "body", "contents"),
        "filename": ("filename", "file_name", "output_file", "output_file_path", "name"),
        "title": ("title", "heading", "subject"),
        "data": ("data", "sheets", "payload", "rows"),
        "query": ("query", "question", "search", "search_query", "q"),
    }

    def _conform_args(self, tool_name: str, args: dict, ctx) -> dict:
        props = TOOLS[tool_name].schema.get("properties", {})
        conformed = {}
        for key, val in args.items():
            if key in props:
                conformed[key] = val
                continue
            for canon, aliases in self._ARG_ALIASES.items():
                if key in aliases and canon in props and canon not in conformed:
                    conformed[canon] = val
                    break
        # auto-fill attachment paths
        if "path" in props and not conformed.get("path") and ctx.attachments:
            conformed["path"] = ctx.attachments[0]
        if "query" in props and not conformed.get("query"):
            conformed["query"] = ctx.task
        if tool_name in ("create_docx", "create_xlsx", "create_pptx"):
            base = conformed.get("filename") or f"deliverable_{ctx.id}"
            if not str(base).endswith((".docx", ".xlsx", ".pptx")):
                base += {"create_docx": ".docx", "create_xlsx": ".xlsx",
                         "create_pptx": ".pptx"}[tool_name]
            conformed["filename"] = base
        if tool_name == "create_docx" and not conformed.get("title"):
            conformed["title"] = ctx.task[:120]
        if tool_name == "create_docx" and not conformed.get("content"):
            conformed["content"] = self._grounded_notes(ctx)
        if tool_name == "create_xlsx" and not conformed.get("data"):
            conformed["data"] = json.dumps({"Sheets": [{
                "name": "Summary",
                "headers": ["#", "Step", "Result"],
                "rows": [[i + 1, a["tool"], a["summary"][:200]]
                         for i, a in enumerate(ctx.actions)],
            }]})
        if tool_name == "create_pptx" and not conformed.get("data"):
            bullets = [a["summary"][:110] for a in ctx.actions][:6] or [ctx.task[:110]]
            conformed["data"] = json.dumps({"Slides": [
                {"title": "Task", "bullets": [ctx.task[:110]]},
                {"title": "Agent findings", "bullets": bullets},
            ]})
        return conformed

    def _llm_classify(self, task: str, labels: list[str]) -> str | None:
        try:
            raw = gateway.generate_for(
                "reasoning",
                f"Classify this work request into exactly one category {labels}.\n"
                f"Request: {task}\nReply with only the category name.",
                temperature=0.0, num_predict=20)
            raw = raw.strip().lower()
            for label in labels:
                if label in raw:
                    return label
        except Exception:
            pass
        return None

    def _make_plan(self, task: str, attachments: list[str], task_type: str) -> list[str]:
        if gateway.online:
            try:
                raw = gateway.generate_for(
                    "reasoning",
                    "Create a short numbered plan (max 6 steps) for this task using only these "
                    f"tools: {', '.join(TOOLS.keys())}.\n"
                    f"Task: {task}\nAttachments: {', '.join(attachments) or 'none'}\n"
                    "Reply ONLY as JSON: {\"steps\": [\"...\", ...]}",
                    temperature=0.1, num_predict=300)
                parsed = extract_json(raw)
                if parsed and isinstance(parsed.get("steps"), list) and parsed["steps"]:
                    steps = []
                    for s in parsed["steps"][:6]:
                        if isinstance(s, dict):
                            action = s.get("action") or s.get("tool") or next(iter(s), "step")
                            detail = ", ".join(
                                f"{k}={v}" for k, v in s.items()
                                if k not in ("action", "tool") and isinstance(v, (str, int)))
                            steps.append(f"{action} — {detail}" if detail else str(action))
                        else:
                            steps.append(str(s))
                    return steps
            except Exception:
                pass
        # Deterministic fallback plans per task type.
        has_pdf = any(a.lower().endswith(".pdf") for a in attachments)
        has_img = any(a.lower().endswith((".png", ".jpg", ".jpeg")) for a in attachments)
        if task_type == "document_analysis":
            plan = []
            if has_pdf:
                plan += ["Extract text and detect scanned pages from the PDF",
                         "OCR / vision-analyse any scanned pages"]
            plan += ["Search the local knowledge base for relevant SOPs and past reports",
                     "Draft the requested output grounded in the findings",
                     "Create the deliverable file in outputs/"]
            return plan
        if task_type == "coding":
            return ["Generate Python code for the requested calculation/task",
                    "Run the code in the sandbox and verify the output",
                    "Repair and re-run if the sandbox reports errors",
                    "Summarise results with calculation steps shown"]
        if task_type == "vision":
            return ["Analyse the image(s) with the local vision model",
                    "Search the local knowledge base for related standards",
                    "Write up findings and create the deliverable"]
        if task_type == "knowledge_qa":
            return ["Search the local knowledge base for the relevant sections",
                    "Read the best-matching document if needed",
                    "Answer strictly grounded in the retrieved text"]
        return ["Break the task down and gather what is needed",
                "Produce the answer or deliverable"]

    def _normalize_decision(self, decision, done, ctx):
        """Return (tool_name, args, thought, from_llm).

        The local LLM gets first pick each turn. If it emits malformed JSON,
        an unknown tool, or repeats an action that already succeeded, we fall
        back to a state-based strategy controller that inspects what has
        actually been done so far (not what the plan said) and picks the next
        sensible local tool for this task type.
        """
        if decision and isinstance(decision.get("tool"), str):
            tool_name = decision["tool"]
            args = decision.get("args") or {}
            if isinstance(args, str):
                try:
                    args = json.loads(args)
                except json.JSONDecodeError:
                    args = {}
            if tool_name in TOOLS:
                return tool_name, args, decision.get("thought", "Choosing next action."), True
            # "finalize" / unknown tool: only accept when the state controller
            # agrees there is no more useful work (guards premature completion).
            nxt, _nargs = self._next_strategic_action(done, ctx)
            if nxt is None:
                if tool_name == "finalize":
                    return "finalize", {}, decision.get("thought", "Task complete."), True
                return None, None, None, False
            thought = (
                f"(model wanted to finish, but {nxt} is still needed per the plan — "
                "continuing.)")
            return nxt, _nargs, thought, False
        tool_name, args = self._next_strategic_action(done, ctx)
        if tool_name is None:
            return None, None, None, False
        return tool_name, args, "State controller: next useful local action given results so far.", False

    # --- state-based strategy controller (deterministic scaffolding) ------
    @staticmethod
    def _res(a: dict) -> dict:
        r = a.get("result")
        return r if isinstance(r, dict) else {}

    def _done_sigs(self, ctx) -> set:
        out = set()
        for a in ctx.actions:
            r = self._res(a)
            ok = a.get("ok") and not (r.get("exit_code") not in (None, 0))
            if ok:
                out.add((a["tool"], (r.get("path"), a.get("path"), str(a.get("args"))[:80])))
        return out

    def _next_strategic_action(self, done, ctx):
        tt = ctx.routing.get("task_type", "general")
        tools_run = [a["tool"] for a in ctx.actions]
        # deliverables the user explicitly asked for ("create an Excel …", etc.)
        want = set()
        tl = ctx.task.lower()
        if re.search(r"\bexcel\b|\bxlsx\b|\bspreadsheet\b", tl):
            want.add("create_xlsx")
        if re.search(r"\bpowerpoint\b|\bpptx?\b|\bslides?\b|\bpresentation\b", tl):
            want.add("create_pptx")
        if re.search(r"\bword\b|\bdocx\b|\bapproval note\b|\bdocument\b", tl):
            want.add("create_docx")
        deliverable_done = any(t in ("create_docx", "create_xlsx", "create_pptx", "write_file")
                               for t in tools_run)
        pdf_done = any(t == "extract_pdf" for t in tools_run)
        pdf_scan = any(self._res(a).get("scanned") for a in ctx.actions if a["tool"] == "extract_pdf")
        page_imgs = next(
            (self._res(a).get("page_images") or []
             for a in ctx.actions if a["tool"] == "extract_pdf"), [])
        pages_done = [a for a in ctx.actions if a["tool"] in ("analyze_image", "ocr_image")]
        kb_done = any(t == "search_knowledge_base" for t in tools_run)
        has_pdf = any(a.lower().endswith(".pdf") for a in ctx.attachments)
        has_img = any(a.lower().endswith((".png", ".jpg", ".jpeg")) for a in ctx.attachments)

        def pending_deliverable():
            """Next explicitly-requested deliverable that hasn't been made."""
            for w in ("create_xlsx", "create_pptx", "create_docx"):
                if w in want and w not in tools_run:
                    if w == "create_xlsx":
                        return w, {"filename": f"summary_{ctx.id}.xlsx"}
                    if w == "create_pptx":
                        return w, {"filename": f"findings_{ctx.id}.pptx"}
                    return w, {"filename": f"deliverable_{ctx.id}.docx",
                               "title": "Deliverable",
                               "content": self._draft_note(ctx)}
            return None, None

        if tt == "document_analysis":
            if has_pdf and not pdf_done:
                return "extract_pdf", {"path": ctx.attachments[0]}
            if pdf_scan and page_imgs and len(pages_done) < min(2, len(page_imgs)):
                img = page_imgs[len(pages_done)]
                return "ocr_image", {"path": img}
            if not kb_done:
                return "search_knowledge_base", {"query": ctx.task}
            w_name, w_args = pending_deliverable()
            if w_name:
                return w_name, w_args
            if not deliverable_done:
                return "create_docx", {
                    "filename": f"approval_note_{ctx.id}.docx",
                    "title": "Approval Note",
                    "content": self._draft_note(ctx)}
            return None, None

        if tt == "vision":
            if has_img and not pages_done:
                return "analyze_image", {"path": ctx.attachments[0],
                                         "question": "Describe this engineering image in detail: equipment tags, line labels, instruments, and anything unusual."}
            if not kb_done:
                return "search_knowledge_base", {"query": ctx.task}
            w_name, w_args = pending_deliverable()
            if w_name:
                return w_name, w_args
            if not deliverable_done:
                return "create_docx", {
                    "filename": f"deliverable_{ctx.id}.docx",
                    "title": "Visual Analysis Findings",
                    "content": self._grounded_notes(ctx)}
            return None, None

        if tt == "knowledge_qa":
            if not kb_done:
                return "search_knowledge_base", {"query": ctx.task}
            w_name, w_args = pending_deliverable()
            if w_name:
                return w_name, w_args
            return None, None  # finalize — answer grounded in retrieved chunks

        if tt == "coding":
            if not tools_run:  # run_python path handles generation+self-heal
                return "run_python", {"purpose": ctx.task}
            if not deliverable_done:
                return "write_file", {"path": f"outputs/verified_code_{ctx.id}.py",
                                      "content": self._last_verified_code(ctx)}
            return None, None

        # general
        if not kb_done and ctx.attachments:
            return "search_knowledge_base", {"query": ctx.task}
        return None, None

    def _last_verified_code(self, ctx) -> str:
        for a in reversed(ctx.actions):
            r = a.get("result")
            if a["tool"] == "run_python" and isinstance(r, dict) and r.get("exit_code") == 0:
                return a.get("_code", "# see activity log")
        return "# see activity log"

    def _grounded_notes(self, ctx) -> str:
        lines = [f"## Task", ctx.task, ""]
        for a in ctx.actions:
            lines.append(f"## Finding — {a['tool']}")
            lines.append(a["summary"])
            r = a.get("result")
            if isinstance(r, dict):
                if r.get("hits"):
                    for h in r["hits"][:3]:
                        lines.append(f"- [{h['source']}] {h['text'][:400]}")
                elif r.get("text"):
                    lines.append(str(r["text"])[:2500])
                elif r.get("answer"):
                    lines.append(str(r["answer"])[:1200])
                elif r.get("stdout"):
                    lines.append(f"```\n{str(r['stdout'])[:1500]}\n```")
            lines.append("")
        return "\n".join(lines)

    def _draft_note(self, ctx) -> str:
        """Draft the deliverable with the local reasoning model, grounded in
        observations; falls back to the raw grounded notes if the model is
        unavailable."""
        evidence = self._observations_block(ctx)
        if gateway.online and ctx.actions:
            try:
                raw = gateway.generate_for(
                    "reasoning",
                    "Draft a structured approval note in markdown with '## ' section "
                    "headers, based ONLY on the tool observations below. Use sections "
                    "such as: Task, Key Findings, Applicable SOP / Acceptance Criteria, "
                    "Conditions Before Restart, Conclusion. Quote actual numbers and "
                    "cite the SOP file names from the observations.\n\n"
                    f"TASK: {ctx.task}\nOBSERVATIONS:\n{evidence}",
                    temperature=0.2, num_predict=900)
                if raw and len(raw) > 200:
                    return raw
            except Exception:
                pass
        return self._grounded_notes(ctx)

    def _generate_code(self, task: str, obs: str) -> str:
        if gateway.online:
            try:
                raw = gateway.generate_for(
                    "coding",
                    f"Write a complete, self-contained Python 3 script for this task.\n"
                    f"Task: {task}\n"
                    "Requirements: print every intermediate calculation step; print a clearly "
                    "marked final result line; no network access; no user input.\n"
                    "Reply ONLY with the code inside a single ```python block.",
                    temperature=0.1, num_predict=700)
                m = re.search(r"```(?:python)?\s*\n(.*?)```", raw, re.S)
                return (m.group(1) if m else raw).strip()
            except Exception:
                pass
        return (
            "# Deterministic scaffold: no local coding model was available.\n"
            "print('Task:', " + repr(task) + ")\n"
            "print('This sandbox run demonstrates the execute -> observe -> repair loop.')\n"
        )

    def _fix_code(self, task: str, code: str, result: dict) -> str | None:
        if not gateway.online:
            return None
        try:
            raw = gateway.generate_for(
                "coding",
                "The following Python script failed in the sandbox. Fix it.\n"
                f"Task: {task}\nScript:\n```python\n{code}\n```\n"
                f"Exit code: {result.get('exit_code')}\nStderr:\n{result.get('stderr','')}\n"
                "Reply ONLY with the corrected code inside a single ```python block.",
                temperature=0.0, num_predict=700)
            m = re.search(r"```(?:python)?\s*\n(.*?)```", raw, re.S)
            fixed = (m.group(1) if m else raw).strip()
            return fixed or None
        except Exception:
            return None

    def _final_answer(self, task: str, ctx: TaskContext) -> str:
        evidence = self._observations_block(ctx, compact=True)
        citations = self._citation_block(ctx)
        if gateway.online and ctx.actions:
            try:
                raw = gateway.generate_for(
                    "reasoning",
                    f"TASK: {task}\nTool observations:\n{evidence}\n\n"
                    "VERBATIM TEXT RETRIEVED FROM THE LOCAL KNOWLEDGE BASE (the only "
                    "authoritative source for facts):\n" + (citations or "(none)") + "\n\n"
                    "Write the final answer for the user. STRICTLY ground every factual "
                    "claim in the observations or verbatim text above — do NOT invent "
                    "numbers, limits or quotes. When the verbatim text answers the task, "
                    "quote its exact figures and name the source file. Mention "
                    "deliverable files by name. If calculations were performed, show the "
                    "steps and the final result.",
                    temperature=0.2, num_predict=800)
                if raw:
                    if citations:
                        raw += "\n\nSources (verbatim, from the local knowledge base):\n" + citations
                    return raw
            except Exception:
                pass
        # deterministic summary
        lines = [f"Task complete: {task}", ""]
        for a in ctx.actions:
            mark = "✓" if a["ok"] else "✗"
            lines.append(f"{mark} {a['tool']}: {a['summary']}")
        if ctx.deliverables:
            lines.append("")
            lines.append("Deliverables: " + ", ".join(ctx.deliverables))
        return "\n".join(lines)

    def _citation_block(self, ctx) -> str:
        """Verbatim text of the best knowledge-base hits, so the final answer
        (and the drafted deliverables) can cite real local sources."""
        out, seen = [], set()
        for a in ctx.actions:
            r = a.get("result")
            if a["tool"] == "search_knowledge_base" and isinstance(r, dict):
                for h in r.get("hits", []):
                    key = (h["source"], h["chunk"])
                    if key in seen:
                        continue
                    seen.add(key)
                    out.append(f"--- {h['source']} ---\n{h['text'][:700]}")
            elif a["tool"] in ("ocr_image",) and isinstance(r, dict) and r.get("text"):
                out.append(f"--- OCR ({r.get('engine', '')}) ---\n{str(r['text'])[:700]}")
        return "\n\n".join(out[:6])

    def _observations_block(self, ctx, compact=False) -> str:
        blocks = []
        for i, a in enumerate(ctx.actions, 1):
            r = a.get("result")
            detail = ""
            if isinstance(r, dict):
                if "hits" in r and r["hits"]:
                    detail = " | ".join(f"[{h['source']}] {h['text'][:180]}" for h in r["hits"][:3])
                elif "text" in r and r.get("text"):
                    detail = str(r["text"])[:300]
                elif "answer" in r:
                    detail = str(r["answer"])[:400]
                elif "stdout" in r:
                    detail = f"stdout: {str(r.get('stdout'))[:400]} exit={r.get('exit_code')}"
            blocks.append(f"{i}. {a['tool']} ({'ok' if a['ok'] else 'FAILED'}): {a['summary']}"
                          + (f" — {detail}" if detail and not compact else ""))
        return "\n".join(blocks)


class TaskManager:
    """Keeps task history so the UI can render past runs."""

    def __init__(self):
        self.tasks: dict[str, TaskContext] = {}

    def register(self, ctx: TaskContext):
        self.tasks[ctx.id] = ctx


task_manager = TaskManager()
