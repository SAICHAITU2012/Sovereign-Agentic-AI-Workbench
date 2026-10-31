"""Central configuration for the Sovereign Agentic AI Workbench."""
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
WORKSPACE = PROJECT_ROOT / "workspace"
KB_DIR = WORKSPACE / "kb"
UPLOADS_DIR = WORKSPACE / "uploads"
OUTPUTS_DIR = WORKSPACE / "outputs"
SANDBOX_DIR = WORKSPACE / "sandbox"
VECTOR_STORE_PATH = WORKSPACE / "vector_store.json"

for d in (WORKSPACE, KB_DIR, UPLOADS_DIR, OUTPUTS_DIR, SANDBOX_DIR):
    d.mkdir(parents=True, exist_ok=True)

# --- Ollama (local inference server on 127.0.0.1 only) ---
OLLAMA_BASE_URL = "http://127.0.0.1:11434"

# Context window per generate() call. Must be set explicitly: Ollama's default
# (~2-4k tokens) would silently truncate our system prompt + tool docs +
# observations on longer tasks. 8k fits the 1.5B models comfortably in 16 GB.
NUM_CTX = 8192

# --- Open-weight model registry ---
# Everything here runs locally through Ollama. New open-weight models can be
# added by appending to this registry — no other code changes required.
MODEL_REGISTRY = {
    "reasoning": {
        "model": "qwen2.5:1.5b",
        "capability": "general reasoning / summarization / drafting",
        "fallbacks": ["qwen2.5:0.5b"],
    },
    "coding": {
        "model": "qwen2.5-coder:1.5b",
        "capability": "code generation & repair",
        "fallbacks": ["qwen2.5:1.5b"],
    },
    "vision": {
        "model": "moondream",
        "capability": "image / drawing / scanned-page understanding",
        "fallbacks": [],
    },
    "embedding": {
        "model": "nomic-embed-text",
        "capability": "local embeddings for the knowledge base",
        "fallbacks": [],
    },
}

# --- Air-gap enforcement ---
STRICT_AIRGAP = True  # block any outbound socket that is not loopback
ALLOWED_HOSTS = {"127.0.0.1", "localhost", "::1", "0.0.0.0"}

AGENT_MAX_STEPS = 12
SANDBOX_TIMEOUT_S = 30
