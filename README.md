# Advisor Harness

Local-first scaffold for a Claude-style advisor strategy across CLI sessions.

The executor model drives the task. The harness injects a starting prompt that tells the executor when to consult the advisor. When the executor reaches a hard decision, it emits an `ADVISOR_CONSULT` block. The harness records the event, calls the advisor model with reconstructed shared context, records the returned `ADVISOR_GUIDANCE`, and resumes the same executor session with that guidance.

Default local pairing:

- Executor: Kimi CLI
- Advisor: Codex CLI
- Test backend: deterministic fake adapter

See [ROADMAP.md](ROADMAP.md) for the staged plan from the generic advisor harness to persistence, UI, vertical applications, and feedback-loop-driven prompt/schema improvement.

## Install

```bash
python3 -m venv .venv
. .venv/bin/activate
python3 -m pip install wheel
python3 -m pip install -e . --no-build-isolation
```

## Commands

```bash
maa doctor
maa init
maa run "fake smoke task" --executor fake --advisor fake --max-turns 3 --max-advisor-calls 3
maa eval
maa ui
maa review --run <run_id> --advisor fake
```

Live local smoke:

```bash
maa run "For this smoke test, consult the advisor once before finalizing, then produce a short final answer." \
  --executor kimi --advisor codex --timeout 240 --max-turns 3 --max-advisor-calls 2
maa review --run <run_id> --advisor codex --timeout 240
```

Evaluation harness:

```bash
maa eval
maa eval --include-live --live-timeout 240
```

`maa eval` runs deterministic fake regression scenarios for autonomous consultation, no-consult completion, malformed blocks, advisor stop signals, max-turn exhaustion, and missing `EXECUTOR_DONE`. It writes `evaluation_summary.json`, `evaluation_summary.md`, and `scenario_results.jsonl` under `runs/eval_*/`.

Run timeline UI:

```bash
maa ui
maa ui --serve --port 8765
```

`maa ui` renders a local HTML dashboard to `runs/ui/index.html` from the SQLite run database. The dashboard filters persisted runs by status, backend, advisor call count, task text, and error mode, then shows the selected run timeline, prompts, raw CLI outputs, consult reasons, guidance, memory proposals, and outcome.

## Advisor Protocol

The executor decides when advice is needed. The advisor does not run tools, mutate files, or write memory. The harness performs the actual advisor call and owns all durable state.

Executor consultation request:

```text
<ADVISOR_CONSULT>
{"question":"...","context":"...","options":["..."],"preferred_option":"...","urgency":"normal"}
</ADVISOR_CONSULT>
```

Advisor guidance:

```text
<ADVISOR_GUIDANCE>
{"guidance":"...","rationale":"...","stop_signal":false}
</ADVISOR_GUIDANCE>
```

Executor completion:

```text
<EXECUTOR_DONE>
{"status":"completed","summary":"..."}
</EXECUTOR_DONE>
```

A run is marked `completed` only when the executor emits `EXECUTOR_DONE`. If the executor exits without a consultation request and without `EXECUTOR_DONE`, the harness records `executor_stopped_without_done`.

## Artifacts

Runtime state is local and gitignored:

- `runs/<run_id>/`
- `mailbox/*.jsonl`
- `memory/*.jsonl`
- `memory/advisor_runs.db`

Important run files:

- `memory/advisor_runs.db`: queryable source of truth for persisted runs, events, turns, consults, guidance, memory proposals, malformed blocks, and outcomes
- `session_events.jsonl`: durable cross-session event log
- `advisor_consults.jsonl`: executor consultation requests
- `advisor_guidance.jsonl`: advisor guidance returned to executor
- `executor_turn_<n>.*`: executor CLI outputs
- `advisor_turn_<n>.*`: advisor CLI outputs
- `outcome.json`: run status and counters
- `evaluation_summary.json`: evaluation metrics and scenario results for `maa eval`
- `runs/ui/index.html`: generated local run timeline dashboard

The `outcome.json` file includes the executor session id, executor turn count, advisor consultation count, guidance count, and completion status.

## Tests

```bash
python3 -m unittest discover -s tests
```
