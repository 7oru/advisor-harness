import json
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import patch

from packages.adapters.base import AgentResult
from packages.harness.cli import main
from packages.harness.runner import RunResult
from packages.verticals.release_readiness import evaluate_release_readiness_run, run_release_readiness


class PrematureReleaseReadinessExecutor:
    def run(self, prompt, *, cwd, session_id=None, output_schema=None, timeout_seconds=None):
        report = {
            "verdict": "conditional_go",
            "summary": "Premature report emitted before advisor guidance was applied.",
            "blockers": [],
            "risks": [],
            "required_actions": [],
            "advisor_consulted": True,
            "confidence": 0.75,
            "measurable_outputs": {
                "blocker_count": 0,
                "risk_count": 0,
                "required_action_count": 0,
            },
        }
        done = {
            "status": "completed",
            "summary": "Premature completion block emitted with the consult.",
        }
        consult = {
            "question": "Should the release proceed?",
            "context": "The executor has not applied advisor guidance yet.",
            "options": ["proceed", "hold"],
            "preferred_option": "proceed",
            "urgency": "normal",
        }
        final = "\n".join(
            [
                "Premature release readiness executor emitted a report and still requested advice.",
                "<RELEASE_READINESS_REPORT>",
                json.dumps(report, indent=2, sort_keys=True),
                "</RELEASE_READINESS_REPORT>",
                "<EXECUTOR_DONE>",
                json.dumps(done, indent=2, sort_keys=True),
                "</EXECUTOR_DONE>",
                "<ADVISOR_CONSULT>",
                json.dumps(consult, indent=2, sort_keys=True),
                "</ADVISOR_CONSULT>",
            ]
        )
        return AgentResult(
            stdout=final,
            stderr="",
            final_message=final,
            events_path=None,
            exit_code=0,
            session_id=session_id,
            raw_artifacts={
                "backend": "premature-release-readiness-executor",
                "cwd": cwd,
                "output_schema": output_schema,
                "timeout_seconds": timeout_seconds,
            },
        )


class ReleaseReadinessGuidanceAdvisor:
    def run(self, prompt, *, cwd, session_id=None, output_schema=None, timeout_seconds=None):
        guidance = {
            "guidance": "Apply this advice before producing the final release report.",
            "rationale": "The final report must reflect advisor guidance.",
            "stop_signal": False,
        }
        final = "\n".join(
            [
                "Advisor guidance for the release readiness run.",
                "<ADVISOR_GUIDANCE>",
                json.dumps(guidance, indent=2, sort_keys=True),
                "</ADVISOR_GUIDANCE>",
            ]
        )
        return AgentResult(
            stdout=final,
            stderr="",
            final_message=final,
            events_path=None,
            exit_code=0,
            session_id=session_id,
            raw_artifacts={
                "backend": "release-readiness-guidance-advisor",
                "cwd": cwd,
                "output_schema": output_schema,
                "timeout_seconds": timeout_seconds,
            },
        )


class ReleaseReadinessVerticalTests(TestCase):
    def test_fake_release_readiness_writes_artifacts_and_passes(self):
        with TemporaryDirectory() as td:
            root = Path(td)
            result = run_release_readiness(
                root=root,
                use_sample=True,
                executor_backend="fake",
                advisor_backend="fake",
                timeout_seconds=10,
            )

            self.assertEqual(result.run.outcome["status"], "completed")
            self.assertEqual(result.run.outcome["advisor_consult_count"], 1)
            self.assertTrue(result.evaluation["passed"])
            self.assertEqual(result.evaluation["report"]["verdict"], "conditional_go")
            self.assertEqual(result.evaluation["metrics"]["risk_count"], 2)
            self.assertTrue((result.run.run_dir / "release_readiness_evidence.md").exists())
            self.assertTrue((result.run.run_dir / "release_readiness_prompt.md").exists())
            self.assertTrue((result.run.run_dir / "release_readiness_report.schema.json").exists())
            self.assertTrue((result.run.run_dir / "release_readiness_evaluation.json").exists())
            self.assertTrue((result.run.run_dir / "release_readiness_evaluation.md").exists())

    def test_release_readiness_cli_sample_returns_success(self):
        with TemporaryDirectory() as td:
            root = Path(td)
            stdout = StringIO()

            with redirect_stdout(stdout):
                exit_code = main(
                    [
                        "--cwd",
                        str(root),
                        "release-readiness",
                        "--sample",
                        "--executor",
                        "fake",
                        "--advisor",
                        "fake",
                        "--timeout",
                        "10",
                    ]
                )

            output = stdout.getvalue()
            self.assertEqual(exit_code, 0)
            self.assertIn("status: completed", output)
            self.assertIn("vertical_passed: True", output)
            self.assertIn("verdict: conditional_go", output)

    def test_release_readiness_evaluator_flags_missing_report(self):
        with TemporaryDirectory() as td:
            root = Path(td)
            run_dir = root / "runs" / "run_missing_report"
            run_dir.mkdir(parents=True)
            (run_dir / "executor_turn_1.final.md").write_text(
                "\n".join(
                    [
                        "Executor completed without the vertical report.",
                        "<EXECUTOR_DONE>",
                        '{"status":"completed","summary":"done"}',
                        "</EXECUTOR_DONE>",
                    ]
                ),
                encoding="utf-8",
            )
            result = RunResult(
                run_id="run_missing_report",
                run_dir=run_dir,
                outcome={
                    "status": "completed",
                    "advisor_consult_count": 1,
                    "max_advisor_calls": 2,
                },
            )

            evaluation = evaluate_release_readiness_run(result)

            self.assertFalse(evaluation["passed"])
            self.assertIn("missing RELEASE_READINESS_REPORT block", evaluation["failures"])

    def test_release_readiness_rejects_report_before_advisor_guidance_is_applied(self):
        def adapter_factory(name):
            if name == "premature-release":
                return PrematureReleaseReadinessExecutor()
            if name == "guidance-advisor":
                return ReleaseReadinessGuidanceAdvisor()
            raise AssertionError("unexpected adapter: {}".format(name))

        with TemporaryDirectory() as td:
            root = Path(td)
            with patch("packages.harness.runner.create_adapter", side_effect=adapter_factory):
                result = run_release_readiness(
                    root=root,
                    use_sample=True,
                    executor_backend="premature-release",
                    advisor_backend="guidance-advisor",
                    timeout_seconds=10,
                    max_turns=1,
                    max_advisor_calls=1,
                )

            self.assertEqual(result.run.outcome["status"], "max_turns_reached")
            self.assertEqual(result.run.outcome["advisor_consult_count"], 1)
            self.assertEqual(result.run.outcome["advisor_guidance_count"], 1)
            self.assertEqual(result.run.outcome["executor_done"], {})
            self.assertFalse(result.evaluation["passed"])
            self.assertIn(
                "run status expected 'completed', got 'max_turns_reached'",
                result.evaluation["failures"],
            )
