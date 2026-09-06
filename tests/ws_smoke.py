"""End-to-end smoke test: drive the workbench over its WebSocket like the UI
does and print every event. Usage: python3 tests/ws_smoke.py <demo-key>"""
import asyncio
import json
import sys

import websockets

DEMOS = {
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
    "qa": {
        "task": "According to our SOPs and manuals in the knowledge base, what is the maximum allowed storage tank temperature and what procedure applies if it is exceeded?",
        "attachments": [],
    },
    "office": {
        "task": "Search the knowledge base for the E-101 inspection history, then create an Excel workbook summarising the key facts and a short PowerPoint presentation of the findings.",
        "attachments": [],
    },
}


async def main(key: str):
    async with websockets.connect("ws://127.0.0.1:8000/ws/task") as ws:
        await ws.send(json.dumps(DEMOS[key]))
        while True:
            ev = json.loads(await ws.recv())
            t = ev["type"]
            if t == "task_started":
                print(f"\n=== TASK STARTED: {ev['task'][:80]}...")
            elif t == "routing":
                print(f"[routing] {ev['task_type']} conf={ev['confidence']} models={ev['models']}")
            elif t == "plan":
                for i, s in enumerate(ev["steps"], 1):
                    print(f"[plan] {i}. {s}")
            elif t == "agent_thought":
                print(f"[think/{ev.get('source','')}] {ev['thought'][:140]}")
            elif t == "tool_call":
                a = dict(ev.get("args") or {})
                if "code" in a and len(str(a["code"])) > 120:
                    a["code"] = str(a["code"])[:120] + "…"
                print(f"[tool] {ev['tool']} {json.dumps(a)[:200]}")
            elif t == "tool_result":
                print(f"[result {'OK ' if ev['ok'] else 'ERR'}] {ev['summary']}")
            elif t == "final":
                print("\n=== FINAL ===")
                print(ev["answer"][:2500])
                print("deliverables:", ev["deliverables"])
                break
            elif t == "error":
                print("[ERROR]", ev.get("message"))
                break


if __name__ == "__main__":
    asyncio.run(main(sys.argv[1] if len(sys.argv) > 1 else "qa"))
