"""Deterministic adapter used by tests and dry-runs."""

from __future__ import annotations

import json
from typing import Optional

from packages.adapters.base import AgentAdapter, AgentResult


class FakeAdapter(AgentAdapter):
    name = "fake"

    @classmethod
    def version(cls) -> str:
        return "fake-adapter 0.1.0"

    def run(
        self,
        prompt: str,
        *,
        cwd: str,
        session_id: Optional[str] = None,
        output_schema: Optional[str] = None,
        timeout_seconds: Optional[int] = None,
    ) -> AgentResult:
        prompt_lower = prompt.lower()
        if "current consultation request:" in prompt_lower:
            if "eval malformed guidance" in prompt_lower:
                final = self._malformed_guidance()
            elif "eval advisor stop" in prompt_lower:
                final = self._advisor_stop_guidance()
            else:
                final = self._advisor_guidance()
        elif "post-run review request:" in prompt_lower or "post run review request:" in prompt_lower:
            final = self._post_run_review()
        elif "advisor guidance to executor:" in prompt_lower:
            if "eval max turns" in prompt_lower:
                final = self._executor_consult(question="Should the fake executor keep consulting?")
            else:
                final = self._executor_done()
        elif "stop without done" in prompt_lower or "eval missing done" in prompt_lower:
            final = "Fake executor stopped without an EXECUTOR_DONE block."
        elif "eval no consult completion" in prompt_lower:
            final = self._executor_done(
                "Fake executor completed without advisor guidance because no hard decision was present."
            )
        elif "eval malformed consult" in prompt_lower:
            final = self._malformed_consult()
        else:
            final = self._executor_consult()
        return AgentResult(
            stdout=final,
            stderr="",
            final_message=final,
            events_path=None,
            exit_code=0,
            session_id=session_id,
            raw_artifacts={
                "backend": self.name,
                "cwd": cwd,
                "output_schema": output_schema,
                "timeout_seconds": timeout_seconds,
            },
        )

    def _executor_consult(self, question: str = "Should the fake executor choose the simple scaffold path?") -> str:
        consult = {
            "question": question,
            "context": "The fake executor is simulating a hard decision before finalizing.",
            "options": ["simple scaffold", "overbuilt framework"],
            "preferred_option": "simple scaffold",
            "urgency": "normal",
        }
        memory_proposal = {
            "type": "episode",
            "content": "Fake smoke run consulted the advisor before finalizing.",
            "source_excerpt": "The fake executor is simulating a hard decision before finalizing.",
            "confidence": 0.9,
            "expires_at": None,
            "tags": ["fake", "smoke"],
        }
        return "\n".join(
            [
                "Fake executor is pausing for advisor guidance.",
                "<ADVISOR_CONSULT>",
                json.dumps(consult, indent=2, sort_keys=True),
                "</ADVISOR_CONSULT>",
                "<MEMORY_PROPOSAL>",
                json.dumps(memory_proposal, indent=2, sort_keys=True),
                "</MEMORY_PROPOSAL>",
            ]
        )

    def _malformed_consult(self) -> str:
        return "\n".join(
            [
                "Fake executor emitted malformed consultation.",
                "<ADVISOR_CONSULT>",
                '{"question": ',
                "</ADVISOR_CONSULT>",
            ]
        )

    def _advisor_guidance(self) -> str:
        guidance = {
            "guidance": "Choose the simple scaffold path and verify the resume loop.",
            "rationale": "The objective is a minimal advisor strategy scaffold, not a framework expansion.",
            "stop_signal": False,
        }
        return "\n".join(
            [
                "Fake advisor returned guidance.",
                "<ADVISOR_GUIDANCE>",
                json.dumps(guidance, indent=2, sort_keys=True),
                "</ADVISOR_GUIDANCE>",
            ]
        )

    def _advisor_stop_guidance(self) -> str:
        guidance = {
            "guidance": "Stop the run because the fake advisor stop regression requested it.",
            "rationale": "This deterministic scenario verifies advisor stop-signal handling.",
            "stop_signal": True,
        }
        return "\n".join(
            [
                "Fake advisor returned stop guidance.",
                "<ADVISOR_GUIDANCE>",
                json.dumps(guidance, indent=2, sort_keys=True),
                "</ADVISOR_GUIDANCE>",
            ]
        )

    def _malformed_guidance(self) -> str:
        return "\n".join(
            [
                "Fake advisor emitted malformed guidance.",
                "<ADVISOR_GUIDANCE>",
                '{"guidance": ',
                "</ADVISOR_GUIDANCE>",
            ]
        )

    def _executor_done(
        self,
        summary: str = "Fake executor applied advisor guidance and completed the task.",
    ) -> str:
        done = {
            "status": "completed",
            "summary": summary,
        }
        return "\n".join(
            [
                "Fake executor applied advisor guidance and completed.",
                "<EXECUTOR_DONE>",
                json.dumps(done, indent=2, sort_keys=True),
                "</EXECUTOR_DONE>",
            ]
        )

    def _post_run_review(self) -> str:
        return "\n".join(
            [
                "## Post-Run Review",
                "",
                "- missed advisor opportunities: none in fake run",
                "- unnecessary advisor calls: none in fake run",
                "- bad memory proposals: none in fake run",
                "",
                "## Suggested Routing Policy Patch",
                "",
                "No policy changes suggested for fake smoke run.",
            ]
        )
