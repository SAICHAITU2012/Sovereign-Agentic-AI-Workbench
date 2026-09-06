"""Task classifier + model router.

Given a user task (and any attached files), decide what KIND of work it is
and which local open-weight model should handle each capability. This is the
component judges look for: the system picks the model, not the user.

Classification is two-stage:
  1. Fast deterministic heuristics (keywords, file types) — always runs.
  2. A local LLM sanity-check when available, which can override the label.

The result is auditable: we keep the evidence for the routing panel in the UI.
"""
import re
from dataclasses import dataclass, field

TASK_TYPES = {
    "coding": "Software task: write, review, debug, or verify code / do a calculation",
    "document_analysis": "Understand a document: PDF, report, scanned file, drawings",
    "vision": "Understand an image: engineering drawing, photograph, handwriting",
    "knowledge_qa": "Answer from internal knowledge: SOPs, manuals, past correspondence",
    "general": "General reasoning, drafting, or planning",
}

_KEYWORDS = {
    "coding": [
        r"\bpython\b", r"\bcode\b", r"\bscript\b", r"\bfunction\b", r"\bbug\b",
        r"\bdebug\b", r"\bprogram\b", r"\bcalculate\b", r"\bcompute\b",
        r"\.py\b", r"\bexcel\b", r"\bspreadsheet\b", r"\bformula\b",
    ],
    "document_analysis": [
        r"\bpdf\b", r"\breport\b", r"\bscanned\b", r"\bdocument\b",
        r"\binspection\b", r"\bocr\b", r"\bp&?id\b", r"\bdrawing\b",
        r"\bsummar(ize|ise|y)\b", r"\bextract\b", r"\bapproval\b", r"\bnote\b",
    ],
    "vision": [
        r"\bimage\b", r"\bphoto\b", r"\bpicture\b", r"\bscan\b", r"\bhandwrit",
        r"\bdrawing\b", r"\bp&?id\b", r"\bdiagram\b",
    ],
    "knowledge_qa": [
        r"\bsop\b", r"\bmanual\b", r"\bpolic(y|ies)\b", r"\bprocedure\b",
        r"\bpast correspondence\b", r"\bknowledge\b", r"\bwhat does\b",
        r"\baccording to\b", r"\bguideline\b", r"\bcompliance\b",
    ],
}


@dataclass
class RoutingDecision:
    task_type: str
    confidence: float
    evidence: list[str] = field(default_factory=list)
    models: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "task_type": self.task_type,
            "description": TASK_TYPES[self.task_type],
            "confidence": round(self.confidence, 2),
            "evidence": self.evidence,
            "models": self.models,
        }


def classify_task(task: str, attachments: list[str] | None = None,
                  llm_classifier=None) -> RoutingDecision:
    attachments = attachments or []
    scores = {k: 0.0 for k in TASK_TYPES}
    evidence: list[str] = []

    lowered = task.lower()
    for ttype, patterns in _KEYWORDS.items():
        for pat in patterns:
            m = re.search(pat, lowered)
            if m:
                scores[ttype] += 1.0
                evidence.append(f"keyword '{m.group(0)}' → {ttype}")

    for path in attachments:
        p = path.lower()
        if p.endswith(".py") or p.endswith(".ipynb"):
            scores["coding"] += 3.0
            evidence.append(f"attachment {path} → coding")
        elif p.endswith((".png", ".jpg", ".jpeg", ".bmp", ".tiff")):
            scores["vision"] += 3.0
            evidence.append(f"attachment {path} → vision")
        elif p.endswith(".pdf"):
            scores["document_analysis"] += 3.0
            evidence.append(f"attachment {path} → document_analysis")

    # "summarize this image" style combos: both signals fire — document wins
    # only when a PDF exists; pure image stays vision.
    best = max(scores, key=scores.get)
    total = sum(scores.values())
    confidence = scores[best] / total if total else 0.0
    if total == 0:
        best, confidence = "general", 0.0
        evidence.append("no strong signals → general")

    if llm_classifier is not None and confidence < 0.5:
        # only let the local LLM override when the heuristics were weak;
        # strong evidence (e.g. an attached .png or .py) wins
        try:
            decision = llm_classifier(task, list(TASK_TYPES.keys()))
            if decision in TASK_TYPES:
                evidence.append(f"local LLM classifier → {decision}")
                if decision != best:
                    best = decision
                    confidence = max(confidence, 0.75)
        except Exception:
            pass  # heuristics already gave us an answer

    return RoutingDecision(task_type=best, confidence=max(confidence, 0.5),
                           evidence=evidence)
