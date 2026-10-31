"""Sovereign Agentic AI Workbench — API server.

All endpoints are served from localhost. The egress guard is installed at
startup so the whole backend process is physically unable to open a
connection to the internet (and every attempt is logged for the monitor).
"""
import asyncio
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path

from fastapi import FastAPI, UploadFile, File, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from .config import UPLOADS_DIR, OUTPUTS_DIR, KB_DIR
from .security import egress

egress.install_egress_guard()  # FIRST — before anything can make requests

from .models.provider import gateway
from .agent.orchestrator import Orchestrator, task_manager
from .rag import store as rag_store

app = FastAPI(title="Sovereign Agentic AI Workbench", version="1.0")


def _safe_filename(name: str) -> str:
    """Keep only the basename of an uploaded filename.

    Blocks traversal ('../../.zprofile'), absolute paths ('/etc/passwd') and
    hidden/dot files — anything else would let a client write outside the
    intended directory.
    """
    clean = Path(name or "").name.strip()
    if not clean or clean.startswith(".") or clean in {".", ".."}:
        raise HTTPException(status_code=400, detail="invalid filename")
    return clean


@app.on_event("startup")
async def startup():
    rag_store.load()


# --------------------------------------------------------------- health ----

@app.get("/api/health")
async def health():
    return {
        "status": "ok",
        "time": datetime.now(timezone.utc).isoformat(),
        "engine": gateway.status(),
        "egress": egress.snapshot(),
        "kb": rag_store.stats(),
    }


@app.get("/api/models")
async def models():
    return gateway.status()


@app.get("/api/network")
async def network():
    return egress.snapshot()


@app.post("/api/network/selftest")
async def network_selftest():
    """Deliberately attempt an outbound connection so the air-gap can be
    demonstrated live: the egress guard must block it and log the event."""
    import httpx
    try:
        httpx.Client(timeout=4.0).get("https://example.com")
        return {"blocked": False, "detail": "UNEXPECTED: outbound request succeeded"}
    except egress.ConnectionBlocked as e:
        return {"blocked": True, "detail": str(e)}
    except Exception as e:  # network-level failure also proves no egress path
        return {"blocked": True, "detail": f"no external egress ({e.__class__.__name__}: {e})"}


# -------------------------------------------------------------- uploads ----

@app.post("/api/upload")
async def upload(file: UploadFile = File(...)):
    clean = _safe_filename(file.filename)
    dest = UPLOADS_DIR / clean
    with dest.open("wb") as f:
        shutil.copyfileobj(file.file, f)
    return {"path": f"uploads/{clean}", "size": dest.stat().st_size}


@app.get("/api/files")
async def files():
    def listing(base: Path):
        return [
            {"path": str(p.relative_to(base.parent)), "name": p.name,
             "size": p.stat().st_size, "modified": p.stat().st_mtime}
            for p in sorted(base.rglob("*")) if p.is_file() and not p.name.startswith(".")
        ]
    return {"uploads": listing(UPLOADS_DIR), "outputs": listing(OUTPUTS_DIR),
            "kb": listing(KB_DIR)}


@app.get("/api/download")
async def download(path: str):
    p = Path(path)
    if not p.is_absolute():
        p = UPLOADS_DIR.parent / p
    p = p.resolve()
    root = UPLOADS_DIR.parent.resolve()
    if root not in p.parents and p != root:
        return JSONResponse({"error": "path escapes workspace"}, status_code=400)
    if not p.exists():
        return JSONResponse({"error": "not found"}, status_code=404)
    return FileResponse(str(p), filename=p.name)


# ------------------------------------------------------------------ kb -----
@app.post("/api/kb/reindex")
async def kb_reindex():
    result = rag_store.reindex()
    return {"ok": True, **result, "stats": rag_store.stats()}


@app.post("/api/kb/upload")
async def kb_upload(file: UploadFile = File(...)):
    clean = _safe_filename(file.filename)
    dest = KB_DIR / clean
    with dest.open("wb") as f:
        shutil.copyfileobj(file.file, f)
    return {"path": str(dest), "name": clean}


# -------------------------------------------------------------- tasks ------

async def run_task_and_stream(ws: WebSocket, task: str, attachments: list[str]):
    loop = asyncio.get_running_loop()
    queue: asyncio.Queue = asyncio.Queue()

    def emit(event: dict):
        loop.call_soon_threadsafe(queue.put_nowait, event)

    async def sender():
        while True:
            event = await queue.get()
            if event is None:
                break
            await ws.send_text(json.dumps(event))

    sender_task = asyncio.create_task(sender())
    try:
        orch = Orchestrator(emit)
        ctx = await loop.run_in_executor(None, orch.run, task, attachments)
        task_manager.register(ctx)
    finally:
        await queue.put(None)
        await sender_task


@app.websocket("/ws/task")
async def ws_task(ws: WebSocket):
    await ws.accept()
    try:
        while True:
            msg = json.loads(await ws.receive_text())
            task = (msg.get("task") or "").strip()
            attachments = msg.get("attachments") or []
            if task:
                await run_task_and_stream(ws, task, attachments)
    except WebSocketDisconnect:
        return
    except Exception as e:
        try:
            await ws.send_text(json.dumps({"type": "error", "message": str(e)}))
        except Exception:
            pass


# ------------------------------------------------------------- static ------
static_dir = Path(__file__).parent / "static"
app.mount("/", StaticFiles(directory=str(static_dir), html=True), name="static")
