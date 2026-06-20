"""Local HTML dashboard for persisted advisor runs."""

from __future__ import annotations

import functools
import http.server
import json
import socketserver
from pathlib import Path
from typing import Any, Dict, List, Optional

from packages.harness.artifacts import write_text
from packages.harness.database import RunDatabase


DEFAULT_UI_PATH = Path("runs") / "ui" / "index.html"
DEFAULT_MAX_TEXT_CHARS = 20000


def build_dashboard_payload(
    root: Path,
    *,
    run_id: Optional[str] = None,
    max_text_chars: int = DEFAULT_MAX_TEXT_CHARS,
) -> Dict[str, Any]:
    """Build the JSON payload consumed by the static dashboard."""
    db = RunDatabase.for_root(root)
    runs = db.list_runs()
    run_ids = [run["run_id"] for run in runs]
    selected_run_id = run_id if run_id in run_ids else (run_ids[0] if run_ids else None)
    payloads: Dict[str, Any] = {}
    for item in runs:
        item_run_id = str(item["run_id"])
        payloads[item_run_id] = _truncate_payload(db.run_payload(item_run_id), max_text_chars=max_text_chars)
    return {
        "workspace": str(root),
        "selected_run_id": selected_run_id,
        "runs": runs,
        "payloads": payloads,
    }


def render_dashboard(
    root: Path,
    *,
    output_path: Optional[Path] = None,
    run_id: Optional[str] = None,
    max_text_chars: int = DEFAULT_MAX_TEXT_CHARS,
) -> Path:
    """Render a local dashboard HTML file and return its path."""
    target = output_path or (root / DEFAULT_UI_PATH)
    if not target.is_absolute():
        target = root / target
    payload = build_dashboard_payload(root, run_id=run_id, max_text_chars=max_text_chars)
    write_text(target, _render_html(payload))
    return target


def dashboard_url(output_path: Path, *, port: int) -> str:
    return "http://127.0.0.1:{}/{}".format(port, output_path.name)


def serve_dashboard(output_path: Path, *, port: int) -> None:
    """Serve a rendered dashboard and block until interrupted."""
    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(output_path.parent))
    with socketserver.ThreadingTCPServer(("127.0.0.1", port), handler) as httpd:
        httpd.serve_forever()


def _truncate_payload(payload: Dict[str, Any], *, max_text_chars: int) -> Dict[str, Any]:
    if max_text_chars <= 0:
        return payload
    return _truncate_value(payload, max_text_chars=max_text_chars)


def _truncate_value(value: Any, *, max_text_chars: int) -> Any:
    if isinstance(value, str):
        if len(value) <= max_text_chars:
            return value
        omitted = len(value) - max_text_chars
        return "{}\n\n[truncated {} chars]".format(value[:max_text_chars], omitted)
    if isinstance(value, list):
        return [_truncate_value(item, max_text_chars=max_text_chars) for item in value]
    if isinstance(value, dict):
        return {key: _truncate_value(item, max_text_chars=max_text_chars) for key, item in value.items()}
    return value


def _render_html(payload: Dict[str, Any]) -> str:
    return HTML_TEMPLATE.replace("__DASHBOARD_DATA__", _script_json(payload))


def _script_json(payload: Dict[str, Any]) -> str:
    text = json.dumps(payload, sort_keys=True)
    return text.replace("&", "\\u0026").replace("<", "\\u003c").replace(">", "\\u003e")


HTML_TEMPLATE = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Advisor Runs</title>
  <style>
    :root {
      color-scheme: light;
      --bg: #f6f7f2;
      --panel: #ffffff;
      --ink: #18221d;
      --muted: #5f6f68;
      --line: #d8dfd8;
      --accent: #107767;
      --accent-bg: #e4f2ee;
      --warn: #9d3e2f;
      --shadow: 0 1px 2px rgba(24, 34, 29, 0.08);
    }

    * {
      box-sizing: border-box;
    }

    body {
      margin: 0;
      background: var(--bg);
      color: var(--ink);
      font: 14px/1.45 ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
    }

    .shell {
      min-height: 100vh;
      display: grid;
      grid-template-rows: auto 1fr;
    }

    header {
      background: var(--panel);
      border-bottom: 1px solid var(--line);
      padding: 14px 18px 12px;
    }

    .header-row {
      display: flex;
      align-items: baseline;
      justify-content: space-between;
      gap: 16px;
    }

    h1 {
      margin: 0;
      font-size: 20px;
      font-weight: 700;
      letter-spacing: 0;
    }

    .workspace {
      color: var(--muted);
      font-size: 12px;
      white-space: nowrap;
      overflow: hidden;
      text-overflow: ellipsis;
      max-width: 58vw;
    }

    .kpis {
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
      margin-top: 12px;
    }

    .kpi {
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 6px 9px;
      background: #fbfcf8;
      color: var(--muted);
      min-width: 112px;
    }

    .kpi strong {
      display: block;
      color: var(--ink);
      font-size: 16px;
      font-weight: 700;
    }

    main {
      display: grid;
      grid-template-columns: minmax(300px, 370px) 1fr;
      min-height: 0;
    }

    .sidebar {
      min-height: 0;
      overflow: auto;
      background: #fbfcf8;
      border-right: 1px solid var(--line);
    }

    .filters {
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 10px;
      padding: 14px;
      border-bottom: 1px solid var(--line);
    }

    label {
      color: var(--muted);
      font-size: 12px;
      font-weight: 650;
    }

    input,
    select,
    button {
      font: inherit;
    }

    input,
    select {
      width: 100%;
      margin-top: 4px;
      border: 1px solid var(--line);
      border-radius: 6px;
      background: var(--panel);
      color: var(--ink);
      padding: 8px 9px;
      min-height: 36px;
    }

    .filter-wide {
      grid-column: 1 / -1;
    }

    .run-list {
      display: grid;
      gap: 8px;
      padding: 12px;
    }

    .run-row {
      display: grid;
      gap: 5px;
      width: 100%;
      border: 1px solid var(--line);
      border-radius: 8px;
      background: var(--panel);
      color: var(--ink);
      padding: 10px;
      text-align: left;
      cursor: pointer;
      box-shadow: var(--shadow);
    }

    .run-row:hover,
    .run-row.active {
      border-color: var(--accent);
      background: var(--accent-bg);
    }

    .run-id {
      font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
      font-size: 12px;
      font-weight: 700;
      overflow-wrap: anywhere;
    }

    .run-task {
      color: var(--muted);
      min-height: 20px;
      overflow-wrap: anywhere;
    }

    .badges {
      display: flex;
      flex-wrap: wrap;
      gap: 5px;
    }

    .badge {
      border: 1px solid var(--line);
      border-radius: 999px;
      background: #f4f5ef;
      color: var(--muted);
      padding: 2px 7px;
      font-size: 12px;
    }

    .badge.warn {
      border-color: #dfb5aa;
      background: #faece8;
      color: var(--warn);
    }

    .content {
      min-width: 0;
      overflow: auto;
      padding: 18px;
    }

    .empty {
      border: 1px dashed var(--line);
      border-radius: 8px;
      padding: 24px;
      color: var(--muted);
      background: var(--panel);
    }

    .detail-grid {
      display: grid;
      grid-template-columns: minmax(0, 1.05fr) minmax(320px, 0.95fr);
      gap: 16px;
      align-items: start;
    }

    .panel {
      border: 1px solid var(--line);
      border-radius: 8px;
      background: var(--panel);
      box-shadow: var(--shadow);
      overflow: hidden;
    }

    .panel h2 {
      margin: 0;
      padding: 12px 14px;
      border-bottom: 1px solid var(--line);
      font-size: 15px;
      letter-spacing: 0;
    }

    .summary-table {
      width: 100%;
      border-collapse: collapse;
    }

    .summary-table th,
    .summary-table td {
      border-bottom: 1px solid var(--line);
      padding: 8px 12px;
      text-align: left;
      vertical-align: top;
    }

    .summary-table th {
      width: 150px;
      color: var(--muted);
      font-size: 12px;
      font-weight: 650;
    }

    .timeline {
      list-style: none;
      margin: 0;
      padding: 0;
    }

    .timeline-item {
      padding: 12px 14px;
      border-bottom: 1px solid var(--line);
    }

    .timeline-item:last-child,
    .summary-table tr:last-child th,
    .summary-table tr:last-child td {
      border-bottom: 0;
    }

    .event-head {
      display: flex;
      justify-content: space-between;
      gap: 10px;
      align-items: baseline;
      margin-bottom: 8px;
    }

    .event-type {
      font-weight: 700;
    }

    .muted {
      color: var(--muted);
      font-size: 12px;
    }

    .field {
      display: grid;
      gap: 3px;
      margin-top: 7px;
    }

    .field-label {
      color: var(--muted);
      font-size: 12px;
      font-weight: 650;
    }

    .field-value {
      white-space: pre-wrap;
      overflow-wrap: anywhere;
    }

    details.agent-turn {
      border-top: 1px solid var(--line);
    }

    details.agent-turn:first-of-type {
      border-top: 0;
    }

    details.agent-turn summary {
      cursor: pointer;
      padding: 11px 14px;
      font-weight: 700;
    }

    .raw-block {
      border-top: 1px solid var(--line);
      padding: 10px 14px 12px;
    }

    .raw-block h3 {
      margin: 0 0 6px;
      color: var(--muted);
      font-size: 12px;
      letter-spacing: 0;
    }

    pre {
      margin: 0;
      max-height: 360px;
      overflow: auto;
      border: 1px solid var(--line);
      border-radius: 6px;
      background: #f9faf6;
      padding: 10px;
      color: #1f2823;
      font: 12px/1.45 ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
      white-space: pre-wrap;
      overflow-wrap: anywhere;
    }

    @media (max-width: 900px) {
      .workspace {
        max-width: 100%;
      }

      .header-row {
        display: grid;
      }

      main,
      .detail-grid {
        grid-template-columns: 1fr;
      }

      .sidebar {
        border-right: 0;
        border-bottom: 1px solid var(--line);
      }
    }
  </style>
</head>
<body>
  <div class="shell">
    <header>
      <div class="header-row">
        <h1>Advisor Runs</h1>
        <div id="workspace" class="workspace"></div>
      </div>
      <div id="kpis" class="kpis"></div>
    </header>
    <main>
      <aside class="sidebar">
        <div class="filters">
          <label>Status
            <select id="status-filter"></select>
          </label>
          <label>Backend
            <select id="backend-filter"></select>
          </label>
          <label>Advisor Calls
            <input id="advisor-filter" type="number" min="0" step="1" placeholder="Any">
          </label>
          <label>Error Mode
            <select id="error-filter"></select>
          </label>
          <label class="filter-wide">Task
            <input id="task-filter" type="search" placeholder="Filter by task">
          </label>
        </div>
        <div id="run-list" class="run-list"></div>
      </aside>
      <section id="content" class="content"></section>
    </main>
  </div>
  <script id="dashboard-data" type="application/json">__DASHBOARD_DATA__</script>
  <script>
    const data = JSON.parse(document.getElementById("dashboard-data").textContent);
    const state = { selectedRunId: data.selected_run_id || null };

    const nodes = {
      workspace: document.getElementById("workspace"),
      kpis: document.getElementById("kpis"),
      runList: document.getElementById("run-list"),
      content: document.getElementById("content"),
      status: document.getElementById("status-filter"),
      backend: document.getElementById("backend-filter"),
      advisor: document.getElementById("advisor-filter"),
      error: document.getElementById("error-filter"),
      task: document.getElementById("task-filter")
    };

    function make(tag, className, text) {
      const node = document.createElement(tag);
      if (className) node.className = className;
      if (text !== undefined && text !== null) node.textContent = String(text);
      return node;
    }

    function clear(node) {
      while (node.firstChild) node.removeChild(node.firstChild);
    }

    function unique(values) {
      return [...new Set(values.filter(Boolean).map(String))].sort();
    }

    function setOptions(select, values, label) {
      clear(select);
      select.appendChild(new Option(label, ""));
      values.forEach(value => select.appendChild(new Option(value, value)));
    }

    function init() {
      nodes.workspace.textContent = data.workspace || "";
      setOptions(nodes.status, unique(data.runs.map(run => run.status)), "Any");
      setOptions(nodes.backend, unique(data.runs.flatMap(run => [run.executor_backend, run.advisor_backend])), "Any");
      setOptions(nodes.error, unique(data.runs.map(run => run.error_mode)), "Any");
      [nodes.status, nodes.backend, nodes.advisor, nodes.error, nodes.task].forEach(node => {
        node.addEventListener("input", render);
      });
      render();
    }

    function currentFilters() {
      return {
        status: nodes.status.value,
        backend: nodes.backend.value,
        advisor: nodes.advisor.value,
        error: nodes.error.value,
        task: nodes.task.value.trim().toLowerCase()
      };
    }

    function filteredRuns() {
      const filters = currentFilters();
      return data.runs.filter(run => {
        if (filters.status && run.status !== filters.status) return false;
        if (filters.backend && run.executor_backend !== filters.backend && run.advisor_backend !== filters.backend) return false;
        if (filters.advisor !== "" && Number(run.advisor_consult_count) !== Number(filters.advisor)) return false;
        if (filters.error && run.error_mode !== filters.error) return false;
        if (filters.task && !String(run.task || "").toLowerCase().includes(filters.task)) return false;
        return true;
      });
    }

    function render() {
      renderKpis();
      const runs = filteredRuns();
      if (runs.length && !runs.some(run => run.run_id === state.selectedRunId)) {
        state.selectedRunId = runs[0].run_id;
      }
      renderRunList(runs);
      renderDetail();
    }

    function renderKpis() {
      clear(nodes.kpis);
      const runs = data.runs;
      const completed = runs.filter(run => run.status === "completed").length;
      const consults = runs.reduce((total, run) => total + Number(run.advisor_consult_count || 0), 0);
      const errors = runs.filter(run => run.error_mode && run.error_mode !== "none").length;
      [
        ["Runs", runs.length],
        ["Completed", completed],
        ["Advisor Calls", consults],
        ["Error Modes", errors]
      ].forEach(([label, value]) => {
        const item = make("div", "kpi");
        item.appendChild(make("strong", "", value));
        item.appendChild(document.createTextNode(label));
        nodes.kpis.appendChild(item);
      });
    }

    function renderRunList(runs) {
      clear(nodes.runList);
      if (!runs.length) {
        nodes.runList.appendChild(make("div", "empty", "No runs"));
        return;
      }
      runs.forEach(run => {
        const button = make("button", "run-row" + (run.run_id === state.selectedRunId ? " active" : ""));
        button.type = "button";
        button.addEventListener("click", () => {
          state.selectedRunId = run.run_id;
          render();
        });
        button.appendChild(make("div", "run-id", run.run_id));
        button.appendChild(make("div", "run-task", run.task || ""));
        const badges = make("div", "badges");
        badges.appendChild(make("span", "badge" + (run.status === "completed" ? "" : " warn"), run.status));
        badges.appendChild(make("span", "badge", run.executor_backend + " -> " + run.advisor_backend));
        badges.appendChild(make("span", "badge", "calls " + run.advisor_consult_count));
        if (run.error_mode && run.error_mode !== "none") badges.appendChild(make("span", "badge warn", run.error_mode));
        button.appendChild(badges);
        nodes.runList.appendChild(button);
      });
    }

    function renderDetail() {
      clear(nodes.content);
      if (!state.selectedRunId || !data.payloads[state.selectedRunId]) {
        nodes.content.appendChild(make("div", "empty", "No run selected"));
        return;
      }
      const payload = data.payloads[state.selectedRunId];
      const grid = make("div", "detail-grid");
      grid.appendChild(renderTimeline(payload));
      const side = make("div", "");
      side.appendChild(renderSummary(payload.run));
      side.appendChild(renderAgentTurns(payload.agent_turns || []));
      grid.appendChild(side);
      nodes.content.appendChild(grid);
    }

    function renderSummary(run) {
      const panel = make("section", "panel");
      panel.appendChild(make("h2", "", "Run Summary"));
      const table = make("table", "summary-table");
      [
        ["Run", run.run_id],
        ["Status", run.status],
        ["Task", run.task],
        ["Backend", run.executor_backend + " -> " + run.advisor_backend],
        ["Executor Session", run.executor_session_id],
        ["Turns", run.executor_turn_count],
        ["Advisor Calls", run.advisor_consult_count],
        ["Guidance", run.advisor_guidance_count],
        ["Memory Proposals", run.memory_proposal_count],
        ["Error Mode", run.error_mode],
        ["Created", run.created_at],
        ["Completed", run.completed_at || ""]
      ].forEach(([label, value]) => {
        const tr = make("tr");
        tr.appendChild(make("th", "", label));
        tr.appendChild(make("td", "", value));
        table.appendChild(tr);
      });
      panel.appendChild(table);
      return panel;
    }

    function renderTimeline(payload) {
      const panel = make("section", "panel");
      panel.appendChild(make("h2", "", "Timeline"));
      const list = make("ol", "timeline");
      (payload.events || []).forEach(event => list.appendChild(renderEvent(event)));
      panel.appendChild(list);
      return panel;
    }

    function renderEvent(event) {
      const item = make("li", "timeline-item");
      const head = make("div", "event-head");
      head.appendChild(make("span", "event-type", event.type || event.event_type || "event"));
      const meta = [event.created_at, event.turn ? "turn " + event.turn : ""].filter(Boolean).join("  ");
      head.appendChild(make("span", "muted", meta));
      item.appendChild(head);

      const fields = [];
      if (event.consult) {
        fields.push(["Question", event.consult.question]);
        fields.push(["Context", event.consult.context]);
        fields.push(["Options", (event.consult.options || []).join("\\n")]);
        fields.push(["Preferred", event.consult.preferred_option]);
      } else if (event.guidance) {
        fields.push(["Guidance", event.guidance.guidance]);
        fields.push(["Rationale", event.guidance.rationale]);
        fields.push(["Stop Signal", event.guidance.stop_signal]);
      } else if (event.proposal) {
        fields.push(["Memory", event.proposal.content]);
        fields.push(["Source", event.proposal.source_excerpt]);
      } else if (event.block) {
        fields.push(["Tag", event.block.tag]);
        fields.push(["Error", event.block.error]);
      } else if (event.outcome) {
        fields.push(["Outcome", event.outcome.status]);
      } else if (event.final_message) {
        fields.push(["Final Message", event.final_message]);
      } else if (event.task) {
        fields.push(["Task", event.task]);
      }

      fields.forEach(([label, value]) => item.appendChild(renderField(label, value)));
      return item;
    }

    function renderField(label, value) {
      const wrapper = make("div", "field");
      wrapper.appendChild(make("div", "field-label", label));
      wrapper.appendChild(make("div", "field-value", value === undefined || value === null ? "" : value));
      return wrapper;
    }

    function renderAgentTurns(turns) {
      const panel = make("section", "panel");
      panel.style.marginTop = "16px";
      panel.appendChild(make("h2", "", "Prompts And Raw Output"));
      if (!turns.length) {
        panel.appendChild(make("div", "empty", "No agent turns"));
        return panel;
      }
      turns.forEach(turn => {
        const details = make("details", "agent-turn");
        details.open = turns.length <= 3;
        const summary = make("summary", "", turn.role + " turn " + turn.turn + "  exit " + turn.exit_code);
        details.appendChild(summary);
        [
          ["Prompt", turn.prompt_text],
          ["Final Message", turn.final_message],
          ["Stdout", turn.stdout_text],
          ["Stderr", turn.stderr_text],
          ["Raw", JSON.stringify(turn.raw_json || {}, null, 2)]
        ].forEach(([label, value]) => {
          if (value === undefined || value === null || value === "") return;
          const block = make("section", "raw-block");
          block.appendChild(make("h3", "", label));
          block.appendChild(make("pre", "", value));
          details.appendChild(block);
        });
        panel.appendChild(details);
      });
      return panel;
    }

    init();
  </script>
</body>
</html>
"""
