"""Local knowledge base (RAG) — 100% on-premise.

Ingestion: walk the kb/ folder, chunk documents, embed chunks with the LOCAL
embedding model (nomic-embed-text via loopback Ollama). If the embedding
model is unavailable, fall back to a deterministic hashed char-ngram TF-IDF
vector computed in-process — still fully local, no downloads.

Storage: a JSON + numpy vector store on local disk. Retrieval: cosine
similarity over local vectors. Nothing leaves the machine at any point.
"""
import hashlib
import json
import math
import re
import threading
from pathlib import Path

import numpy as np

from ..config import KB_DIR, VECTOR_STORE_PATH
from ..models.provider import gateway

_lock = threading.Lock()
_store = {"chunks": [], "vectors": None}

CHUNK_SIZE = 900
CHUNK_OVERLAP = 120


def _iter_documents():
    for p in sorted(KB_DIR.rglob("*")):
        if not p.is_file() or p.name.startswith("."):
            continue
        ext = p.suffix.lower()
        try:
            if ext in (".txt", ".md"):
                yield p, p.read_text(errors="replace")
            elif ext == ".pdf":
                import pypdf
                reader = pypdf.PdfReader(str(p))
                yield p, "\n".join((pg.extract_text() or "") for pg in reader.pages)
            elif ext == ".docx":
                from docx import Document
                d = Document(str(p))
                yield p, "\n".join(par.text for par in d.paragraphs)
        except Exception:
            continue


def _chunk_text(text: str) -> list[str]:
    text = re.sub(r"\s+", " ", text).strip()
    if not text:
        return []
    chunks = []
    start = 0
    while start < len(text):
        end = min(start + CHUNK_SIZE, len(text))
        # try to break on a sentence boundary
        if end < len(text):
            window = text[start:end]
            for sep in (". ", ".\n", "! ", "? "):
                idx = window.rfind(sep)
                if idx > CHUNK_SIZE // 2:
                    end = start + idx + 1
                    break
        chunks.append(text[start:end])
        start = max(end - CHUNK_OVERLAP, start + 1)
    return chunks


def _hash_embed(text: str, dim: int = 512) -> list[float]:
    """Deterministic local fallback embedding: hashed char-trigram TF-IDF."""
    vec = np.zeros(dim, dtype=np.float32)
    text = text.lower()
    tokens = re.findall(r"[a-z0-9]+", text)
    grams = []
    for tok in tokens:
        grams.append(tok)
        if len(tok) > 3:
            grams += [tok[i:i + 3] for i in range(len(tok) - 2)]
    if not grams:
        return vec.tolist()
    for g in grams:
        h = int(hashlib.md5(g.encode()).hexdigest(), 16)
        vec[h % dim] += 1.0
        vec[(h >> 32) % dim] += 0.5
    norm = float(np.linalg.norm(vec))
    if norm:
        vec /= norm
    return vec.tolist()


def _embed(text: str) -> tuple[list[float], str]:
    v = gateway.embed_text(text)
    if v is not None:
        return v, f"local-embedding:{gateway.resolve('embedding')}"
    return _hash_embed(text), "local-hash-tfidf"


def reindex(progress=None) -> dict:
    """Rebuild the vector store from everything in kb/."""
    with _lock:
        chunks: list[dict] = []
        vectors: list[list[float]] = []
        engines = set()
        for path, text in _iter_documents():
            for i, chunk in enumerate(_chunk_text(text)):
                vec, engine = _embed(chunk)
                engines.add(engine)
                chunks.append({
                    "id": f"{path.name}#{i}",
                    "source": path.name,
                    "chunk": i,
                    "text": chunk,
                })
                vectors.append(vec)
                if progress:
                    progress(f"indexed {path.name} chunk {i + 1}")
        _store["chunks"] = chunks
        _store["vectors"] = np.array(vectors, dtype=np.float32) if vectors else None
        VECTOR_STORE_PATH.write_text(json.dumps({
            "chunks": chunks,
            "engine": sorted(engines),
            # persisted so restarts don't need to re-embed
            "vectors": [v for v in (_store["vectors"].tolist() if _store["vectors"] is not None else [])],
        }))
    return {"documents_indexed": len(_store["chunks"]),
            "engines": sorted(engines)}


def load() -> None:
    with _lock:
        if VECTOR_STORE_PATH.exists():
            data = json.loads(VECTOR_STORE_PATH.read_text())
            _store["chunks"] = data.get("chunks", [])
            stored = data.get("vectors")
            if stored:
                _store["vectors"] = np.array(stored, dtype=np.float32)
            else:
                # legacy store without saved vectors — re-embed locally
                vecs = [_embed(c["text"])[0] for c in _store["chunks"]]
                _store["vectors"] = np.array(vecs, dtype=np.float32) if vecs else None


def _cosine(a: np.ndarray, b: np.ndarray) -> float:
    na, nb = np.linalg.norm(a), np.linalg.norm(b)
    if na == 0 or nb == 0:
        return 0.0
    return float(np.dot(a, b) / (na * nb))


def search(query: str, top_k: int = 4) -> list[dict]:
    with _lock:
        chunks = _store["chunks"]
        vectors = _store["vectors"]
    if not chunks or vectors is None:
        return []
    qv = np.nan_to_num(np.array(_embed(query)[0], dtype=np.float64))
    vecs = np.nan_to_num(vectors.astype(np.float64))
    doc_norms = np.linalg.norm(vecs, axis=1)
    q_norm = np.linalg.norm(qv)
    denom = np.where(doc_norms * (q_norm or 1.0) > 1e-9,
                     doc_norms * (q_norm or 1.0), 1.0)
    sims = (vecs @ qv) / denom
    top_idx = np.argsort(sims)[::-1][:top_k]
    results = []
    for i in top_idx:
        if sims[i] <= 0.01:
            continue
        c = chunks[int(i)]
        results.append({"source": c["source"], "chunk": c["chunk"],
                        "score": round(float(sims[i]), 3), "text": c["text"]})
    return results


def stats() -> dict:
    with _lock:
        chunks = _store["chunks"]
        vectors = _store["vectors"]
        sources = sorted({c["source"] for c in chunks})
        return {"chunks": len(chunks), "sources": sources,
                "dim": int(vectors.shape[1]) if vectors is not None and vectors.size else 0,
                "kb_files": [p.name for p in sorted(KB_DIR.rglob('*')) if p.is_file()]}
