"""F.2 — the egress guard's install order is load-bearing.

`app.main` installs the socket monkey-patch (security.egress.install_egress_guard)
BEFORE importing any module that could open a socket (models/provider.py builds
an httpx client). If that line moves below a socket-capable import, the patch
may install too late and early connections would escape both the guard and the
event log. Two guards against regression:

1. STATIC  — parse main.py and assert the guard call precedes every other
   local `from .` import.
2. DYNAMIC — in a fresh interpreter, import app.main and assert that
   socket.socket.connect is the guarded replacement.
"""
import re
import subprocess
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1] / "backend"
MAIN_PY = BACKEND_DIR / "app" / "main.py"
sys.path.insert(0, str(BACKEND_DIR))  # for in-process app.* imports

GUARD_CALL = "egress.install_egress_guard()"

# Local imports allowed BEFORE the guard call, and why each is safe:
#   .security -> egress  : the module being configured (import is the point)
#   .config              : pulled in transitively by .security; it only
#                          defines constants and mkdirs (purity asserted below)
GUARD_OK_PRECEDING = ("from .config import", "from .security import egress")

SOCKET_CAPABLE = ("import socket", "import httpx", "import urllib", "import requests")


def test_guard_call_is_first_socket_capable_side_effect():
    """Static: no socket-capable local import may precede
    egress.install_egress_guard() in main.py."""
    source = MAIN_PY.read_text()
    lines = source.splitlines()
    guard_idx = next(i for i, l in enumerate(lines) if GUARD_CALL in l)
    preceding = [
        (i, l.strip()) for i, l in enumerate(lines)
        if i < guard_idx and re.match(r"^\s*(from\s+\.|import\s+app)", l)
    ]
    offenders = [(i, l) for i, l in preceding
                 if not l.startswith(GUARD_OK_PRECEDING)]
    assert not offenders, (
        "REGRESSION (F.2): an import precedes the egress-guard install and is "
        f"not on the known-safe allowlist. Offenders: {offenders}"
    )
    # nothing but comments/blank lines between the egress import and the call
    egress_idx = next(i for i, l in enumerate(lines)
                      if l.strip().startswith("from .security import egress"))
    between = [l for l in lines[egress_idx + 1:guard_idx]
               if l.strip() and not l.strip().startswith(("#", ";"))]
    assert not between, f"code injected between guard import and install: {between}"


def test_config_module_is_socket_free():
    """Purity: .config may precede the guard ONLY because it cannot open
    sockets. If this fails, remove it from GUARD_OK_PRECEDING instead of
    loosening this test."""
    config_src = (BACKEND_DIR / "app" / "config.py").read_text()
    bad = [m for m in SOCKET_CAPABLE if m in config_src]
    assert not bad, f"config.py became socket-capable ({bad}) — no longer safe to precede the guard"


def test_connect_is_patched_after_import():
    """Dynamic: in a fresh interpreter, importing app.main patches
    socket.socket.connect with the guarded replacement."""
    code = (
        "import socket\n"
        "import app.main\n"
        "fn = socket.socket.connect\n"
        "name = getattr(fn, '__name__', '')\n"
        "assert name == 'guarded_connect', f'unpatched: {name}'\n"
        "print('PATCHED')\n"
    )
    proc = subprocess.run(
        [sys.executable, "-c", code],
        cwd=str(BACKEND_DIR), capture_output=True, text=True, timeout=60,
    )
    assert proc.returncode == 0, (
        f"REGRESSION (F.2): egress guard not installed at import time.\n"
        f"stderr: {proc.stderr[-800:]}"
    )
    assert "PATCHED" in proc.stdout


# ------------------------------------------------------- F.1: honest pill --

def test_pill_is_not_hardcoded():
    """The UI must never claim enforcement it cannot show evidence for."""
    html = (BACKEND_DIR / "app" / "static" / "index.html").read_text()
    assert "AIR-GAP: ENFORCED" not in html, "hardcoded claim regressed into index.html"
    assert 'id="airgap-pill"' in html


def test_network_snapshot_exposes_kernel_and_verdict():
    """The pill's inputs exist: kernel_policy label + last battery verdict."""
    from app.security import egress
    snap = egress.snapshot()
    assert "kernel_policy" in snap and "last_escape_test" in snap
    egress.record_escape_test(True)
    last = egress.snapshot()["last_escape_test"]
    assert last and last["all_blocked"] is True and last["ts"]
    egress.record_escape_test(False)
    assert egress.snapshot()["last_escape_test"]["all_blocked"] is False
