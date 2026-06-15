"""Executor role prompt construction."""

from __future__ import annotations

from typing import Optional


def build_executor_prompt(
    *,
    task: str,
    memory_summary: str,
    routing_policy_summary: str,
    workflow_context: Optional[str] = None,
) -> str:
    context = workflow_context or "No specialized workflow context was provided."
    return """You are the Executor in a local multi-agent advisor harness.

You own the low-cost main task execution. You do not call the Advisor directly, and you never write long-term memory. The harness is the only scheduler and writer.

Task:
{task}

Memory summary:
{memory_summary}

Routing policy summary:
{routing_policy_summary}

Workflow context:
{context}

When the task contains a high-risk claim, low confidence answer, unsupported affirmative claim, conflicting source, or any reusable long-term fact, emit structured blocks for the harness.

Use exactly these optional block formats when relevant:

<ADVICE_REQUEST>
{{"reason":"high_risk_security_claim","task":"short task summary","packet":{{"claim":"...","risk":"high","evidence":"..."}}}}
</ADVICE_REQUEST>

<MEMORY_PROPOSAL>
{{"type":"fact","content":"...","source_excerpt":"...","confidence":0.8,"expires_at":null,"tags":["..."]}}
</MEMORY_PROPOSAL>

Return your normal draft or task result outside the blocks. Keep block contents valid JSON objects.
""".format(
        task=task,
        memory_summary=memory_summary,
        routing_policy_summary=routing_policy_summary,
        context=context,
    )
