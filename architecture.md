# Multi-Agent Advisor Architecture

## Goal

This repository implements a local-first scaffold for the advisor strategy across separate CLI sessions.

Core idea:

- A lower-cost executor model drives the task end-to-end.
- The executor receives a harness-injected starting prompt that defines when to ask for guidance.
- The executor can pause at hard decision points and ask for guidance by emitting a structured block.
- The harness records all events, calls a stronger advisor model with reconstructed shared context, then resumes the executor session.
- The advisor does not call tools, mutate files, or produce user-facing deliverables. It returns guidance for the executor.

## Flow

```text
User task
  -> Harness creates run and executor session id
  -> Harness injects the executor starting prompt
  -> Executor session starts through Kimi CLI
  -> Executor emits ADVISOR_CONSULT when it needs guidance
  -> Harness appends consult to session_events.jsonl
  -> Harness calls Advisor through Codex CLI with reconstructed context
  -> Advisor returns ADVISOR_GUIDANCE
  -> Harness appends guidance to session_events.jsonl
  -> Harness resumes the same executor session with the guidance
  -> Executor continues until EXECUTOR_DONE, advisor stop signal, or a run limit
  -> Harness writes outcome and optional post-run review
```

The session log is the durable shared context object. The executor and advisor do not talk directly; they communicate through structured blocks and harness-managed events.

## Repository Layout

```text
multi-agent-advisor/
  README.md
  architecture.md
  prd.md

  packages/
    adapters/
      base.py
      kimi_cli.py
      codex_cli.py
      fake.py
    roles/
      executor.py
      advisor.py
    harness/
      cli.py
      runner.py
      review.py
      artifacts.py
      mailbox.py
      memory.py
      parser.py
      policy.py
      defaults.py
      jsonl.py

  policy/
    routing_policy.md
    post_run_review.md

  memory/
    README.md
    schema.json

  runs/        # gitignored
  mailbox/     # gitignored
```

## Protocol

The executor should consult the advisor before high-impact architecture, API, schema, migration, deletion, security, privacy, or irreversible design decisions; after repeated failures or conflicting evidence; and before final completion when independent review is warranted. It should not consult for routine mechanical edits or questions directly answered by the repository.

Executor asks for guidance:

```text
<ADVISOR_CONSULT>
{"question":"Which approach should I take?","context":"...","options":["A","B"],"preferred_option":"A","urgency":"normal"}
</ADVISOR_CONSULT>
```

Advisor returns guidance:

```text
<ADVISOR_GUIDANCE>
{"guidance":"Choose A, but add a verification step.","rationale":"...","stop_signal":false}
</ADVISOR_GUIDANCE>
```

Executor marks completion:

```text
<EXECUTOR_DONE>
{"status":"completed","summary":"..."}
</EXECUTOR_DONE>
```

## Boundaries

Adapters only isolate CLI details: command construction, working directory, session id, timeout, stdout/stderr, and final message extraction.

Roles only build prompts.

Harness owns:

- run creation
- event log persistence
- consultation routing
- advisor call limits
- executor resume prompts
- artifact writes
- optional memory writes through explicit harness policy

Long-term memory is separate from the advisor tool. The advisor may recommend what to remember, but only harness code may write durable memory.

## Completion Semantics

The harness does not treat a successful executor CLI exit as task completion by itself.

- `completed`: the executor emitted a valid `EXECUTOR_DONE` block.
- `executor_stopped_without_done`: the executor exited without `ADVISOR_CONSULT` and without `EXECUTOR_DONE`.
- `advisor_call_limit_reached`: the executor requested more advice than allowed.
- `max_turns_reached`: the run exhausted the configured executor turn limit.
- `advisor_stop_signal`: the advisor explicitly told the harness to stop.
- `executor_failed`: the executor CLI exited non-zero.

This keeps the executor responsible for explicitly declaring completion while the harness remains responsible for durable state and run status.
