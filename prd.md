# Multi-Agent Advisor PRD

## Product

Multi-Agent Advisor is a local CLI scaffold for running an executor model with a stronger advisor model in the loop.

The first supported local pairing is:

- Kimi CLI as executor
- Codex CLI as advisor

The repo intentionally avoids vertical business logic. Domain workflows can be added later on top of the generic advisor harness.

## User Goal

Run long or ambiguous tasks with a cheaper executor model while consulting a stronger advisor model only at key decision points. The executor decides when advice is needed based on a harness-injected starting prompt; the harness performs the actual advisor call and resumes the same executor session.

## MVP Requirements

- Provide `maa doctor` to verify local Kimi and Codex CLI availability.
- Provide `maa init` to create local runtime directories and default policy files.
- Provide `maa run` to start an executor session and allow mid-task advisor consultations.
- Preserve a durable event log per run so advisor calls can receive reconstructed shared context.
- Resume the executor after each advisor guidance response.
- Cap advisor consultations per run through a CLI option.
- Cap executor turns per run through a CLI option.
- Require an explicit `EXECUTOR_DONE` block before reporting a run as completed.
- Provide a fake backend for deterministic tests.
- Provide `maa review --run <run_id>` for post-run review.

## Advisor Trigger Policy

The injected executor prompt must tell the executor to consult the advisor before high-impact architecture, API, schema, migration, deletion, security, privacy, or irreversible design choices. It must also encourage consultation after repeated failure, ambiguous tests, conflicting evidence, or materially different tradeoffs.

The same prompt must discourage unnecessary consultation for routine mechanical edits, obvious local fixes, or questions answered directly by the repository.

## Run Status Semantics

- `completed`: executor emitted `EXECUTOR_DONE`.
- `executor_stopped_without_done`: executor exited without a consult request and without `EXECUTOR_DONE`.
- `advisor_call_limit_reached`: advisor consultation budget was exhausted.
- `max_turns_reached`: executor turn budget was exhausted.
- `advisor_stop_signal`: advisor requested that the harness stop the run.
- `executor_failed`: executor CLI exited non-zero.

## Non-Goals

- No vertical business workflow in the scaffold.
- No web UI.
- No cloud sync.
- No direct advisor file edits or tool calls.
- No automatic policy mutation.

## Success Criteria

- Fake executor/advisor tests prove a consult-guidance-resume loop.
- A local live smoke run proves Kimi can emit a consultation request and Codex can return guidance.
- Run artifacts include `session_events.jsonl`, `advisor_consults.jsonl`, `advisor_guidance.jsonl`, executor/advisor stdout and stderr, and `outcome.json`.
- A run without `EXECUTOR_DONE` is not reported as completed.
