"""Evaluation and regression harness for advisor strategy runs."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

from packages.harness.artifacts import new_id, utc_now, write_json, write_text
from packages.harness.defaults import init_workspace
from packages.harness.jsonl import append_jsonl
from packages.harness.runner import RunResult, run_task


_BEHAVIOR_METRIC_DIRECTIONS = {
    "malformed_block_rate": "lower",
    "completion_without_executor_done_rate": "lower",
    "average_advisor_consults_per_run": "higher",
    "max_turn_exhaustion_rate": "lower",
    "advisor_guidance_application_rate": "higher",
}


@dataclass(frozen=True)
class EvalScenario:
    name: str
    task: str
    description: str
    executor_backend: str = "fake"
    advisor_backend: str = "fake"
    timeout_seconds: int = 30
    max_turns: int = 3
    max_advisor_calls: int = 3
    expected_status: Optional[str] = None
    expected_advisor_consults: Optional[int] = None
    expected_advisor_guidance: Optional[int] = None
    expected_malformed_blocks: Optional[int] = None
    live: bool = False


def fake_scenarios() -> List[EvalScenario]:
    return [
        EvalScenario(
            name="fake_autonomous_consult",
            task="fake smoke task",
            description="Executor consults advisor, receives guidance, resumes, and completes.",
            expected_status="completed",
            expected_advisor_consults=1,
            expected_advisor_guidance=1,
            expected_malformed_blocks=0,
        ),
        EvalScenario(
            name="fake_no_consult_completion",
            task="eval no consult completion",
            description="Executor completes without advisor consultation when no hard decision exists.",
            expected_status="completed",
            expected_advisor_consults=0,
            expected_advisor_guidance=0,
            expected_malformed_blocks=0,
        ),
        EvalScenario(
            name="fake_missing_done",
            task="eval missing done",
            description="Executor exits without EXECUTOR_DONE and should not be marked completed.",
            expected_status="executor_stopped_without_done",
            expected_advisor_consults=0,
            expected_advisor_guidance=0,
            expected_malformed_blocks=0,
        ),
        EvalScenario(
            name="fake_malformed_consult",
            task="eval malformed consult",
            description="Malformed executor consultation block is captured as a malformed block status.",
            expected_status="malformed_block",
            expected_advisor_consults=0,
            expected_advisor_guidance=0,
            expected_malformed_blocks=1,
        ),
        EvalScenario(
            name="fake_malformed_guidance",
            task="eval malformed guidance",
            description="Malformed advisor guidance block is captured as a malformed block status.",
            expected_status="malformed_block",
            expected_advisor_consults=1,
            expected_advisor_guidance=0,
            expected_malformed_blocks=1,
        ),
        EvalScenario(
            name="fake_advisor_stop",
            task="eval advisor stop",
            description="Advisor stop signal stops the run with advisor_stop_signal status.",
            expected_status="advisor_stop_signal",
            expected_advisor_consults=1,
            expected_advisor_guidance=1,
            expected_malformed_blocks=0,
        ),
        EvalScenario(
            name="fake_max_turns",
            task="eval max turns",
            description="Repeated consultations exhaust max turns and produce max_turns_reached.",
            expected_status="max_turns_reached",
            expected_advisor_consults=2,
            expected_advisor_guidance=2,
            expected_malformed_blocks=0,
            max_turns=2,
            max_advisor_calls=2,
        ),
    ]


def live_smoke_scenario(*, executor_backend: str, advisor_backend: str, timeout_seconds: int) -> EvalScenario:
    return EvalScenario(
        name="live_autonomous_consult",
        task=(
            "For this evaluation smoke test, before finalizing you must emit exactly one "
            "ADVISOR_CONSULT block asking whether to keep the generic advisor scaffold minimal. "
            "After advisor guidance, produce a two sentence final answer and include EXECUTOR_DONE."
        ),
        description="Live executor/advisor consult-guidance-resume smoke test.",
        executor_backend=executor_backend,
        advisor_backend=advisor_backend,
        timeout_seconds=timeout_seconds,
        max_turns=3,
        max_advisor_calls=2,
        expected_status="completed",
        expected_advisor_consults=1,
        expected_advisor_guidance=1,
        expected_malformed_blocks=0,
        live=True,
    )


def run_evaluation(
    *,
    root: Path,
    include_live: bool = False,
    live_executor: str = "kimi",
    live_advisor: str = "codex",
    live_timeout_seconds: int = 240,
) -> Dict[str, Any]:
    init_workspace(root)
    eval_dir = root / "runs" / "{}_{}".format(new_id("eval"), utc_now().replace(":", "").replace("-", ""))
    eval_dir.mkdir(parents=True, exist_ok=False)

    scenarios = fake_scenarios()
    if include_live:
        scenarios.append(
            live_smoke_scenario(
                executor_backend=live_executor,
                advisor_backend=live_advisor,
                timeout_seconds=live_timeout_seconds,
            )
        )

    previous_summary = _latest_previous_summary(root, exclude_dir=eval_dir)
    scenario_results = []
    for scenario in scenarios:
        scenario_result = _run_scenario(root=root, scenario=scenario)
        scenario_results.append(scenario_result)
        append_jsonl(eval_dir / "scenario_results.jsonl", scenario_result)

    metrics = _compute_metrics(scenario_results)
    verdict = _compare_to_previous(metrics, previous_summary)
    summary = {
        "evaluation_id": eval_dir.name,
        "created_at": utc_now(),
        "include_live": include_live,
        "verdict": verdict,
        "metrics": metrics,
        "scenario_count": len(scenario_results),
        "passed_count": sum(1 for result in scenario_results if result["passed"]),
        "failed_count": sum(1 for result in scenario_results if not result["passed"]),
        "previous_evaluation_id": previous_summary.get("evaluation_id") if previous_summary else None,
        "scenarios": scenario_results,
    }
    write_json(eval_dir / "evaluation_summary.json", summary)
    write_text(eval_dir / "evaluation_summary.md", _summary_markdown(summary))
    return {"eval_dir": str(eval_dir), "summary": summary}


def _run_scenario(*, root: Path, scenario: EvalScenario) -> Dict[str, Any]:
    result = run_task(
        root=root,
        task=scenario.task,
        executor_backend=scenario.executor_backend,
        advisor_backend=scenario.advisor_backend,
        timeout_seconds=scenario.timeout_seconds,
        max_turns=scenario.max_turns,
        max_advisor_calls=scenario.max_advisor_calls,
    )
    failures = _scenario_failures(scenario, result)
    return {
        "name": scenario.name,
        "description": scenario.description,
        "live": scenario.live,
        "passed": not failures,
        "failures": failures,
        "run_id": result.run_id,
        "run_dir": str(result.run_dir),
        "outcome": result.outcome,
        "expected": {
            "status": scenario.expected_status,
            "advisor_consult_count": scenario.expected_advisor_consults,
            "advisor_guidance_count": scenario.expected_advisor_guidance,
            "malformed_block_count": scenario.expected_malformed_blocks,
        },
    }


def _scenario_failures(scenario: EvalScenario, result: RunResult) -> List[str]:
    failures = []
    outcome = result.outcome
    checks = [
        ("status", scenario.expected_status),
        ("advisor_consult_count", scenario.expected_advisor_consults),
        ("advisor_guidance_count", scenario.expected_advisor_guidance),
        ("malformed_block_count", scenario.expected_malformed_blocks),
    ]
    for key, expected in checks:
        if expected is None:
            continue
        actual = outcome.get(key)
        if actual != expected:
            failures.append("{} expected {!r}, got {!r}".format(key, expected, actual))
    return failures


def _compute_metrics(results: List[Dict[str, Any]]) -> Dict[str, Any]:
    total = len(results)
    if total == 0:
        return {}
    status_counts: Dict[str, int] = {}
    advisor_consults = 0
    malformed_runs = 0
    missing_done_runs = 0
    max_turn_runs = 0
    runs_with_guidance = 0
    completed_with_guidance = 0
    for result in results:
        outcome = result["outcome"]
        status = str(outcome.get("status") or "unknown")
        status_counts[status] = status_counts.get(status, 0) + 1
        advisor_consults += int(outcome.get("advisor_consult_count") or 0)
        if int(outcome.get("malformed_block_count") or 0) > 0:
            malformed_runs += 1
        if status == "executor_stopped_without_done":
            missing_done_runs += 1
        if status == "max_turns_reached":
            max_turn_runs += 1
        if int(outcome.get("advisor_guidance_count") or 0) > 0:
            runs_with_guidance += 1
            if status == "completed":
                completed_with_guidance += 1
    passed_count = sum(1 for result in results if result["passed"])
    return {
        "pass_rate": passed_count / total,
        "malformed_block_rate": malformed_runs / total,
        "completion_without_executor_done_rate": missing_done_runs / total,
        "average_advisor_consults_per_run": advisor_consults / total,
        "max_turn_exhaustion_rate": max_turn_runs / total,
        "advisor_guidance_application_rate": (
            completed_with_guidance / runs_with_guidance if runs_with_guidance else 0.0
        ),
        "status_counts": status_counts,
    }


def _latest_previous_summary(root: Path, *, exclude_dir: Path) -> Dict[str, Any]:
    summaries = []
    runs_dir = root / "runs"
    if not runs_dir.exists():
        return {}
    for path in runs_dir.glob("eval_*/evaluation_summary.json"):
        if path.parent == exclude_dir:
            continue
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if isinstance(value, dict):
            summaries.append(value)
    if not summaries:
        return {}
    summaries.sort(key=lambda item: str(item.get("created_at") or ""))
    return summaries[-1]


def _compare_to_previous(metrics: Dict[str, Any], previous_summary: Dict[str, Any]) -> str:
    if not previous_summary:
        return "stable"
    previous_metrics = previous_summary.get("metrics") or {}
    current_pass_rate = float(metrics.get("pass_rate") or 0.0)
    previous_pass_rate = float(previous_metrics.get("pass_rate") or 0.0)
    if current_pass_rate > previous_pass_rate:
        return "improved"
    if current_pass_rate < previous_pass_rate:
        return "regressed"
    behavior_verdict = _compare_behavior_metrics(metrics, previous_metrics)
    if behavior_verdict:
        return behavior_verdict
    return "stable"


def _compare_behavior_metrics(metrics: Dict[str, Any], previous_metrics: Dict[str, Any]) -> str:
    improved = False
    for key, direction in _BEHAVIOR_METRIC_DIRECTIONS.items():
        if key not in metrics or key not in previous_metrics:
            continue
        current_value = float(metrics.get(key) or 0.0)
        previous_value = float(previous_metrics.get(key) or 0.0)
        if current_value == previous_value:
            continue
        current_is_better = (
            current_value > previous_value if direction == "higher" else current_value < previous_value
        )
        if not current_is_better:
            return "regressed"
        improved = True
    return "improved" if improved else ""


def _summary_markdown(summary: Dict[str, Any]) -> str:
    lines = [
        "# Evaluation Summary",
        "",
        "- Evaluation: `{}`".format(summary["evaluation_id"]),
        "- Verdict: `{}`".format(summary["verdict"]),
        "- Scenarios: {}".format(summary["scenario_count"]),
        "- Passed: {}".format(summary["passed_count"]),
        "- Failed: {}".format(summary["failed_count"]),
        "",
        "## Metrics",
        "",
    ]
    for key, value in sorted(summary["metrics"].items()):
        lines.append("- `{}`: {}".format(key, value))
    lines.extend(["", "## Scenarios", ""])
    for result in summary["scenarios"]:
        marker = "PASS" if result["passed"] else "FAIL"
        lines.append("- `{}` {}: `{}`".format(marker, result["name"], result["outcome"].get("status")))
        for failure in result["failures"]:
            lines.append("  - {}".format(failure))
    return "\n".join(lines) + "\n"
