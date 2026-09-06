#!/usr/bin/env python3
"""End-to-end timing of every demo flow, via the same WebSocket protocol the
UI uses. Records wall time per phase (routing, planning, each tool call,
final answer) and totals. Writes /tmp/wb_e2e.json."""
import asyncio
import json
import sys
import time
from datetime import datetime

import websockets

DEMOS = {
    "qa": {
        "task": "According to our SOPs and manuals in the knowledge base, what is the maximum allowed storage tank temperature and what procedure applies if it is exceeded?",
        "attachments": [],
    },
    "doc": {
        "task": "Read the scanned inspection report uploads/inspection_report.pdf, extract the key findings, check them against our SOPs in the knowledge base, and draft an approval note as a Word document.",
        "attachments": ["uploads/inspection_report.pdf"],
    },
    "code": {
        "task": "Write a Python program to calculate the overall thermal efficiency of a boiler given feedwater temperature 105 C, steam output 42 T/hr at 65 bar, and fuel consumption 3.1 T/hr with GCV 10200 kcal/kg. Show every calculation step and verify it runs correctly.",
        "attachments": [],
    },
    "vision": {
        "task": "Analyse the engineering drawing uploads/pid_sample.png: identify the main equipment, line labels and instruments you can see, and note anything that looks unusual.",
        "attachments": ["uploads/pid_sample.png"],
    },
    "office": {
        "task": "Search the knowledge base for the E-101 inspection history, then create an Excel workbook summarising the key facts and a short PowerPoint presentation of the findings.",
        "attachments": [],
    },
}

OUT = {}


def ts(ev):
    return datetime.fromisoformat(ev["ts"]).timestamp()


async def run_demo(ws, name):
    d = DEMOS[name]
    await ws.send(json.dumps(d))
    t_start = time.perf_counter()
    phases, tools, ok, deliverables = [], [], False, []
    prev_ts = None
    while True:
        try:
            ev = json.loads(await asyncio.wait_for(ws.recv(), timeout=420))
        except asyncio.TimeoutError:
            phases.append({"phase": "TIMEOUT", "s": 420})
            break
        t = ts(ev)
        gap = (t - prev_ts) if prev_ts else 0
        prev_ts = t
        et = ev["type"]
        if et in ("task_started",):
            continue
        if et == "routing":
            phases.append({"phase": f"routing -> {ev['task_type']}", "s": round(gap, 2)})
        elif et == "plan":
            phases.append({"phase": "planning (LLM)", "s": round(gap, 2)})
        elif et == "agent_thought":
            phases.append({"phase": f"think ({ev.get('source','')[:24]})", "s": round(gap, 2)})
        elif et == "tool_call":
            tools.append({"tool": ev["tool"], "start_gap": round(gap, 2)})
        elif et == "tool_result":
            if tools:
                tools[-1]["duration_s"] = round(gap, 2)
                tools[-1]["ok"] = ev["ok"]
            phases.append({"phase": f"tool: {ev['tool']}", "s": round(gap, 2)})
        elif et == "final":
            phases.append({"phase": "final answer (LLM)", "s": round(gap, 2)})
            deliverables = ev.get("deliverables", [])
            ok = True
            break
    OUT[name] = {
        "total_s": round(time.perf_counter() - t_start, 2),
        "completed": ok,
        "phases": [p for p in phases if p["s"] >= 0.05],
        "tools": tools,
        "deliverables": deliverables,
    }
    print(f"  {name}: {OUT[name]['total_s']}s completed={ok}", flush=True)


async def main():
    only = sys.argv[1:] or list(DEMOS)
    async with websockets.connect("ws://127.0.0.1:8000/ws/task") as ws:
        for name in only:
            print("running", name, flush=True)
            await run_demo(ws, name)
    with open("/tmp/wb_e2e.json", "w") as f:
        json.dump(OUT, f, indent=2)
    print(json.dumps(OUT, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
