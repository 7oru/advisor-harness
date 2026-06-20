from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase

from packages.harness.database import RunDatabase, database_path


class RunDatabaseTests(TestCase):
    def test_records_and_queries_run_state(self):
        with TemporaryDirectory() as td:
            root = Path(td)
            db = RunDatabase.for_root(root)
            db.record_run_started(
                run_id="run_test_1",
                task="Investigate a hard decision",
                executor_backend="fake",
                advisor_backend="fake",
                executor_session_id="run_test_1_executor",
                max_turns=3,
                max_advisor_calls=2,
                created_at="2026-06-20T00:00:00Z",
            )
            db.record_session_event(
                "run_test_1",
                {"type": "run_started", "created_at": "2026-06-20T00:00:00Z"},
            )
            db.record_agent_turn(
                run_id="run_test_1",
                role="executor",
                turn=1,
                exit_code=0,
                prompt_text="prompt",
                final_message="final",
                stdout_text="stdout",
                stderr_text="stderr",
                raw_payload={"session_id": "run_test_1_executor"},
                prompt_path="runs/run_test_1/executor_turn_1.prompt.md",
                stdout_path="runs/run_test_1/executor_turn_1.stdout.txt",
                stderr_path="runs/run_test_1/executor_turn_1.stderr.txt",
                raw_path="runs/run_test_1/executor_turn_1.raw.json",
                created_at="2026-06-20T00:00:01Z",
            )
            consult = {
                "id": "adv_consult_1",
                "run_id": "run_test_1",
                "turn": 1,
                "question": "Which path?",
                "context": "A hard decision exists.",
                "options": ["small", "large"],
                "preferred_option": "small",
                "urgency": "normal",
                "created_at": "2026-06-20T00:00:02Z",
            }
            db.record_advisor_consult(consult)
            db.record_advisor_guidance(
                run_id="run_test_1",
                turn=1,
                guidance={
                    "id": "adv_guidance_1",
                    "consult_id": "adv_consult_1",
                    "guidance": "Choose small.",
                    "rationale": "It is enough.",
                    "stop_signal": False,
                    "created_at": "2026-06-20T00:00:03Z",
                },
            )
            db.record_memory_proposal(
                {
                    "id": "mem_prop_1",
                    "run_id": "run_test_1",
                    "type": "episode",
                    "content": "Consulted advisor.",
                    "source_excerpt": "A hard decision exists.",
                    "confidence": 0.8,
                    "expires_at": None,
                    "tags": ["fake"],
                    "created_at": "2026-06-20T00:00:04Z",
                }
            )
            malformed = {"tag": "ADVISOR_CONSULT", "turn": 1, "error": "invalid JSON"}
            db.record_malformed_block(run_id="run_test_1", turn=1, block=malformed)
            db.record_outcome(
                {
                    "run_id": "run_test_1",
                    "status": "malformed_block",
                    "executor_turn_count": 1,
                    "advisor_consult_count": 1,
                    "advisor_guidance_count": 1,
                    "memory_proposal_count": 1,
                    "malformed_block_count": 1,
                    "malformed_blocks": [malformed],
                    "executor_done": {},
                    "completed_at": "2026-06-20T00:00:05Z",
                }
            )

            self.assertTrue(database_path(root).exists())

            run = db.get_run("run_test_1")
            self.assertEqual(run["status"], "malformed_block")
            self.assertEqual(run["error_mode"], "malformed:ADVISOR_CONSULT")
            self.assertEqual(run["advisor_consult_count"], 1)
            self.assertEqual(run["outcome"]["status"], "malformed_block")

            runs = db.list_runs(
                status="malformed_block",
                backend="fake",
                advisor_call_count=1,
                task="hard",
                error_mode="malformed:ADVISOR_CONSULT",
            )
            self.assertEqual([item["run_id"] for item in runs], ["run_test_1"])

            payload = db.run_payload("run_test_1")
            self.assertEqual(payload["events"][0]["type"], "run_started")
            self.assertEqual(payload["agent_turns"][0]["raw_json"]["session_id"], "run_test_1_executor")
            self.assertEqual(payload["advisor_consults"][0]["question"], "Which path?")
            self.assertEqual(payload["advisor_guidance"][0]["guidance"], "Choose small.")
            self.assertEqual(payload["memory_proposals"][0]["content"], "Consulted advisor.")
            self.assertEqual(payload["malformed_blocks"][0]["tag"], "ADVISOR_CONSULT")
