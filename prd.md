# Multi-Agent Advisor PRD

## Product

Multi-Agent Advisor is a local CLI scaffold for running an executor model with a stronger advisor model in the loop.

The first supported local pairing is:

- Kimi CLI as executor
- Codex CLI as advisor

The repo intentionally avoids vertical business logic. Domain workflows can be added later on top of the generic advisor harness.

## User Goal

Run long or ambiguous tasks with a cheaper executor model while consulting a stronger advisor model only at key decision points.

## MVP Requirements

- Provide `maa doctor` to verify local Kimi and Codex CLI availability.
- Provide `maa init` to create local runtime directories and default policy files.
- Provide `maa run` to start an executor session and allow mid-task advisor consultations.
- Preserve a durable event log per run so advisor calls can receive reconstructed shared context.
- Resume the executor after each advisor guidance response.
- Cap advisor consultations per run through a CLI option.
- Provide a fake backend for deterministic tests.
- Provide `maa review --run <run_id>` for post-run review.

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
