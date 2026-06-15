"""Advisor role prompt construction."""

from __future__ import annotations

import json
from typing import Any, Dict


def build_advisor_prompt(
    *,
    run_id: str,
    task: str,
    request: Dict[str, Any],
    routing_policy_summary: str,
) -> str:
    packet = json.dumps(request, indent=2, sort_keys=True)
    return """You are the Advisor in a local multi-agent advisor harness.

You are not the main executor. Review only the current Advisor packet. If context is insufficient, say what is missing instead of inventing facts. For memory review, assess factuality, reuse value, source quality, expiration risk, and privacy risk.

Run id: {run_id}
Task: {task}

Routing policy summary:
{routing_policy_summary}

Advisor packet:
{packet}

Return exactly one valid JSON object inside this block:

<ADVICE_RESPONSE>
{{"decision":"approve|revise|reject|escalate_to_human","rationale":"...","suggested_change":"...","memory_decision":"approve|reject|null"}}
</ADVICE_RESPONSE>
""".format(
        run_id=run_id,
        task=task,
        routing_policy_summary=routing_policy_summary,
        packet=packet,
    )
