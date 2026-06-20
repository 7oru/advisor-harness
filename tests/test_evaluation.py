import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase

from packages.harness.evaluation import run_evaluation


class EvaluationTests(TestCase):
    def test_fake_evaluation_writes_summary_and_metrics(self):
        with TemporaryDirectory() as td:
            root = Path(td)
            result = run_evaluation(root=root)
            summary = result["summary"]
            eval_dir = Path(result["eval_dir"])

            self.assertEqual(summary["failed_count"], 0)
            self.assertEqual(summary["scenario_count"], 7)
            self.assertEqual(summary["verdict"], "stable")
            self.assertEqual(summary["metrics"]["pass_rate"], 1.0)
            self.assertGreater(summary["metrics"]["malformed_block_rate"], 0.0)
            self.assertGreater(summary["metrics"]["completion_without_executor_done_rate"], 0.0)
            self.assertGreater(summary["metrics"]["max_turn_exhaustion_rate"], 0.0)
            self.assertTrue((eval_dir / "evaluation_summary.json").exists())
            self.assertTrue((eval_dir / "evaluation_summary.md").exists())
            self.assertTrue((eval_dir / "scenario_results.jsonl").exists())

    def test_second_evaluation_compares_to_previous(self):
        with TemporaryDirectory() as td:
            root = Path(td)
            run_evaluation(root=root)
            result = run_evaluation(root=root)

            self.assertEqual(result["summary"]["verdict"], "stable")
            self.assertIsNotNone(result["summary"]["previous_evaluation_id"])

    def test_evaluation_regresses_when_consultation_metric_drops(self):
        with TemporaryDirectory() as td:
            root = Path(td)
            previous_dir = root / "runs" / "eval_previous"
            previous_dir.mkdir(parents=True)
            previous_summary = {
                "evaluation_id": "eval_previous",
                "created_at": "2000-01-01T00:00:00Z",
                "metrics": {
                    "pass_rate": 1.0,
                    "average_advisor_consults_per_run": 1.0,
                },
            }
            (previous_dir / "evaluation_summary.json").write_text(
                json.dumps(previous_summary),
                encoding="utf-8",
            )

            result = run_evaluation(root=root)

            self.assertEqual(result["summary"]["verdict"], "regressed")
            self.assertEqual(result["summary"]["metrics"]["pass_rate"], 1.0)
            self.assertLess(result["summary"]["metrics"]["average_advisor_consults_per_run"], 1.0)

    def test_evaluation_regresses_when_consultation_metric_drops_despite_pass_rate_gain(self):
        with TemporaryDirectory() as td:
            root = Path(td)
            previous_dir = root / "runs" / "eval_previous"
            previous_dir.mkdir(parents=True)
            previous_summary = {
                "evaluation_id": "eval_previous",
                "created_at": "2000-01-01T00:00:00Z",
                "metrics": {
                    "pass_rate": 6 / 7,
                    "average_advisor_consults_per_run": 1.0,
                },
            }
            (previous_dir / "evaluation_summary.json").write_text(
                json.dumps(previous_summary),
                encoding="utf-8",
            )

            result = run_evaluation(root=root)

            self.assertEqual(result["summary"]["verdict"], "regressed")
            self.assertEqual(result["summary"]["metrics"]["pass_rate"], 1.0)
            self.assertLess(result["summary"]["metrics"]["average_advisor_consults_per_run"], 1.0)

    def test_default_evaluation_ignores_previous_live_suite(self):
        with TemporaryDirectory() as td:
            root = Path(td)
            live_result = run_evaluation(
                root=root,
                include_live=True,
                live_executor="fake",
                live_advisor="fake",
            )

            result = run_evaluation(root=root)

            self.assertEqual(live_result["summary"]["scenario_count"], 8)
            self.assertEqual(result["summary"]["scenario_count"], 7)
            self.assertEqual(result["summary"]["verdict"], "stable")
            self.assertIsNone(result["summary"]["previous_evaluation_id"])
