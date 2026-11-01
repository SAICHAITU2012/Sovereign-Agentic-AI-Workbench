#!/usr/bin/env bash
#
# Start the Sovereign Workbench under macOS kernel-enforced network isolation.
#
# Every process in the tree — the uvicorn backend, the sandboxed Python
# children it spawns, tesseract, and any process launched by generated code —
# inherits the same kernel policy: loopback only. Anything else (DNS, external
# TCP, cloud APIs) is refused by the operating system itself. The in-app
# egress guard remains active as a second, logged layer on top.
#
# Usage:  scripts/run_airgapped.sh [port]     (default 8000)
#
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PROFILE="$ROOT/scripts/airgap/sovereign-airgap.sb"

if [[ ! -f "$PROFILE" ]]; then
    echo "error: Seatbelt profile not found: $PROFILE" >&2
    exit 1
fi

PORT="${1:-8000}"

echo "[air-gap] kernel policy : Seatbelt profile $PROFILE"
echo "[air-gap] allowed       : loopback only (UI :$PORT, Ollama :11434, local UNIX IPC)"
echo "[air-gap] denied by OS  : all DNS and external TCP/UDP, for this process tree"

# SOVEREIGN_AIRGAP_KERNEL labels the enforcement level for /api/health; the
# empirical proof comes from the sandbox-escape probes in
# POST /api/network/sandbox_escape_test, not from this label.
cd "$ROOT/backend"
exec /usr/bin/sandbox-exec -f "$PROFILE" \
    env SOVEREIGN_AIRGAP_KERNEL=seatbelt \
    python3 -m uvicorn app.main:app --host 127.0.0.1 --port "$PORT"
