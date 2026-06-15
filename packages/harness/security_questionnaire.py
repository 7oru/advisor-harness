"""Security questionnaire workflow scaffold."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from packages.harness.artifacts import write_text
from packages.harness.jsonl import read_jsonl
from packages.harness.runner import RunResult, run_task


def run_security_questionnaire(
    *,
    root: Path,
    questionnaire: Path,
    knowledge: Path,
    executor_backend: str = "kimi",
    advisor_backend: str = "codex",
    timeout_seconds: Optional[int] = 240,
) -> RunResult:
    questionnaire = questionnaire.resolve()
    knowledge = knowledge.resolve()
    task = (
        "Draft a security questionnaire response using the local knowledge base. "
        "Questionnaire: {questionnaire}. Knowledge directory: {knowledge}."
    ).format(questionnaire=questionnaire, knowledge=knowledge)
    workflow_context = _workflow_context(questionnaire, knowledge)
    result = run_task(
        root=root,
        task=task,
        executor_backend=executor_backend,
        advisor_backend=advisor_backend,
        timeout_seconds=timeout_seconds,
        workflow_context=workflow_context,
        extra_artifacts={
            "questionnaire_input.md": _input_preview(questionnaire),
            "knowledge_input.md": _knowledge_preview(knowledge),
        },
    )
    _write_security_artifacts(result.run_dir, questionnaire, knowledge)
    return result


def _workflow_context(questionnaire: Path, knowledge: Path) -> str:
    return """Security Questionnaire Advisor workflow.

Input questionnaire path: {questionnaire}
Knowledge base path: {knowledge}

Produce a customer-readable draft, evidence references, risk flags, and open questions. Human confirmation remains required for all customer-visible answers.

Flag these cases aggressively:
- no evidence supports an affirmative answer
- compliance, encryption, SSO, backup, logging, retention, subprocessors, access control, privacy, data residency, or legal-adjacent claims
- stale or conflicting sources
- planned, roadmap, partial, or low-confidence capabilities

Use ADVICE_REQUEST for high-risk or low-confidence packets. Use MEMORY_PROPOSAL only for reusable facts with a concrete source excerpt.
""".format(
        questionnaire=questionnaire,
        knowledge=knowledge,
    )


def _input_preview(path: Path) -> str:
    return "# Questionnaire Input\n\nPath: `{}`\n\n{}\n".format(path, _safe_preview(path))


def _knowledge_preview(path: Path) -> str:
    if path.is_file():
        return "# Knowledge Input\n\nPath: `{}`\n\n{}\n".format(path, _safe_preview(path))
    if not path.exists():
        return "# Knowledge Input\n\nPath does not exist: `{}`\n".format(path)
    markdown_files = sorted(path.rglob("*.md"))[:10]
    lines = ["# Knowledge Input", "", "Path: `{}`".format(path), ""]
    if not markdown_files:
        lines.append("No Markdown files found in this scaffold preview.")
    for markdown_file in markdown_files:
        lines.extend(["", "## {}".format(markdown_file.relative_to(path)), "", _safe_preview(markdown_file)])
    return "\n".join(lines) + "\n"


def _safe_preview(path: Path, max_chars: int = 4000) -> str:
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return "_Preview unavailable for this file type in scaffold mode._"
    if len(text) > max_chars:
        return text[:max_chars] + "\n\n_Preview truncated._"
    return text


def _write_security_artifacts(run_dir: Path, questionnaire: Path, knowledge: Path) -> None:
    executor_final = (run_dir / "executor.final.md").read_text(encoding="utf-8")
    advice_requests = read_jsonl(run_dir / "advice_requests.jsonl")
    memory_proposals = read_jsonl(run_dir / "memory_proposals.jsonl")

    write_text(
        run_dir / "answers_draft.md",
        "# Answers Draft\n\n"
        "Source questionnaire: `{}`\n\n"
        "Knowledge base: `{}`\n\n"
        "{}\n".format(questionnaire, knowledge, executor_final.strip()),
    )
    write_text(
        run_dir / "evidence_links.md",
        "# Evidence Links\n\n"
        "- Questionnaire: `{}`\n"
        "- Knowledge base: `{}`\n"
        "- Memory proposals emitted: {}\n".format(questionnaire, knowledge, len(memory_proposals)),
    )

    risk_lines = ["# Risk Flags", ""]
    if advice_requests:
        for request in advice_requests:
            risk_lines.append("- `{}`: {}".format(request.get("reason"), request.get("id")))
    else:
        risk_lines.append("- No advisor-triggering risk packets were emitted.")
    write_text(run_dir / "risk_flags.md", "\n".join(risk_lines) + "\n")

    write_text(
        run_dir / "open_questions.md",
        "# Open Questions\n\n"
        "- Human confirmation is required before using customer-visible answers.\n"
        "- Review `risk_flags.md` and `advisor_reviews.jsonl` before finalizing.\n",
    )
