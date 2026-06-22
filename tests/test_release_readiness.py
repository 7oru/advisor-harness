from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase

from packages.harness.cli import main
from packages.harness.runner import RunResult
from packages.verticals.release_readiness import evaluate_release_readiness_run, run_release_readiness


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

