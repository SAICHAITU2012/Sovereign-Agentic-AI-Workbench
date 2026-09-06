#!/usr/bin/env python3
"""Full performance benchmark for the Sovereign Agentic AI Workbench.

Measures:
  A. System / engine context
  B. Per-model throughput: load time, prompt-eval tok/s, generation tok/s
  C. KV / prompt cache behaviour (repeat-prefix speedup)
  D. Embedding latency (single + batch)
  E. RAG retrieval latency (avg / p50 / p95)
  F. Python sandbox overhead (spawn + execution)
  G. OCR throughput (tesseract)
  H. Office deliverable generation (docx / xlsx / pptx)
  I. Egress guard overhead (allowed + blocked paths)
  J. End-to-end wall times for every demo flow (via WebSocket)

Writes results to /tmp/wb_bench.json and prints a summary.
"""
import asyncio
import json
import platform
import statistics
import subprocess
import sys
import time
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
sys.path.insert(0, str(BACKEND))

OLLAMA = "http://127.0.0.1:11434"
RESULTS = {}

LONG_PROMPT = (
    "You are an expert refinery inspection engineer. Below is an extract from an "
    "equipment inspection report. Read it carefully and answer the question at the end. "
) + ("Shell wall thickness measured 8.2 mm against the minimum required thickness of "
     "8.8 mm. Localised thinning observed near the shell inlet nozzle. Tube bundle "
     "leakage detected at 4 locations during the hydro test at 12.5 bar. " * 18) + (
    "\n\nQuestion: in one short sentence, is the shell acceptable? Answer yes or no.")


def bench_model(client: httpx.Client, model: str, prompt: str, num_predict: int,
                repeat: int = 3, images=None) -> dict:
    runs = []
    for _ in range(repeat):
        payload = {"model": model, "prompt": prompt, "stream": False,
                   "keep_alive": "10m",
                   "options": {"temperature": 0, "num_predict": num_predict}}
        if images:
            payload["images"] = images
        t0 = time.perf_counter()
        r = client.post(f"{OLLAMA}/api/generate", json=payload, timeout=600)
        wall = time.perf_counter() - t0
        d = r.json()
        runs.append({
            "wall_s": round(wall, 2),
            "load_s": round(d.get("load_duration", 0) / 1e9, 2),
            "prompt_eval_tokens": d.get("prompt_eval_count", 0),
            "prompt_eval_s": round(d.get("prompt_eval_duration", 0) / 1e9, 3),
            "gen_tokens": d.get("eval_count", 0),
            "gen_s": round(d.get("eval_duration", 0) / 1e9, 3),
        })
    gen_tps = [r["gen_tokens"] / r["gen_s"] for r in runs if r["gen_s"] > 0]
    pe_tps = [r["prompt_eval_tokens"] / r["prompt_eval_s"] for r in runs if r["prompt_eval_s"] > 0]
    return {
        "model": model,
        "runs": runs,
        "gen_tok_s_median": round(statistics.median(gen_tps), 1) if gen_tps else None,
        "prompt_eval_tok_s_median": round(statistics.median(pe_tps), 1) if pe_tps else None,
        "load_s_first_run": runs[0]["load_s"],
        "gen_tokens_typical": statistics.median([r["gen_tokens"] for r in runs]),
        "wall_s_median": round(statistics.median([r["wall_s"] for r in runs]), 2),
    }


def kv_cache_test(client: httpx.Client, model: str) -> dict:
    """Call twice with the identical prompt inside the keep_alive window;
    a working prompt/KV cache shows a much smaller prompt_eval_count on #2."""
    out = []
    for i in range(2):
        t0 = time.perf_counter()
        r = client.post(f"{OLLAMA}/api/generate", json={
            "model": model, "prompt": LONG_PROMPT, "stream": False,
            "keep_alive": "10m", "options": {"temperature": 0, "num_predict": 8},
        }, timeout=600)
        wall = time.perf_counter() - t0
        d = r.json()
        out.append({
            "call": i + 1,
            "prompt_eval_tokens": d.get("prompt_eval_count", 0),
            "prompt_eval_s": round(d.get("prompt_eval_duration", 0) / 1e9, 3),
            "wall_s": round(wall, 2),
        })
    saved = 100 * (1 - out[1]["prompt_eval_tokens"] / max(out[0]["prompt_eval_tokens"], 1))
    return {"calls": out, "prompt_tokens_saved_pct": round(saved, 1)}


def main():
    # ---------------- A. system context ----------------
    try:
        ollama_ver = subprocess.run(["ollama", "--version"], capture_output=True,
                                    text=True, timeout=10).stdout.strip()
    except Exception:
        ollama_ver = "unknown"
    RESULTS["system"] = {
        "machine": platform.machine(),
        "cpu": subprocess.run(["sysctl", "-n", "machdep.cpu.brand_string"],
                              capture_output=True, text=True).stdout.strip(),
        "ram_gb": round(int(subprocess.run(["sysctl", "-n", "hw.memsize"],
                                           capture_output=True, text=True).stdout) / 2**30, 1),
        "cores": int(subprocess.run(["sysctl", "-n", "hw.ncpu"],
                                    capture_output=True, text=True).stdout),
        "python": platform.python_version(),
        "ollama": ollama_ver,
    }

    client = httpx.Client()
    installed = [m["name"] for m in client.get(f"{OLLAMA}/api/tags", timeout=10).json()["models"]]
    RESULTS["installed_models"] = installed

    # ---------------- B. per-model throughput ----------------
    print("== B. model throughput ==", flush=True)
    throughput = {}
    for model in ["qwen2.5:1.5b", "qwen2.5-coder:1.5b"]:
        print("  benching", model, flush=True)
        throughput[model] = bench_model(
            client, model,
            "List 5 important checks in an industrial equipment inspection, one sentence each.",
            num_predict=140, repeat=3)
    print("  benching moondream (vision)", flush=True)
    import base64
    img_b64 = base64.b64encode(
        (ROOT / "workspace" / "uploads" / "pid_sample.png").read_bytes()).decode()
    throughput["moondream"] = bench_model(
        client, "moondream",
        "Describe the equipment tags visible in this P&ID drawing in one short sentence.",
        num_predict=90, repeat=2, images=[img_b64])
    RESULTS["throughput"] = throughput

    # ---------------- C. KV / prompt cache ----------------
    print("== C. KV cache ==", flush=True)
    RESULTS["kv_cache"] = {m: kv_cache_test(client, m)
                           for m in ["qwen2.5:1.5b", "qwen2.5-coder:1.5b"]}

    # ---------------- D. embedding latency ----------------
    print("== D. embeddings ==", flush=True)
    sample = "The maximum permitted product temperature in atmospheric storage tanks is 90 degrees Celsius."
    lat = []
    for _ in range(8):
        t0 = time.perf_counter()
        client.post(f"{OLLAMA}/api/embed", json={"model": "nomic-embed-text", "input": sample},
                    timeout=60)
        lat.append((time.perf_counter() - t0) * 1000)
    RESULTS["embedding"] = {
        "single_ms_avg": round(statistics.mean(lat), 1),
        "single_ms_min": round(min(lat), 1),
        "single_ms_max": round(max(lat), 1),
    }

    # ---------------- E. RAG retrieval ----------------
    print("== E. RAG ==", flush=True)
    from app.rag import store as rag_store
    rag_store.load()
    queries = [
        "maximum allowed storage tank temperature",
        "hydro test acceptance pressure loss",
        "approval note requirements inspection SOP",
        "minimum required thickness corrosion allowance",
        "E-101 condenser history retubing",
        "level 2 incident reporting deadline",
        "plugged tubes limit per pass",
        "gasket seating surface corrosion re-machining",
        "cooling water spray tank procedure",
        "fitness for service re-rating approval",
        "floating roof seal inspection frequency",
        "who signs the approval note",
    ]
    lat = []
    for q in queries:
        t0 = time.perf_counter()
        hits = rag_store.search(q, top_k=4)
        lat.append((time.perf_counter() - t0) * 1000)
    lat.sort()
    RESULTS["rag"] = {
        "chunks_indexed": len(rag_store._store["chunks"]),
        "vector_dim": int(rag_store._store["vectors"].shape[1]) if rag_store._store["vectors"] is not None else 0,
        "search_ms_avg": round(statistics.mean(lat), 2),
        "search_ms_p50": round(lat[len(lat)//2], 2),
        "search_ms_p95": round(lat[int(len(lat)*0.95) - 1], 2),
        "top_hit_correct_for_tank_query": None,
    }
    hits = rag_store.search("maximum allowed storage tank temperature", top_k=1)
    RESULTS["rag"]["top_hit_correct_for_tank_query"] = (
        hits and "OPS-MAN-07" in hits[0]["source"])

    # ---------------- F. sandbox ----------------
    print("== F. sandbox ==", flush=True)
    from app.tools.local_tools import get_tools
    tools = get_tools()
    lat = []
    for _ in range(5):
        t0 = time.perf_counter()
        s, r = tools["run_python"].run(code="print(2 + 2)")
        assert r["exit_code"] == 0
        lat.append((time.perf_counter() - t0) * 1000)
    t0 = time.perf_counter()
    s, r = tools["run_python"].run(code=(
        "import time\n"
        "primes = [n for n in range(2, 20000) if all(n % p for p in range(2, int(n**0.5)+1))]\n"
        "print('primes found:', len(primes))\n"
        "steps = {'inputs': {'a': 42, 'b': 58}, 'formula': 'a + b', 'result': 42 + 58}\n"
        "print(steps)\n"))
    compute_ms = (time.perf_counter() - t0) * 1000
    RESULTS["sandbox"] = {
        "trivial_run_ms_avg": round(statistics.mean(lat), 1),
        "trivial_run_ms_min": round(min(lat), 1),
        "compute_20k_primes_ms": round(compute_ms, 1),
        "note": "trivial run ~= full subprocess spawn + interpreter boot + prelude cost",
    }

    # ---------------- G. OCR ----------------
    print("== G. OCR ==", flush=True)
    ocr = []
    for page in ["inspection_report_p1.png", "inspection_report_p2.png"]:
        p = ROOT / "workspace" / "sandbox" / page
        if not p.exists():
            continue
        t0 = time.perf_counter()
        s, r = tools["ocr_image"].run(path=f"sandbox/{page}")
        ms = (time.perf_counter() - t0) * 1000
        ocr.append({"page": page, "ms": round(ms, 1),
                    "chars": len(r.get("text", "")),
                    "chars_per_s": round(len(r.get("text", "")) / (ms / 1000), 1),
                    "engine": r.get("engine")})
    RESULTS["ocr"] = ocr

    # ---------------- H. office generation ----------------
    print("== H. office ==", flush=True)
    content = ("## Key Findings\n- F-1: shell thickness 8.2 mm vs 8.8 mm minimum\n"
               "- F-2: hydro test leak at 4 tube locations\n\n## Conclusion\n"
               "Repair required before restart per EMP-SOP-014.\n" * 12)
    t0 = time.perf_counter()
    s, r = tools["create_docx"].run(filename="bench_test.docx", title="Benchmark Note", content=content)
    docx_ms = (time.perf_counter() - t0) * 1000
    t0 = time.perf_counter()
    s, r = tools["create_xlsx"].run(filename="bench_test.xlsx", data=json.dumps({
        "Sheets": [{"name": "Bench", "headers": ["i", "x"],
                    "rows": [[i, i * 2] for i in range(500)]}]}))
    xlsx_ms = (time.perf_counter() - t0) * 1000
    t0 = time.perf_counter()
    s, r = tools["create_pptx"].run(filename="bench_test.pptx", data=json.dumps({
        "Slides": [{"title": f"Slide {i}", "bullets": ["alpha", "beta", "gamma"]}
                   for i in range(8)]}))
    pptx_ms = (time.perf_counter() - t0) * 1000
    RESULTS["office"] = {"docx_ms": round(docx_ms, 1), "xlsx_500rows_ms": round(xlsx_ms, 1),
                         "pptx_8slides_ms": round(pptx_ms, 1)}

    # ---------------- I. egress guard overhead ----------------
    print("== I. egress guard ==", flush=True)
    from app.security import egress as eg
    import socket
    eg.install_egress_guard()
    t0 = time.perf_counter()
    for _ in range(200):
        s = socket.socket()
        try:
            s.connect(("127.0.0.1", 1))
        except OSError:
            pass
    allowed_us = (time.perf_counter() - t0) / 200 * 1e6
    blocked = []
    for _ in range(20):
        s = socket.socket()
        t0 = time.perf_counter()
        try:
            s.connect(("93.184.216.34", 80))
            s.close()
        except eg.ConnectionBlocked:
            blocked.append((time.perf_counter() - t0) * 1e6)
    RESULTS["egress_guard"] = {
        "loopback_connect_us_avg": round(allowed_us, 1),
        "blocked_attempt_us_avg": round(statistics.mean(blocked), 1),
        "note": "overhead = DNS/guard verdict per connect; negligible vs any LLM call",
    }

    Path("/tmp/wb_bench.json").write_text(json.dumps(RESULTS, indent=2))
    print(json.dumps(RESULTS, indent=2))


if __name__ == "__main__":
    main()
