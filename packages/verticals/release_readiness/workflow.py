"""Release readiness vertical built on the generic advisor harness."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

from packages.harness.artifacts import write_json, write_text
from packages.harness.parser import parse_json_blocks
from packages.harness.runner import RunResult, run_task


VERTICAL_NAME = "release_readiness"

_ASSET_DIR = Path(__file__).resolve().parent
_PROMPT_PATH = _ASSET_DIR / "prompts" / "release_readiness.md"
_SAMPLE_EVIDENCE_PATH = _ASSET_DIR / "samples" / "sample_evidence.md"
_SCHEMA_PATH = _ASSET_DIR / "schemas" / "release_readiness_report.schema.json"

_ALLOWED_VERDICTS = {"go", "conditional_go", "hold"}
_ALLOWED_SEVERITIES = {"critical", "high", "medium", "low"}


@dataclass(frozen=True)
class ReleaseReadinessResult:
    run: RunResult
    evaluation: Dict[str, Any]


def run_release_readiness(
    *,
    root: Path,
    evidence_path: Optional[Path] = None,
    evidence_text: Optional[str] = None,
    executor_backend: str = "kimi",
    advisor_backend: str = "codex",
    timeout_seconds: Optional[int] = 240,
    max_turns: int = 3,
    max_advisor_calls: int = 2,
    use_sample: bool = False,
) -> ReleaseReadinessResult:
    evidence = _load_evidence(
        evidence_path=evidence_path,
        evidence_text=evidence_text,
        use_sample=use_sample,
    )
    task = _build_task()
    workflow_context = _build_workflow_context(evidence)
    result = run_task(
        root=root,
        task=task,
        executor_backend=executor_backend,
        advisor_backend=advisor_backend,
        timeout_seconds=timeout_seconds,
        workflow_context=workflow_context,
        extra_artifacts={
            "release_readiness_evidence.md": evidence,
            "release_readiness_prompt.md": _PROMPT_PATH.read_text(encoding="utf-8"),
            "release_readiness_report.schema.json": _SCHEMA_PATH.read_text(encoding="utf-8"),
        },
        max_turns=max_turns,
        max_advisor_calls=max_advisor_calls,
    )
    evaluation = evaluate_release_readiness_run(result)
    write_json(result.run_dir / "release_readiness_evaluation.json", evaluation)
    write_text(result.run_dir / "release_readiness_evaluation.md", _evaluation_markdown(evaluation))
    return ReleaseReadinessResult(run=result, evaluation=evaluation)


def evaluate_release_readiness_run(result: RunResult) -> Dict[str, Any]:
    final_message = _latest_executor_final(result.run_dir)
    failures: List[str] = []
    try:
        reports = parse_json_blocks(final_message, "RELEASE_READINESS_REPORT")
    except ValueError as exc:
        reports = []
        failures.append(str(exc))
    report = reports[0] if reports else {}
    failures.extend(_report_failures(report))
    if result.outcome.get("status") != "completed":
        failures.append("run status expected 'completed', got {!r}".format(result.outcome.get("status")))
    if int(result.outcome.get("advisor_consult_count") or 0) < 1:
        failures.append("expected at least one advisor consultation")
    if int(result.outcome.get("advisor_consult_count") or 0) > int(result.outcome.get("max_advisor_calls") or 0):
        failures.append("advisor consultations exceeded configured limit")
    evaluation = {
        "vertical": VERTICAL_NAME,
        "passed": not failures,
        "failures": failures,
        "report": report,
        "metrics": {
            "advisor_consult_count": int(result.outcome.get("advisor_consult_count") or 0),
            "blocker_count": len(report.get("blockers") or []) if isinstance(report, dict) else 0,
            "risk_count": len(report.get("risks") or []) if isinstance(report, dict) else 0,
            "required_action_count": (
                len(report.get("required_actions") or []) if isinstance(report, dict) else 0
            ),
        },
    }
    return evaluation


def _load_evidence(
    *,
    evidence_path: Optional[Path],
    evidence_text: Optional[str],
    use_sample: bool,
) -> str:
    provided = [evidence_path is not None, evidence_text is not None, use_sample]
    if sum(1 for value in provided if value) != 1:
        raise ValueError("provide exactly one of evidence_path, evidence_text, or use_sample")
    if evidence_path is not None:
        return evidence_path.read_text(encoding="utf-8")
    if evidence_text is not None:
        return evidence_text
    return _SAMPLE_EVIDENCE_PATH.read_text(encoding="utf-8")


def _build_task() -> str:
    return (
        "Run the release readiness vertical workflow. Assess the supplied evidence, consult the "
        "advisor before the final release verdict, then produce RELEASE_READINESS_REPORT and "
        "EXECUTOR_DONE blocks."
    )


def _build_workflow_context(evidence: str) -> str:
    prompt = _PROMPT_PATH.read_text(encoding="utf-8")
    schema = _SCHEMA_PATH.read_text(encoding="utf-8")
    return "\n\n".join(
        [
            prompt,
            "## Release Readiness Report JSON Schema",
            "```json\n{}\n```".format(schema.strip()),
            "## Supplied Release Evidence",
            evidence.strip(),
        ]
    )


def _latest_executor_final(run_dir: Path) -> str:
    paths = sorted(run_dir.glob("executor_turn_*.final.md"))
    if not paths:
        return ""
    return paths[-1].read_text(encoding="utf-8")


def _report_failures(report: Dict[str, Any]) -> List[str]:
    failures: List[str] = []
    if not report:
        return ["missing RELEASE_READINESS_REPORT block"]
    _require_type(report, "verdict", str, failures)
    _require_type(report, "summary", str, failures)
    _require_type(report, "blockers", list, failures)
    _require_type(report, "risks", list, failures)
    _require_type(report, "required_actions", list, failures)
    _require_type(report, "advisor_consulted", bool, failures)
    _require_number(report, "confidence", failures)
    _require_type(report, "measurable_outputs", dict, failures)
    if report.get("verdict") not in _ALLOWED_VERDICTS:
        failures.append("verdict must be one of {}".format(sorted(_ALLOWED_VERDICTS)))
    if isinstance(report.get("confidence"), (int, float)):
        confidence = float(report["confidence"])
        if confidence < 0 or confidence > 1:
            failures.append("confidence must be between 0 and 1")
    if report.get("advisor_consulted") is not True:
        failures.append("advisor_consulted must be true")
    _validate_items(report, "blockers", ["id", "severity", "description", "evidence"], failures)
    _validate_items(report, "risks", ["id", "severity", "description", "mitigation"], failures)
    _validate_measurable_outputs(report, failures)
    return failures


def _require_type(report: Dict[str, Any], key: str, expected_type: type, failures: List[str]) -> None:
    if key not in report:
        failures.append("missing required field: {}".format(key))
    elif not isinstance(report[key], expected_type):
        failures.append("{} must be {}".format(key, expected_type.__name__))


def _require_number(report: Dict[str, Any], key: str, failures: List[str]) -> None:
    if key not in report:
        failures.append("missing required field: {}".format(key))
    elif not isinstance(report[key], (int, float)):
        failures.append("{} must be number".format(key))


def _validate_items(report: Dict[str, Any], key: str, required: List[str], failures: List[str]) -> None:
    items = report.get(key)
    if not isinstance(items, list):
        return
    for index, item in enumerate(items):
        if not isinstance(item, dict):
            failures.append("{}[{}] must be object".format(key, index))
            continue
        for field in required:
            value = item.get(field)
            if not isinstance(value, str) or not value.strip():
                failures.append("{}[{}].{} must be a non-empty string".format(key, index, field))
        severity = item.get("severity")
        if severity is not None and severity not in _ALLOWED_SEVERITIES:
            failures.append("{}[{}].severity must be one of {}".format(key, index, sorted(_ALLOWED_SEVERITIES)))


def _validate_measurable_outputs(report: Dict[str, Any], failures: List[str]) -> None:
    outputs = report.get("measurable_outputs")
    if not isinstance(outputs, dict):
        return
    expected_counts = {
        "blocker_count": len(report.get("blockers") or []),
        "risk_count": len(report.get("risks") or []),
        "required_action_count": len(report.get("required_actions") or []),
    }
    for key, expected in expected_counts.items():
        value = outputs.get(key)
        if not isinstance(value, int):
            failures.append("measurable_outputs.{} must be integer".format(key))
        elif value != expected:
            failures.append("measurable_outputs.{} expected {}, got {}".format(key, expected, value))


def _evaluation_markdown(evaluation: Dict[str, Any]) -> str:
    lines = [
        "# Release Readiness Evaluation",
        "",
        "- Passed: `{}`".format(evaluation["passed"]),
        "- Vertical: `{}`".format(evaluation["vertical"]),
        "",
        "## Metrics",
        "",
    ]
    for key, value in sorted(evaluation["metrics"].items()):
        lines.append("- `{}`: {}".format(key, value))
    lines.extend(["", "## Failures", ""])
    if evaluation["failures"]:
        for failure in evaluation["failures"]:
            lines.append("- {}".format(failure))
    else:
        lines.append("- None")
    lines.extend(["", "## Report", "", "```json", json.dumps(evaluation["report"], indent=2, sort_keys=True), "```"])
    return "\n".join(lines) + "\n"
