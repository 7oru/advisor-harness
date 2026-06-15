# Multi-Agent Advisor

Local-first harness for a two-agent advisor pattern:

- Kimi as the low-cost executor
- Codex as the advisor for high-risk packets, memory review, and post-run feedback
- Harness-owned artifacts, mailbox, policy, and approved memory writes

The first scaffold targets Security Questionnaire Advisor workflows while keeping the harness reusable.

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
maa run-security-questionnaire apps/security_questionnaire/sample_inputs/questionnaire_sample.csv \
  --knowledge apps/security_questionnaire/sample_inputs/company_knowledge \
  --executor fake --advisor fake
```

Live local smoke:

```bash
maa run "Produce one advice request and one memory proposal for a scaffold smoke test." \
  --executor kimi --advisor codex --timeout 240
maa review --run <run_id> --advisor codex --timeout 240
```

## Artifacts

Runtime state is local and gitignored:

- `runs/<run_id>/`
- `mailbox/*.jsonl`
- `memory/*.jsonl`

Each run stores the task, executor stdout/stderr, advisor reviews, memory proposals, approved memory records, and `outcome.json`.

## Tests

```bash
python3 -m unittest discover -s tests
```
