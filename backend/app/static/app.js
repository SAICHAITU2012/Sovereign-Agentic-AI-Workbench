/* Sovereign Agentic AI Workbench — frontend logic */

const DEMOS = {
  doc: {
    task: "Read the scanned inspection report uploads/inspection_report.pdf, extract the key findings, check them against our SOPs in the knowledge base, and draft an approval note as a Word document.",
    attachments: ["uploads/inspection_report.pdf"],
  },
  code: {
    task: "Write a Python program to calculate the overall thermal efficiency of a boiler given feedwater temperature 105 C, steam output 42 T/hr at 65 bar, and fuel consumption 3.1 T/hr with GCV 10200 kcal/kg. Show every calculation step and verify it runs correctly.",
    attachments: [],
  },
  vision: {
    task: "Analyse the engineering drawing uploads/pid_sample.png: identify the main equipment, line labels and instruments you can see, and note anything that looks unusual.",
    attachments: ["uploads/pid_sample.png"],
  },
  qa: {
    task: "According to our SOPs and manuals in the knowledge base, what is the maximum allowed storage tank temperature and what procedure applies if it is exceeded?",
    attachments: [],
  },
  office: {
    task: "Create an Excel workbook summarising the E-101 inspection thickness readings (use the values from the knowledge base correspondence and inspection standards) and a short PowerPoint with the key findings.",
    attachments: [],
  },
};

let ws = null;
let attachments = [];
let busy = false;

const $ = (id) => document.getElementById(id);
const timeline = $("timeline");

// ------------------------------------------------------------- helpers ----
function esc(s) {
  return String(s ?? "").replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
}

function addEvent(type, cls, tagText, bodyHtml) {
  const div = document.createElement("div");
  div.className = "ev " + (cls || "");
  div.innerHTML = `
    <div class="ev-head"><span class="ev-tag ${cls || ""}">${esc(tagText)}</span></div>
    <div class="ev-body">${bodyHtml}</div>`;
  timeline.appendChild(div);
  div.scrollIntoView({ behavior: "smooth", block: "end" });
  return div;
}

// ---------------------------------------------------------- web socket ----
function ensureSocket() {
  return new Promise((resolve, reject) => {
    if (ws && ws.readyState === WebSocket.OPEN) return resolve(ws);
    const proto = location.protocol === "https:" ? "wss" : "ws";
    ws = new WebSocket(`${proto}://${location.host}/ws/task`);
    ws.onopen = () => resolve(ws);
    ws.onerror = (e) => reject(e);
    ws.onmessage = (m) => handleEvent(JSON.parse(m.data));
    ws.onclose = () => { ws = null; };
  });
}

function handleEvent(ev) {
  switch (ev.type) {
    case "task_started":
      addEvent(ev.type, "", "task started",
        `<div>${esc(ev.task)}</div>` +
        (ev.attachments?.length ? `<div class="muted">attachments: ${esc(ev.attachments.join(", "))}</div>` : ""));
      break;

    case "routing": {
      const models = Object.entries(ev.models || {})
        .map(([cap, m]) => `<div class="model-row"><span>${esc(cap)}</span><b>${esc(m || "n/a")}</b></div>`)
        .join("");
      const evidence = (ev.evidence || []).slice(0, 6).map((e) => `<li>${esc(e)}</li>`).join("");
      addEvent(ev.type, "routing", "model routing",
        `<div class="route-head">task type: ${esc(ev.task_type)} (confidence ${ev.confidence})</div>` +
        `<div class="muted">${esc(ev.description)}</div>` + models +
        (evidence ? `<details><summary>classification evidence</summary><ul class="evidence">${evidence}</ul></details>` : ""));
      renderRouting(ev);
      break;
    }

    case "plan": {
      const steps = (ev.steps || []).map((s) => `<li>${esc(s)}</li>`).join("");
      addEvent(ev.type, "plan", "plan",
        `<ol class="plan-steps">${steps}</ol>`);
      break;
    }

    case "agent_thought":
      addEvent(ev.type, "agent_thought", "thinking",
        `<div>${esc(ev.thought)}</div><div class="muted">source: ${esc(ev.source || "")}</div>`);
      break;

    case "tool_call": {
      const args = { ...(ev.args || {}) };
      if (args.code && args.code.length > 400) args.code = args.code.slice(0, 400) + "\n… (truncated)";
      addEvent(ev.type, "tool_call", `→ ${ev.tool}`,
        `<pre>${esc(JSON.stringify(args, null, 2))}</pre>`);
      break;
    }

    case "tool_result": {
      let inner = `<div class="summary">${ev.ok ? "✔" : "✘"} ${esc(ev.summary)}</div>`;
      const r = ev.result || {};
      if (r.hits?.length) {
        inner += r.hits.map((h) =>
          `<pre>【${esc(h.source)} · score ${h.score}】\n${esc(h.text.slice(0, 400))}</pre>`).join("");
      } else if (r.stdout !== undefined) {
        inner += `<details><summary>sandbox output</summary><pre>exit=${esc(r.exit_code)}  (${esc(r.elapsed_s ?? "?")}s)\n${esc(r.stdout)}${r.stderr ? "\nSTDERR:\n" + esc(r.stderr) : ""}</pre></details>`;
      } else if (r.answer) {
        inner += `<pre>${esc(String(r.answer).slice(0, 1200))}${r.model ? "\n[vision model: " + esc(r.model) + "]" : ""}</pre>`;
      } else if (r.text) {
        inner += `<details><summary>extracted text</summary><pre>${esc(String(r.text).slice(0, 1200))}</pre></details>`;
      } else if (r.deliverable) {
        inner += `<div class="muted">wrote ${esc(r.deliverable)}</div>`;
      }
      addEvent(ev.type, ev.ok ? "ok" : "fail", ev.tool, inner);
      if (r.deliverable) addDeliverable(r.deliverable);
      break;
    }

    case "final": {
      addEvent(ev.type, "final", "final answer", `<div class="answer">${esc(ev.answer)}</div>` +
        (ev.deliverables?.length
          ? `<div class="muted" style="margin-top:8px">deliverables: ${esc(ev.deliverables.join(", "))}</div>` : ""));
      setBusy(false);
      break;
    }

    case "error":
      addEvent(ev.type, "error", "error", `<div>${esc(ev.message)}</div>`);
      setBusy(false);
      break;
  }
  refreshNetwork();
}

// ------------------------------------------------------------- render -----
function renderRouting(ev) {
  const models = Object.entries(ev.models || {})
    .map(([cap, m]) => `<div class="model-row"><span>${esc(cap)}</span><b>${esc(m || "n/a")}</b></div>`)
    .join("");
  $("routing").innerHTML =
    `<div class="route-head">${esc(ev.task_type)} · ${ev.confidence}</div>` +
    `<div class="muted">${esc(ev.description)}</div>` + models;
}

function addDeliverable(path) {
  const list = $("deliverables");
  if (list.querySelector("li.muted")) list.innerHTML = "";
  if ([...list.querySelectorAll("a")].some((a) => a.dataset.path === path)) return;
  const a = document.createElement("a");
  a.dataset.path = path;
  a.href = `/api/download?path=${encodeURIComponent(path)}`;
  a.textContent = "📄 " + path;
  list.appendChild(a);
}

async function refreshNetwork() {
  try {
    const r = await fetch("/api/network");
    const s = await r.json();
    $("net-blocked").textContent = s.counters.external_blocked;
    $("net-attempts").textContent = s.counters.outbound_attempts;
    $("net-local").textContent = s.counters.local_allowed;
    $("net-events").innerHTML = (s.events || [])
      .slice().reverse().slice(0, 30)
      .map((e) => `<div class="${e.verdict.includes("BLOCK") ? "blocked" : ""}">${esc(e.time.slice(11, 19))} → ${esc(e.dest)}:${esc(e.port ?? "")} · ${esc(e.verdict)}</div>`)
      .join("");
  } catch {}
}

async function refreshEngine() {
  try {
    const r = await fetch("/api/models");
    const s = await r.json();
    const pill = $("engine-pill");
    pill.textContent = s.online ? "OLLAMA ONLINE · LOCAL" : "OLLAMA OFFLINE";
    pill.className = "pill " + (s.online ? "ok" : "warn");
    const caps = Object.entries(s.capabilities || {})
      .map(([cap, c]) => `<div class="cap"><span>${esc(cap)} — ${esc(c.capability)}</span><span class="${c.ready ? "ready" : "missing"}">${esc(c.resolved || "not installed")}</span></div>`)
      .join("");
    $("engine").innerHTML =
      `<div class="muted">engine: ${esc(s.engine)} · installed: ${s.installed.length} model(s)</div>` + caps;
  } catch {}
}

async function refreshKB() {
  try {
    const r = await fetch("/api/health");
    const s = await r.json();
    $("kb-stats").textContent =
      `${s.kb.chunks} chunks indexed from ${s.kb.sources.length} source(s): ${s.kb.sources.join(", ") || "—"}`;
  } catch {}
}

function setBusy(b) {
  busy = b;
  $("run-btn").disabled = b;
  $("run-btn").textContent = b ? "⏳ agent working…" : "▶ Run Task";
}

// -------------------------------------------------------------- upload ----
async function uploadFiles(files, endpoint, chipContainer) {
  for (const f of files) {
    const fd = new FormData();
    fd.append("file", f);
    const r = await fetch(endpoint, { method: "POST", body: fd });
    const j = await r.json();
    if (chipContainer) {
      const chip = document.createElement("span");
      chip.className = "chip";
      chip.textContent = j.path;
      chipContainer.appendChild(chip);
    }
  }
}

$("file-input").addEventListener("change", async (e) => {
  await uploadFiles(e.target.files, "/api/upload", $("attachment-chips"));
  attachments = [...$("attachment-chips").querySelectorAll(".chip")].map((c) => c.textContent);
  e.target.value = "";
});

$("kb-input").addEventListener("change", async (e) => {
  await uploadFiles(e.target.files, "/api/kb/upload", null);
  await $("reindex-btn").click();
  e.target.value = "";
});

$("reindex-btn").addEventListener("click", async () => {
  $("kb-stats").textContent = "re-indexing…";
  await fetch("/api/kb/reindex", { method: "POST" });
  refreshKB();
});

// ----------------------------------------------------------------- run ----
async function runTask(task, attach) {
  if (busy) return;
  setBusy(true);
  timeline.innerHTML = "";
  try {
    const socket = await ensureSocket();
    socket.send(JSON.stringify({ task, attachments: attach }));
  } catch (err) {
    addEvent("error", "error", "error", "Could not connect to the local server.");
    setBusy(false);
  }
}

$("run-btn").addEventListener("click", () => {
  const t = $("task-input").value.trim();
  if (!t) { $("task-input").focus(); return; }
  runTask(t, attachments);
});

document.querySelectorAll("button.demo").forEach((b) => {
  b.addEventListener("click", () => {
    const demo = DEMOS[b.dataset.demo];
    $("task-input").value = demo.task;
    $("attachment-chips").innerHTML = "";
    demo.attachments.forEach((p) => {
      const chip = document.createElement("span");
      chip.className = "chip";
      chip.textContent = p;
      $("attachment-chips").appendChild(chip);
    });
    attachments = [...demo.attachments];
    runTask(demo.task, attachments);
  });
});

$("selftest-btn").addEventListener("click", async () => {
  const r = await fetch("/api/network/selftest", { method: "POST" });
  const j = await r.json();
  addEvent("error", j.blocked ? "ok" : "error", "air-gap self-test",
    `<div>${j.blocked ? "✔ outbound attempt BLOCKED by the egress guard" : "✘ outbound request was NOT blocked!"}</div>` +
    `<pre>${esc(j.detail)}</pre>`);
  refreshNetwork();
});

// ---------------------------------------------------------------- init ----
refreshEngine();
refreshNetwork();
refreshKB();
setInterval(refreshNetwork, 4000);
