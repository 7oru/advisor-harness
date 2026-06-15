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
        if "advisor packet:" in prompt_lower:
            final = self._advisor_response()
        elif "post-run review request:" in prompt_lower or "post run review request:" in prompt_lower:
            final = self._post_run_review()
        else:
            final = self._executor_response()
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

    def _executor_response(self) -> str:
        advice_request = {
            "reason": "fake_high_risk_security_claim",
            "task": "fake smoke task",
            "packet": {
                "claim": "The product supports SSO.",
                "risk": "high",
                "evidence": "Fake adapter evidence excerpt.",
            },
        }
        memory_proposal = {
            "type": "fact",
            "content": "Fake smoke memory: the product supports SSO.",
            "source_excerpt": "Fake adapter evidence excerpt.",
            "confidence": 0.9,
            "expires_at": None,
            "tags": ["fake", "smoke"],
        }
        return "\n".join(
            [
                "Fake executor completed.",
                "<ADVICE_REQUEST>",
                json.dumps(advice_request, indent=2, sort_keys=True),
                "</ADVICE_REQUEST>",
                "<MEMORY_PROPOSAL>",
                json.dumps(memory_proposal, indent=2, sort_keys=True),
                "</MEMORY_PROPOSAL>",
            ]
        )

    def _advisor_response(self) -> str:
        response = {
            "decision": "approve",
            "rationale": "Fake advisor approves deterministic smoke packet.",
            "suggested_change": "",
            "memory_decision": "approve",
        }
        return "\n".join(
            [
                "Fake advisor reviewed the packet.",
                "<ADVICE_RESPONSE>",
                json.dumps(response, indent=2, sort_keys=True),
                "</ADVICE_RESPONSE>",
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
