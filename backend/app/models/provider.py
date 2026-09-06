"""Model provider layer — the only module that ever talks to an LLM.

Everything is routed to a LOCAL Ollama server on 127.0.0.1. No cloud SDKs
exist anywhere in this codebase. Adding a new open-weight model later means
appending one entry to MODEL_REGISTRY — nothing else changes.
"""
import json
from typing import Optional

import httpx

from ..config import OLLAMA_BASE_URL, MODEL_REGISTRY
from ..security import egress


class OllamaProvider:
    """Thin client over the local Ollama HTTP API (loopback only)."""

    def __init__(self, base_url: str = OLLAMA_BASE_URL):
        self.base_url = base_url
        self._client = httpx.Client(base_url=base_url, timeout=300.0)

    def available(self) -> bool:
        try:
            r = self._client.get("/api/tags", timeout=3.0)
            return r.status_code == 200
        except Exception:
            return False

    def installed_models(self) -> list[str]:
        try:
            r = self._client.get("/api/tags", timeout=3.0)
            return [m["name"] for m in r.json().get("models", [])]
        except Exception:
            return []

    def generate(self, model: str, prompt: str, images: Optional[list[str]] = None,
                 system: Optional[str] = None, temperature: float = 0.2,
                 num_predict: int = 1024) -> str:
        payload = {
            "model": model,
            "prompt": prompt,
            "stream": False,
            "keep_alive": "30m",
            "options": {"temperature": temperature, "num_predict": num_predict},
        }
        if system:
            payload["system"] = system
        if images:
            payload["images"] = images  # base64, no prefix
        r = self._client.post("/api/generate", json=payload)
        r.raise_for_status()
        return r.json().get("response", "").strip()

    def embed(self, model: str, text: str) -> list[float]:
        r = self._client.post("/api/embed", json={"model": model, "input": text})
        r.raise_for_status()
        data = r.json()
        if "embeddings" in data and data["embeddings"]:
            return data["embeddings"][0]
        return data["embedding"]


provider = OllamaProvider()


def _strip_latest(name: str) -> str:
    return name[:-len(":latest")] if name.endswith(":latest") else name


def _matches(wanted: str, installed: set[str]) -> bool:
    w = _strip_latest(wanted)
    return wanted in installed or any(_strip_latest(i) == w for i in installed)


def _canonical(wanted: str, installed: set[str]) -> str:
    if wanted in installed:
        return wanted
    w = _strip_latest(wanted)
    for i in installed:
        if _strip_latest(i) == w:
            return i
    return wanted


class ModelGateway:
    """Resolve a capability ('reasoning' | 'coding' | 'vision' | 'embedding')
    to the best installed local model, honouring fallbacks."""

    def __init__(self):
        self._installed: set[str] = set()
        self._online = False
        self.refresh()

    def refresh(self) -> None:
        self._online = provider.available()
        self._installed = set(provider.installed_models())

    @property
    def online(self) -> bool:
        return self._online

    def resolve(self, capability: str) -> Optional[str]:
        entry = MODEL_REGISTRY.get(capability)
        if entry is None:
            return None
        candidates = [entry["model"]] + list(entry.get("fallbacks", []))
        for m in candidates:
            if _matches(m, self._installed):
                return _canonical(m, self._installed)
        return None

    def status(self) -> dict:
        self.refresh()
        caps = {}
        for cap, entry in MODEL_REGISTRY.items():
            primary = entry["model"]
            resolved = self.resolve(cap)
            caps[cap] = {
                "primary": primary,
                "capability": entry["capability"],
                "resolved": resolved,
                "ready": resolved is not None,
                "fallbacks": entry.get("fallbacks", []),
            }
        return {
            "engine": "ollama (local, 127.0.0.1:11434)",
            "online": self._online,
            "installed": sorted(self._installed),
            "capabilities": caps,
        }

    def generate_for(self, capability: str, prompt: str, **kw) -> str:
        model = self.resolve(capability)
        if model is None:
            raise RuntimeError(f"No local model installed for capability '{capability}'")
        return provider.generate(model, prompt, **kw)

    def embed_text(self, text: str) -> Optional[list[float]]:
        model = self.resolve("embedding")
        if model is None:
            return None
        try:
            return provider.embed(model, text)
        except Exception:
            return None


gateway = ModelGateway()


def extract_json(text: str) -> Optional[dict]:
    """Best-effort extraction of a JSON object from an LLM reply."""
    text = text.strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.lower().startswith("json"):
            text = text[4:]
    start = text.find("{")
    if start == -1:
        return None
    depth = 0
    for i in range(start, len(text)):
        if text[i] == "{":
            depth += 1
        elif text[i] == "}":
            depth -= 1
            if depth == 0:
                try:
                    return json.loads(text[start:i + 1])
                except json.JSONDecodeError:
                    return None
    return None
