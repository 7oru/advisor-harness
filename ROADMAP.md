# Roadmap

This roadmap keeps the project focused on a generic advisor strategy scaffold first, then expands toward persistence, visualization, domain workflows, and self-improving prompts/memory.

## Phase 1: Complete the Advisor Strategy Harness

Goal: make the cross-session advisor strategy loop reliable enough to use as a reusable local runtime.

Key outcomes:

- Harden the `ADVISOR_CONSULT` -> `ADVISOR_GUIDANCE` -> executor resume loop.
- Make executor session continuation explicit, observable, and resilient across CLI failures.
- Add stricter schema validation for executor, advisor, and completion blocks.
- Improve run status handling for advisor stop signals, malformed blocks, repeated consults, and exhausted budgets.
- Keep the harness domain-agnostic: no vertical business workflow should be required for the core loop.

Acceptance signal:

- A live Kimi executor and Codex advisor run can complete a non-trivial task through at least one autonomous consultation and resume cycle.

## Phase 1.5: Add an Evaluation and Regression Harness

Goal: create a small, repeatable quality baseline before adding persistence, UI, vertical workflows, or self-improvement loops.

Key outcomes:

- Maintain fixed smoke tasks for fake and live executor/advisor runs.
- Add regression scenarios for autonomous consultation, no-consult completion, malformed blocks, advisor stop signals, and missing `EXECUTOR_DONE`.
- Track simple quality and reliability metrics:
  - malformed block rate
  - completion without `EXECUTOR_DONE` rate
  - advisor consultation count per run
  - max-turn exhaustion rate
  - advisor guidance application rate
- Save evaluation summaries as run artifacts so later UI and feedback-loop work has a concrete baseline.

Acceptance signal:

- A single command can run the scaffold regression suite and report whether advisor consultation behavior improved, regressed, or stayed stable.

Current scaffold support:

- `maa eval` runs the fake regression suite and writes `evaluation_summary.json`, `evaluation_summary.md`, and `scenario_results.jsonl` under `runs/eval_*/`.
- `maa eval --include-live` adds one live Kimi/Codex consult-guidance-resume smoke scenario.
- The summary reports pass rate, malformed block rate, completion without `EXECUTOR_DONE` rate, advisor consultation count, max-turn exhaustion rate, and advisor guidance application rate.

## Phase 2: Persist Sessions to a Database and Add UI Visualization

Goal: move beyond file-only artifacts so runs, turns, consultations, guidance, and outcomes can be queried and visualized.

Key outcomes:

- Persist session events, executor turns, advisor consultations, advisor guidance, memory proposals, and outcomes to a local database.
- Keep JSONL artifacts as export/debug output, but make the database the queryable source of truth.
- Add a lightweight UI to inspect timelines, prompts, raw CLI outputs, consult reasons, guidance, and final outcomes.
- Support filtering by run status, backend, advisor call count, task, and error mode.

Acceptance signal:

- A user can open a local UI, inspect a run timeline, and understand exactly when the executor consulted the advisor and how guidance changed the next executor turn.

Current scaffold support:

- `maa run` persists runs to `memory/advisor_runs.db` while keeping JSONL and text artifacts for export/debug.
- The database records run summaries, session events, executor/advisor turns, advisor consultations, advisor guidance, memory proposals, malformed blocks, and outcomes.
- `maa ui` renders `runs/ui/index.html` from the database, with filters for status, backend, advisor call count, task text, and error mode.
- `maa ui --serve --port 8765` serves the rendered dashboard on localhost for browser inspection.

## Phase 3: Add a Focused Vertical Application

Goal: validate the generic harness against a narrow, high-value domain without polluting the core runtime.

Key outcomes:

- Pick one specific vertical workflow with repeated tasks, high-value judgment points, and measurable outputs.
- Keep domain prompts, schemas, samples, and evaluators outside the generic harness core.
- Reuse the same advisor loop, session persistence, and UI timeline.
- Add domain-specific acceptance tests and live smoke scenarios.

Acceptance signal:

- The vertical application demonstrates that the advisor strategy improves task quality or safety while keeping advisor calls explainable and bounded.

## Phase 4: Build the Feedback Loop for Memory Schema and Prompts

Goal: let post-run review propose improvements to durable memory structure and the injected prompts used by executor and advisor.

Key outcomes:

- Use post-run review to detect missing advisor consultations, unnecessary consultations, weak guidance, bad memory proposals, and confusing prompt instructions.
- Generate structured improvement proposals for:
  - memory schema
  - executor starting prompt
  - advisor guidance prompt
- Require harness-side validation and human approval before applying changes.
- Track prompt and schema versions per run so quality changes can be evaluated over time.

Acceptance signal:

- The system can produce auditable patch proposals that improve future executor/advisor behavior without letting a model directly mutate durable policy, schema, or prompts.
