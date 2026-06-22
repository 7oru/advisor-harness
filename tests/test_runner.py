from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import patch

from packages.adapters.base import AgentResult
from packages.adapters.fake import FakeAdapter
from packages.harness.defaults import init_workspace
from packages.harness.database import RunDatabase, database_path
from packages.harness.jsonl import read_jsonl
from packages.harness.review import review_run
from packages.harness.runner import run_task


class FailingAdvisorAdapter:
    def run(self, prompt, *, cwd, session_id=None, output_schema=None, timeout_seconds=None):
        return AgentResult(
            stdout="",
            stderr="advisor command failed",
            final_message="",
            events_path=None,
            exit_code=127,
            session_id=session_id,
            raw_artifacts={
                "backend": "failing-advisor",
                "cwd": cwd,
                "output_schema": output_schema,
                "timeout_seconds": timeout_seconds,
            },
        )


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
            self.assertTrue((result.run_dir / "version_manifest.json").exists())
            self.assertTrue((result.run_dir / "outcome.json").exists())
            self.assertEqual(result.outcome["status"], "completed")
            self.assertEqual(
                result.outcome["version_manifest"]["prompt_versions"]["executor_start"],
                "executor-start.v1",
            )
            self.assertEqual(
                result.outcome["version_manifest"]["memory_schema"]["version"],
                "memory-record.v1",
            )
            self.assertEqual(result.outcome["executor_turn_count"], 2)
            self.assertEqual(result.outcome["advisor_consult_count"], 1)
            self.assertEqual(result.outcome["advisor_guidance_count"], 1)
            self.assertEqual(result.outcome["memory_proposal_count"], 1)
            self.assertEqual(result.outcome["malformed_block_count"], 0)
            self.assertFalse((root / "memory" / "facts.jsonl").exists())

            self.assertTrue(database_path(root).exists())
            payload = RunDatabase.for_root(root).run_payload(result.run_id)
            self.assertEqual(payload["run"]["status"], "completed")
            self.assertEqual(payload["run"]["error_mode"], "none")
            self.assertEqual(
                payload["run"]["outcome"]["version_manifest"]["prompt_versions"]["advisor_guidance"],
                "advisor-guidance.v1",
            )
            self.assertEqual(len(payload["events"]), 7)
            self.assertEqual([turn["role"] for turn in payload["agent_turns"]], ["executor", "advisor", "executor"])
            self.assertEqual(payload["advisor_consults"][0]["turn"], 1)
            self.assertEqual(payload["advisor_guidance"][0]["consult_id"], payload["advisor_consults"][0]["id"])
            self.assertEqual(payload["memory_proposals"][0]["run_id"], result.run_id)

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

    def test_failed_advisor_does_not_persist_or_apply_guidance(self):
        def adapter_factory(name):
            if name == "fake":
                return FakeAdapter()
            if name == "failing":
                return FailingAdvisorAdapter()
            raise AssertionError("unexpected adapter: {}".format(name))

        with TemporaryDirectory() as td:
            root = Path(td)
            init_workspace(root)
            with patch("packages.harness.runner.create_adapter", side_effect=adapter_factory):
                result = run_task(
                    root=root,
                    task="fake smoke task",
                    executor_backend="fake",
                    advisor_backend="failing",
                    timeout_seconds=10,
                )

            self.assertEqual(result.outcome["status"], "advisor_failed")
            self.assertEqual(result.outcome["executor_turn_count"], 1)
            self.assertEqual(result.outcome["advisor_consult_count"], 1)
            self.assertEqual(result.outcome["advisor_guidance_count"], 0)
            self.assertEqual(read_jsonl(result.run_dir / "advisor_guidance.jsonl"), [])
            self.assertFalse((root / "mailbox" / "advisor_guidance.jsonl").exists())

            payload = RunDatabase.for_root(root).run_payload(result.run_id)
            self.assertEqual(payload["run"]["status"], "advisor_failed")
            self.assertEqual(payload["run"]["error_mode"], "advisor_failed")
            self.assertEqual([turn["role"] for turn in payload["agent_turns"]], ["executor", "advisor"])
            self.assertEqual(payload["agent_turns"][1]["exit_code"], 127)
            self.assertEqual(payload["advisor_guidance"], [])

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
