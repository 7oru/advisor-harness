"""Advisor role prompt construction."""

from __future__ import annotations

import json
from typing import Any, Dict


ADVISOR_PROMPT_VERSION = "advisor-guidance.v1"


def build_advisor_prompt(
    *,
    run_id: str,
    task: str,
    consult: Dict[str, Any],
    session_context: str,
    routing_policy_summary: str,
) -> str:
    packet = json.dumps(consult, indent=2, sort_keys=True)
    return """You are the Advisor in a local multi-agent advisor strategy harness.

You are not the main executor. Do not call tools, do not mutate files, and do not produce a user-facing deliverable. Review the shared session context and the current consultation request, then return guidance for the Executor to apply before it continues.

Run id: {run_id}
Task: {task}

Routing policy summary:
{routing_policy_summary}

Shared session context:
{session_context}

Current consultation request:
{packet}

Return exactly one valid JSON object inside this block:

<ADVISOR_GUIDANCE>
{{"guidance":"...","rationale":"...","stop_signal":false}}
</ADVISOR_GUIDANCE>
""".format(
        run_id=run_id,
        task=task,
        routing_policy_summary=routing_policy_summary,
        session_context=session_context,
        packet=packet,
    )
