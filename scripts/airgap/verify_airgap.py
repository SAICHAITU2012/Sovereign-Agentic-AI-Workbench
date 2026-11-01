#!/usr/bin/env python3
"""Air-gap verification auditor for the Sovereign Workbench.

Run this while the workbench is up under scripts/run_airgapped.sh. It
executes an adversarial battery — through the app's own API and directly
against the kernel profile — and writes a judge-inspectable evidence
report:

    evidence/airgap_report_<UTC timestamp>.md   human-readable, commit this
    evidence/airgap_report_<UTC timestamp>.json  raw results

Stdlib only. Exit code 0 iff every check passes.

Usage:  python3 scripts/airgap/verify_airgap.py [--base-url http://127.0.0.1:8000]
"""
import argparse
import json
import subprocess
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PROFILE = ROOT / "scripts" / "airgap" / "sovereign-airgap.sb"
SANDBOX_EXEC = "/usr/bin/sandbox-exec"
CURL = "/usr/bin/curl"


def http(base_url: str, method: str, path: str, body: dict | None = None,
         timeout: float = 90.0):
    req = urllib.request.Request(
        base_url + path,
        data=json.dumps(body).encode() if body is not None else None,
        headers={"Content-Type": "application/json"} if body else {},
        method=method)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.status, json.loads(resp.read())


def sb_curl(args: list[str], timeout: float = 30.0) -> dict:
    """Run curl under the Seatbelt profile; never leak the auditor's own net."""
    try:
        proc = subprocess.run([SANDBOX_EXEC, "-f", str(PROFILE), CURL, *args],
                              capture_output=True, text=True, timeout=timeout)
        return {"exit": proc.returncode, "stdout": proc.stdout[-500:],
                "stderr": proc.stderr[-500:]}
    except subprocess.TimeoutExpired:
        return {"exit": -9, "stdout": "", "stderr": "timeout"}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base-url", default="http://127.0.0.1:8000")
    args = ap.parse_args()
    base = args.base_url.rstrip("/")

    checks: list[dict] = []

    def record(cid: str, title: str, passed: bool, detail: dict):
        checks.append({"id": cid, "title": title, "passed": bool(passed),
                       "detail": detail})
        print(f"  [{'PASS' if passed else 'FAIL'}] {cid}  {title}")

    run_ts = datetime.now(timezone.utc)

    # ---- T0: the app is up -------------------------------------------------
    print(f"Auditing {base} …")
    try:
        status, health = http(base, "GET", "/api/health", timeout=15)
        record("T0", "workbench healthy under kernel policy",
               status == 200 and health.get("status") == "ok",
               {"http": status, "kernel_policy": health.get("egress", {})
                .get("strict_airgap"), "models": health.get("engine")})
    except Exception as e:
        record("T0", "workbench healthy under kernel policy", False,
               {"error": f"{e.__class__.__name__}: {e}"})
        print("\nIs the server running under scripts/run_airgapped.sh?")
        return finish(checks, run_ts, 1)

    # ---- T1: the kernel profile itself, independent of the app ------------
    ext = sb_curl(["-sS", "-m", "8", "-o", "/dev/null",
                   "https://example.com"])
    record("T1a", "kernel denies external HTTPS from any process in the tree",
           ext["exit"] != 0, ext)

    loop = sb_curl(["-s", "-m", "8", "-o", "/dev/null",
                    "-w", "%{http_code}", "http://127.0.0.1:11434/api/tags"])
    record("T1b", "kernel still allows loopback (Ollama reachable)",
           loop["stdout"].strip() == "200", loop)

    # ---- T2: the app-level egress guard (Python layer) --------------------
    _, selftest = http(base, "POST", "/api/network/selftest")
    record("T2", "app egress guard blocks outbound HTTP attempt (logged)",
           selftest.get("blocked") is True, selftest)

    # ---- T3: sandbox-escape battery through the REAL run_python tool ------
    _, esc = http(base, "POST", "/api/network/sandbox_escape_test")
    record("T3", "sandbox escape attempts (raw _socket / child curl / "
           "ctypes syscalls) all blocked",
           esc.get("all_blocked") is True,
           {"kernel_policy": esc.get("kernel_policy"),
            "positive_control": esc.get("positive_control"),
            "probes": [{"name": p["name"], "vector": p["vector"],
                        "blocked": p["blocked"],
                        "enforced_by": p["enforced_by"],
                        "exit_code": p["exit_code"],
                        "stdout": p["stdout"],
                        "stderr": p["stderr"]}
                       for p in esc.get("probes", [])]})

    # ---- T4: REAL local inference while the kernel policy is active -------
    payload = json.dumps({"model": "qwen2.5:1.5b", "stream": False,
                          "options": {"num_predict": 8},
                          "prompt": "Reply with exactly one word: sovereign"}).encode()
    try:
        req = urllib.request.Request("http://127.0.0.1:11434/api/generate",
                                     data=payload,
                                     headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=60) as resp:
            gen = json.loads(resp.read())
        record("T4", "local LLM inference completes while air-gapped",
               bool(gen.get("response")), {"model": gen.get("model"),
                                           "response": gen.get("response", "")[:80]})
    except Exception as e:
        record("T4", "local LLM inference completes while air-gapped", False,
               {"error": f"{e.__class__.__name__}: {e}"})

    return finish(checks, run_ts, 0 if all(c["passed"] for c in checks) else 1)


def finish(checks: list[dict], run_ts, code: int) -> int:
    out_dir = ROOT / "evidence"
    out_dir.mkdir(exist_ok=True)
    stamp = run_ts.strftime("%Y%m%dT%H%M%SZ")
    md = out_dir / f"airgap_report_{stamp}.md"
    js = out_dir / f"airgap_report_{stamp}.json"
    js.write_text(json.dumps({"run": run_ts.isoformat(), "platform": sys.platform,
                              "profile": str(PROFILE), "checks": checks}, indent=2))
    lines = [
        "# Air-Gap Evidence Report",
        "",
        f"- **Run (UTC)**: {run_ts.isoformat()}",
        f"- **Platform**: {sys.platform} · kernel policy: macOS Seatbelt (`{PROFILE.name}`)",
        f"- **Result**: {'ALL CHECKS PASSED' if code == 0 else 'FAILURES PRESENT'}"
        f" ({sum(c['passed'] for c in checks)}/{len(checks)})",
        "",
        "| # | Check | Verdict |",
        "|---|-------|---------|",
    ]
    for c in checks:
        lines.append(f"| {c['id']} | {c['title']} | {'✅ PASS' if c['passed'] else '❌ FAIL'} |")
    lines += ["",
              "Reproduce with: `scripts/run_airgapped.sh` in one terminal, then",
              "`python3 scripts/airgap/verify_airgap.py` in another.",
              "", "## Raw check details", ""]
    for c in checks:
        lines.append(f"### {c['id']} — {c['title']}")
        lines.append("```json")
        lines.append(json.dumps(c["detail"], indent=2)[:3000])
        lines.append("```")
    md.write_text("\n".join(lines) + "\n")

    print(f"\nEvidence written:\n  {md}\n  {js}")
    print("RESULT:", "ALL CHECKS PASSED" if code == 0 else "FAILURES PRESENT")
    return code


if __name__ == "__main__":
    sys.exit(main())
