# Sample Release Candidate Evidence

Project: Multi-Agent Advisor local harness

Release objective:

- Demonstrate an advisor strategy loop with persisted sessions, a run timeline UI, and one focused vertical workflow.

Completed evidence:

- Generic fake regression suite covers consult, no-consult completion, malformed blocks, advisor stop signal, max-turn exhaustion, and missing `EXECUTOR_DONE`.
- Run persistence stores summaries, events, turns, consultations, guidance, memory proposals, malformed blocks, and outcomes in SQLite.
- `maa ui` renders a local HTML timeline from the database.

Known gaps:

- Live Kimi/Codex smoke is optional and may not have been run for every local release candidate.
- The first vertical workflow is still new and needs a deterministic fake acceptance test before live use.
- The release should document how to run the vertical smoke path and where its artifacts are written.

Decision context:

- A cautious release can proceed if the deterministic vertical path passes and the missing live smoke is called out as follow-up.

