from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase

from packages.harness.defaults import init_workspace
from packages.harness.review import review_run
from packages.harness.runner import run_task


class RunnerTests(TestCase):
    def test_fake_run_writes_artifacts_and_memory(self):
        with TemporaryDirectory() as td:
            root = Path(td)
            init_workspace(root)
            result = run_task(
                root=root,
                task="fake smoke task",
                executor_backend="fake",
                advisor_backend="fake",
                timeout_seconds=10,
            )

            self.assertTrue((result.run_dir / "task.md").exists())
            self.assertTrue((result.run_dir / "executor.stdout.txt").exists())
            self.assertTrue((result.run_dir / "advisor_reviews.jsonl").exists())
            self.assertTrue((result.run_dir / "memory_proposals.jsonl").exists())
            self.assertTrue((result.run_dir / "outcome.json").exists())
            self.assertTrue((root / "memory" / "facts.jsonl").exists())
            self.assertEqual(result.outcome["advice_request_count"], 2)
            self.assertEqual(result.outcome["approved_memory_count"], 1)

    def test_fake_review_writes_review_files(self):
        with TemporaryDirectory() as td:
            root = Path(td)
            init_workspace(root)
            result = run_task(
                root=root,
                task="fake smoke task",
                executor_backend="fake",
                advisor_backend="fake",
                timeout_seconds=10,
            )

            review = review_run(
                root=root,
                run_id=result.run_id,
                advisor_backend="fake",
                timeout_seconds=10,
            )

            self.assertEqual(review["status"], "completed")
            self.assertTrue((result.run_dir / "post_run_review.md").exists())
            self.assertTrue((result.run_dir / "policy_patch_proposal.md").exists())
