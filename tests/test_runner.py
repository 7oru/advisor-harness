from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase

from packages.harness.defaults import init_workspace
from packages.harness.review import review_run
from packages.harness.runner import run_task


class RunnerTests(TestCase):
    def test_fake_run_writes_consult_guidance_resume_artifacts(self):
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
            self.assertTrue((result.run_dir / "session_events.jsonl").exists())
            self.assertTrue((result.run_dir / "executor_turn_1.stdout.txt").exists())
            self.assertTrue((result.run_dir / "executor_turn_2.stdout.txt").exists())
            self.assertTrue((result.run_dir / "advisor_consults.jsonl").exists())
            self.assertTrue((result.run_dir / "advisor_guidance.jsonl").exists())
            self.assertTrue((result.run_dir / "memory_proposals.jsonl").exists())
            self.assertTrue((result.run_dir / "outcome.json").exists())
            self.assertEqual(result.outcome["status"], "completed")
            self.assertEqual(result.outcome["executor_turn_count"], 2)
            self.assertEqual(result.outcome["advisor_consult_count"], 1)
            self.assertEqual(result.outcome["advisor_guidance_count"], 1)
            self.assertEqual(result.outcome["memory_proposal_count"], 1)
            self.assertEqual(result.outcome["malformed_block_count"], 0)
            self.assertFalse((root / "memory" / "facts.jsonl").exists())

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

    def test_run_requires_executor_done_for_completed_status(self):
        with TemporaryDirectory() as td:
            root = Path(td)
            init_workspace(root)
            result = run_task(
                root=root,
                task="stop without done",
                executor_backend="fake",
                advisor_backend="fake",
                timeout_seconds=10,
            )

            self.assertEqual(result.outcome["status"], "executor_stopped_without_done")
            self.assertEqual(result.outcome["executor_turn_count"], 1)
            self.assertEqual(result.outcome["advisor_consult_count"], 0)
            self.assertEqual(result.outcome["executor_done"], {})

    def test_malformed_consult_sets_malformed_status(self):
        with TemporaryDirectory() as td:
            root = Path(td)
            init_workspace(root)
            result = run_task(
                root=root,
                task="eval malformed consult",
                executor_backend="fake",
                advisor_backend="fake",
                timeout_seconds=10,
            )

            self.assertEqual(result.outcome["status"], "malformed_block")
            self.assertEqual(result.outcome["malformed_block_count"], 1)
            self.assertEqual(result.outcome["malformed_blocks"][0]["tag"], "ADVISOR_CONSULT")
            self.assertTrue((result.run_dir / "malformed_blocks.jsonl").exists())

    def test_advisor_stop_signal_sets_status(self):
        with TemporaryDirectory() as td:
            root = Path(td)
            init_workspace(root)
            result = run_task(
                root=root,
                task="eval advisor stop",
                executor_backend="fake",
                advisor_backend="fake",
                timeout_seconds=10,
            )

            self.assertEqual(result.outcome["status"], "advisor_stop_signal")
            self.assertEqual(result.outcome["advisor_consult_count"], 1)
            self.assertEqual(result.outcome["advisor_guidance_count"], 1)

    def test_max_turns_reached_status(self):
        with TemporaryDirectory() as td:
            root = Path(td)
            init_workspace(root)
            result = run_task(
                root=root,
                task="eval max turns",
                executor_backend="fake",
                advisor_backend="fake",
                timeout_seconds=10,
                max_turns=2,
                max_advisor_calls=2,
            )

            self.assertEqual(result.outcome["status"], "max_turns_reached")
            self.assertEqual(result.outcome["executor_turn_count"], 2)
            self.assertEqual(result.outcome["advisor_consult_count"], 2)
