"""Local tool implementations for the agent.

Every tool is pure-local: filesystem under the workspace, local Ollama,
local Python sandbox. Each tool declares a JSON schema so the agent can
call it, and returns (summary, payload) tuples for the activity timeline.
"""
import base64
import json
import os
import re
import subprocess
import sys
import tempfile
import textwrap
import time
import uuid
from pathlib import Path
from typing import Any, Callable

from ..config import UPLOADS_DIR, OUTPUTS_DIR, SANDBOX_DIR, KB_DIR, SANDBOX_TIMEOUT_S

TOOL_REGISTRY: dict[str, "Tool"] = {}


class Tool:
    def __init__(self, name: str, description: str, schema: dict,
                 fn: Callable[..., tuple[str, Any]]):
        self.name = name
        self.description = description
        self.schema = schema
        self.fn = fn

    def run(self, **kwargs):
        return self.fn(**kwargs)

    def to_dict(self) -> dict:
        return {"name": self.name, "description": self.description,
                "schema": self.schema}


def tool(name: str, description: str, schema: dict):
    def deco(fn):
        TOOL_REGISTRY[name] = Tool(name, description, schema, fn)
        return fn
    return deco


def _safe_path(path: str, base: Path = None) -> Path:
    """Resolve a path and refuse anything escaping the workspace."""
    base = base or (SANDBOX_DIR.parent)
    p = (base / path).resolve() if not Path(path).is_absolute() else Path(path).resolve()
    workspace_root = SANDBOX_DIR.parent.resolve()
    if not (p == workspace_root or workspace_root in p.parents):
        raise ValueError(f"Path escapes workspace: {path}")
    return p


def _relative(path: Path) -> str:
    try:
        return str(path.relative_to(SANDBOX_DIR.parent))
    except ValueError:
        return str(path)


# ---------------------------------------------------------------- files ----

@tool("list_files", "List files in a workspace folder (uploads, outputs, kb, sandbox).",
      {"type": "object", "properties": {"folder": {"type": "string",
       "description": "one of: uploads, outputs, kb, sandbox"}},
       "required": ["folder"]})
def list_files(folder: str = "uploads"):
    base = SANDBOX_DIR.parent / folder
    if not base.exists():
        return f"Folder '{folder}' does not exist.", []
    files = [str(p.relative_to(SANDBOX_DIR.parent)) for p in sorted(base.rglob("*"))
             if p.is_file() and not p.name.startswith(".")]
    return f"{len(files)} file(s) in {folder}/", files


@tool("read_file", "Read a text file from the workspace (uploads, outputs, kb, sandbox).",
      {"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]})
def read_file(path: str):
    p = _safe_path(path)
    if not p.exists():
        return f"File not found: {path}", None
    text = p.read_text(errors="replace")
    return f"Read {len(text)} chars from {path}", text[:20000]


@tool("write_file", "Write text content to a file inside the workspace.",
      {"type": "object",
       "properties": {"path": {"type": "string"}, "content": {"type": "string"}},
       "required": ["path", "content"]})
def write_file(path: str, content: str):
    p = _safe_path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content)
    return f"Wrote {len(content)} chars to {path}", {"path": _relative(p),
                                                     "deliverable": _relative(p),
                                                     "bytes": len(content)}


# ------------------------------------------------------- python sandbox ----

_SANDBOX_PRELUDE = textwrap.dedent("""
    import sys, types
    # Air-gapped sandbox: no network, no subprocesses, no file writes outside
    # the sandbox working directory are permitted from generated code.
    import socket
    class _BlockedSocket(socket.socket):
        def connect(self, address):
            raise ConnectionError("Sandbox: network access is disabled")
    socket.socket = _BlockedSocket
    import os
    os.chdir(os.environ.get("SANDBOX_CWD", "."))
    os.environ["HOME"] = os.environ.get("SANDBOX_CWD", ".")
""")


@tool("run_python", "Execute Python code in a restricted local sandbox (no network, "
      "no subprocess, 30s timeout). Use for calculations (show steps) and data processing.",
      {"type": "object", "properties": {"code": {"type": "string"},
       "purpose": {"type": "string", "description": "why this code is being run"}},
       "required": ["code"]})
def run_python(code: str, purpose: str = ""):
    run_id = uuid.uuid4().hex[:8]
    workdir = SANDBOX_DIR / f"run_{run_id}"
    workdir.mkdir(parents=True, exist_ok=True)
    script = workdir / "main.py"
    script.write_text(_SANDBOX_PRELUDE + "\n# --- generated code ---\n" + code)

    env = {
        "PATH": "/usr/bin:/bin:/opt/homebrew/bin",
        "SANDBOX_CWD": str(workdir),
        "HOME": str(workdir),
        "PYTHONHASHSEED": "0",
    }
    started = time.time()
    try:
        proc = subprocess.run(
            [sys.executable, "-I", str(script)],
            cwd=str(workdir), env=env, capture_output=True, text=True,
            timeout=SANDBOX_TIMEOUT_S,
        )
        elapsed = round(time.time() - started, 2)
        result = {
            "run_id": run_id,
            "exit_code": proc.returncode,
            "stdout": proc.stdout[-8000:],
            "stderr": proc.stderr[-4000:],
            "elapsed_s": elapsed,
            "workdir": _relative(workdir),
        }
        verdict = "OK" if proc.returncode == 0 else f"EXIT {proc.returncode}"
        return f"Sandbox run {verdict} in {elapsed}s", result
    except subprocess.TimeoutExpired:
        return f"Sandbox run timed out after {SANDBOX_TIMEOUT_S}s", {
            "run_id": run_id, "exit_code": -9, "stdout": "", "stderr": "timeout",
            "timed_out": True,
        }


# ------------------------------------------------------ office documents ----

def _add_runs(par, text: str):
    """Add text to a paragraph, converting **bold** spans to real bold runs
    and stripping any leftover markdown emphasis characters."""
    for i, part in enumerate(re.split(r"\*\*(.+?)\*\*", text)):
        if not part:
            continue
        run = par.add_run(part.replace("*", ""))
        if i % 2 == 1:
            run.bold = True


def _md_heading_level(line: str) -> int | None:
    """Return the Word heading level for a markdown '# ' line, else None."""
    m = re.match(r"^(#{1,4})\s+(.*)$", line)
    if not m:
        return None
    return len(m.group(1))


@tool("create_docx", "Create a Word (.docx) deliverable from a title and structured "
      "content (sections given as markdown-ish text with '## Section' headers).",
      {"type": "object",
       "properties": {"filename": {"type": "string"},
                      "title": {"type": "string"},
                      "content": {"type": "string"}},
       "required": ["filename", "title", "content"]})


def create_docx(filename: str, title: str, content: str):
    from docx import Document

    doc = Document()
    doc.add_heading(title, level=0)
    for raw_line in content.split("\n"):
        line = raw_line.strip()
        if not line:
            continue
        level = _md_heading_level(line)
        if level:
            text = re.sub(r"^#+\s*", "", line).replace("**", "")
            doc.add_heading(text, level=min(level, 3))
        elif line.startswith("- ") or line.startswith("* "):
            par = doc.add_paragraph(style="List Bullet")
            _add_runs(par, line[2:])
        elif re.match(r"^\d+\.\s+", line):
            par = doc.add_paragraph(style="List Number")
            _add_runs(par, re.sub(r"^\d+\.\s+", "", line))
        else:
            par = doc.add_paragraph()
            _add_runs(par, line)

    out = OUTPUTS_DIR / filename
    out.parent.mkdir(parents=True, exist_ok=True)
    doc.save(str(out))
    return f"Created Word document {out.name}", {"deliverable": _relative(out)}


@tool("create_xlsx", "Create an Excel (.xlsx) deliverable. Provide rows for one or "
      "more sheets: {\"Sheets\": [{\"name\": str, \"headers\": [..], \"rows\": [[..],..]}]}",
      {"type": "object",
       "properties": {"filename": {"type": "string"}, "data": {"type": "string",
        "description": "JSON string with key 'Sheets'"}},
       "required": ["filename", "data"]})
def create_xlsx(filename: str, data: str):
    from openpyxl import Workbook

    parsed = data if isinstance(data, dict) else json.loads(data)
    wb = Workbook()
    wb.remove(wb.active)
    for sheet in parsed.get("Sheets", []):
        ws = wb.create_sheet(title=str(sheet.get("name", "Sheet"))[:31])
        headers = sheet.get("headers", [])
        if headers:
            ws.append(headers)
        for row in sheet.get("rows", []):
            ws.append(row)
    out = OUTPUTS_DIR / filename
    out.parent.mkdir(parents=True, exist_ok=True)
    wb.save(str(out))
    return f"Created Excel workbook {out.name}", {"deliverable": _relative(out)}


@tool("create_pptx", "Create a PowerPoint (.pptx) deliverable from slide definitions: "
      "JSON {\"Slides\": [{\"title\": str, \"bullets\": [..]}]}",
      {"type": "object",
       "properties": {"filename": {"type": "string"}, "data": {"type": "string"}},
       "required": ["filename", "data"]})
def create_pptx(filename: str, data: str):
    from pptx import Presentation

    parsed = data if isinstance(data, dict) else json.loads(data)
    prs = Presentation()
    for slide_def in parsed.get("Slides", []):
        slide = prs.slides.add_slide(prs.slide_layouts[1])
        slide.shapes.title.text = str(slide_def.get("title", ""))
        body = slide.placeholders[1].text_frame
        body.text = ""
        for i, bullet in enumerate(slide_def.get("bullets", [])):
            p = body.paragraphs[0] if i == 0 else body.add_paragraph()
            p.text = str(bullet)
    out = OUTPUTS_DIR / filename
    out.parent.mkdir(parents=True, exist_ok=True)
    prs.save(str(out))
    return f"Created presentation {out.name}", {"deliverable": _relative(out)}


# ------------------------------------------------------------ pdf / ocr ----

@tool("extract_pdf", "Extract text and page images from a PDF (works for digital and "
      "scanned PDFs; scanned pages are flagged for OCR / vision analysis).",
      {"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]})
def extract_pdf(path: str):
    p = _safe_path(path)
    if not p.exists():
        return f"File not found: {path}", None

    text_parts, image_pages, needs_ocr = [], [], False
    try:
        import pypdf
        reader = pypdf.PdfReader(str(p))
        for i, page in enumerate(reader.pages):
            t = (page.extract_text() or "").strip()
            if len(t) < 20:
                needs_ocr = True
                image_pages.append(i + 1)
            text_parts.append(f"--- page {i + 1} ---\n{t}")
    except Exception as e:
        return f"PDF extraction failed: {e}", None

    # Render pages to PNG so the vision model can inspect them.
    page_images: list[str] = []
    try:
        import pypdfium2 as pdfium
        pdf = pdfium.PdfDocument(str(p))
        for i in range(len(pdf)):
            bmp = pdf[i].render(scale=2.0)
            img_path = workdir_img = SANDBOX_DIR / f"{p.stem}_p{i + 1}.png"
            img = bmp.to_pil()
            img.save(img_path)
            page_images.append(_relative(img_path))
    except Exception:
        pass

    full_text = "\n".join(text_parts)
    if needs_ocr:
        full_text += ("\n\n[NOTE: little/no text layer detected on page(s) "
                      f"{image_pages} — this looks like a scanned document; run OCR/vision on page images]")
    summary = (f"Extracted {len(text_parts)} pages, {len(full_text)} chars from {p.name}"
               + (" — scanned document, OCR/vision recommended" if needs_ocr else ""))
    return summary, {
        "text": full_text[:20000], "pages": len(text_parts),
        "scanned": needs_ocr, "image_pages": image_pages,
        "page_images": page_images,
    }


@tool("ocr_image", "Run on-device OCR on an image (scanned page, handwriting). Falls "
      "back to the local vision model if tesseract is unavailable.",
      {"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]})
def ocr_image(path: str):
    p = _safe_path(path)
    if not p.exists():
        return f"File not found: {path}", None
    try:
        import pytesseract
        from PIL import Image
        text = pytesseract.image_to_string(Image.open(str(p)))
        text = text.strip()
        if text:
            return f"OCR extracted {len(text)} chars", {"text": text, "engine": "tesseract (local)"}
    except Exception:
        pass
    # Air-gapped fallback: the local open-weight VLM does the text extraction.
    from ..models.provider import gateway
    model = gateway.resolve("vision")
    if model is None:
        return "No OCR engine or local vision model available", {"text": "", "engine": None}
    answer = gateway.generate_for(
        "vision",
        "Extract ALL text from this scanned page verbatim, preserving headings, "
        "numbers, units and table structure.",
        images=[base64.b64encode(p.read_bytes()).decode()], num_predict=900)
    return (f"OCR via local vision model '{model}' extracted {len(answer)} chars",
            {"text": answer, "engine": f"vision-model:{model}"})


@tool("analyze_image", "Analyse an image with the local open-weight vision model "
      "(P&IDs, drawings, photographs, scanned/handwritten pages).",
      {"type": "object",
       "properties": {"path": {"type": "string"}, "question": {"type": "string"}},
       "required": ["path"]})
def analyze_image(path: str, question: str = "Describe this image in detail, including any text, labels, equipment and notable features."):
    from ..models.provider import gateway
    p = _safe_path(path)
    if not p.exists():
        return f"File not found: {path}", None
    b64 = base64.b64encode(p.read_bytes()).decode()
    model = gateway.resolve("vision")
    if model is None:
        return "No local vision model installed", None
    answer = gateway.generate_for("vision", question, images=[b64], num_predict=512)
    return f"Vision model '{model}' analysed {p.name}", {"model": model, "answer": answer}


@tool("search_knowledge_base", "Semantic search over the local knowledge base "
      "(company SOPs, manuals, past correspondence). Grounds answers in internal docs.",
      {"type": "object", "properties": {"query": {"type": "string"},
       "top_k": {"type": "integer"}}, "required": ["query"]})
def search_knowledge_base(query: str, top_k: int = 4):
    from ..rag import store as rag_store
    hits = rag_store.search(query, top_k=top_k)
    if not hits:
        return "No matching documents in the local knowledge base.", {"hits": []}
    top_src = ", ".join(sorted({h["source"] for h in hits}))
    return f"Found {len(hits)} relevant chunk(s) in {top_src}", {"hits": hits}


def get_tools() -> dict[str, Tool]:
    return TOOL_REGISTRY
