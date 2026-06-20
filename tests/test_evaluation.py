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
