# Multi-Agent Advisor

Local-first scaffold for a Claude-style advisor strategy across CLI sessions.

The executor model drives the task. When it reaches a hard decision, it emits an `ADVISOR_CONSULT` block. The harness records the event, calls the advisor model with reconstructed shared context, records the returned `ADVISOR_GUIDANCE`, and resumes the executor session with that guidance.

Default local pairing:

- Executor: Kimi CLI
- Advisor: Codex CLI
- Test backend: deterministic fake adapter

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
maa run "fake smoke task" --executor fake --advisor fake
maa review --run <run_id> --advisor fake
```

Live local smoke:

```bash
maa run "For this smoke test, consult the advisor once before finalizing, then produce a short final answer." \
  --executor kimi --advisor codex --timeout 240 --max-turns 3
maa review --run <run_id> --advisor codex --timeout 240
```

## Advisor Protocol

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

## Artifacts

Runtime state is local and gitignored:

- `runs/<run_id>/`
- `mailbox/*.jsonl`
- `memory/*.jsonl`

Important run files:

- `session_events.jsonl`: durable cross-session event log
- `advisor_consults.jsonl`: executor consultation requests
- `advisor_guidance.jsonl`: advisor guidance returned to executor
- `executor_turn_<n>.*`: executor CLI outputs
- `advisor_turn_<n>.*`: advisor CLI outputs
- `outcome.json`: run status and counters

## Tests

```bash
python3 -m unittest discover -s tests
```
