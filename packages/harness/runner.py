"""Main harness runner."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

from packages.adapters import create_adapter
from packages.harness.artifacts import ensure_run_dir, write_agent_result, write_json, write_outcome, write_text
from packages.harness.defaults import init_workspace
from packages.harness.jsonl import write_jsonl
from packages.harness.mailbox import (
    append_mailbox_record,
    prepare_advice_request,
    prepare_advice_response,
    prepare_memory_proposal,
)
from packages.harness.memory import build_memory_summary, write_approved_memory
from packages.harness.parser import parse_json_blocks
from packages.harness.policy import load_policy_summary
from packages.roles.advisor import build_advisor_prompt
from packages.roles.executor import build_executor_prompt


@dataclass
class RunResult:
    run_id: str
    run_dir: Path
    outcome: Dict[str, Any]


def run_task(
    *,
    root: Path,
    task: str,
    executor_backend: str = "kimi",
    advisor_backend: str = "codex",
    timeout_seconds: Optional[int] = 240,
    workflow_context: Optional[str] = None,
    extra_artifacts: Optional[Dict[str, str]] = None,
) -> RunResult:
    init_workspace(root)
    run_dir = ensure_run_dir(root)
    run_id = run_dir.name
    write_text(run_dir / "task.md", task + "\n")

    for name, content in (extra_artifacts or {}).items():
        write_text(run_dir / name, content)

    routing_policy = load_policy_summary(root)
    executor_prompt = build_executor_prompt(
        task=task,
        memory_summary=build_memory_summary(root),
        routing_policy_summary=routing_policy,
        workflow_context=workflow_context,
    )
    write_text(run_dir / "executor.prompt.md", executor_prompt)

    executor = create_adapter(executor_backend)
    executor_result = executor.run(
        executor_prompt,
        cwd=str(root),
        timeout_seconds=timeout_seconds,
    )
    write_agent_result(run_dir, "executor", executor_result)
    write_text(run_dir / "executor.final.md", executor_result.final_message)

    advice_requests = [
        prepare_advice_request(run_id, raw)
        for raw in parse_json_blocks(executor_result.final_message, "ADVICE_REQUEST")
    ]
    memory_proposals = [
        prepare_memory_proposal(run_id, raw)
        for raw in parse_json_blocks(executor_result.final_message, "MEMORY_PROPOSAL")
    ]

    advisor_requests: List[Dict[str, Any]] = list(advice_requests)
    for proposal in memory_proposals:
        advisor_requests.append(
            prepare_advice_request(
                run_id,
                {
                    "reason": "memory_proposal_review",
                    "task": task,
                    "packet": {"proposal_id": proposal["id"], "proposal": proposal},
                },
            )
        )

    for proposal in memory_proposals:
        append_mailbox_record(root, "memory_proposals", proposal)
    for request in advisor_requests:
        append_mailbox_record(root, "advice_requests", request)

    write_jsonl(run_dir / "memory_proposals.jsonl", memory_proposals)
    write_jsonl(run_dir / "advice_requests.jsonl", advisor_requests)

    advisor_responses: List[Dict[str, Any]] = []
    approved_memory: List[Dict[str, Any]] = []
    advisor = create_adapter(advisor_backend)
    for index, request in enumerate(advisor_requests, start=1):
        advisor_prompt = build_advisor_prompt(
            run_id=run_id,
            task=task,
            request=request,
            routing_policy_summary=routing_policy,
        )
        write_text(run_dir / "advisor_{}.prompt.md".format(index), advisor_prompt)
        advisor_result = advisor.run(
            advisor_prompt,
            cwd=str(root),
            timeout_seconds=timeout_seconds,
        )
        write_agent_result(run_dir, "advisor_{}".format(index), advisor_result)
        write_text(run_dir / "advisor_{}.final.md".format(index), advisor_result.final_message)
        raw_responses = parse_json_blocks(advisor_result.final_message, "ADVICE_RESPONSE")
        raw_response = raw_responses[0] if raw_responses else {}
        response = prepare_advice_response(request["id"], raw_response)
        advisor_responses.append(response)
        append_mailbox_record(root, "advice_responses", response)

        if request["reason"] == "memory_proposal_review" and _response_approves_memory(response):
            proposal = request["packet"]["proposal"]
            approved_memory.append(
                write_approved_memory(root, proposal, run_id=run_id, approved_by=advisor_backend)
            )

    write_jsonl(run_dir / "advisor_reviews.jsonl", advisor_responses)
    write_jsonl(run_dir / "approved_memory.jsonl", approved_memory)

    outcome = {
        "run_id": run_id,
        "status": "completed" if executor_result.exit_code == 0 else "executor_failed",
        "executor_backend": executor_backend,
        "advisor_backend": advisor_backend,
        "executor_exit_code": executor_result.exit_code,
        "advice_request_count": len(advisor_requests),
        "memory_proposal_count": len(memory_proposals),
        "approved_memory_count": len(approved_memory),
        "advisor_response_count": len(advisor_responses),
    }
    write_outcome(run_dir, outcome)
    return RunResult(run_id=run_id, run_dir=run_dir, outcome=outcome)


def _response_approves_memory(response: Dict[str, Any]) -> bool:
    decision = str(response.get("decision") or "").lower()
    memory_decision = str(response.get("memory_decision") or "").lower()
    return decision == "approve" or memory_decision == "approve"
