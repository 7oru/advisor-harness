# Multi-Agent Advisor Architecture

## Goal

This repository implements a local-first scaffold for the advisor strategy across separate CLI sessions.

Core idea:

- A lower-cost executor model drives the task end-to-end.
- The executor can pause at hard decision points and ask for guidance.
- The harness records all events, calls a stronger advisor model with reconstructed shared context, then resumes the executor session.
- The advisor does not call tools, mutate files, or produce user-facing deliverables. It returns guidance for the executor.

## Flow

```text
User task
  -> Harness creates run and executor session id
  -> Executor session starts through Kimi CLI
  -> Executor emits ADVISOR_CONSULT when it needs guidance
  -> Harness appends consult to session_events.jsonl
  -> Harness calls Advisor through Codex CLI with reconstructed context
  -> Advisor returns ADVISOR_GUIDANCE
  -> Harness appends guidance to session_events.jsonl
  -> Harness resumes the same executor session with the guidance
  -> Executor continues until EXECUTOR_DONE or no more consults
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
