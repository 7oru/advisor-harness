"""Main advisor strategy harness runner."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

from packages.adapters import create_adapter
from packages.harness.artifacts import ensure_run_dir, utc_now, write_agent_result, write_outcome, write_text
from packages.harness.defaults import init_workspace
from packages.harness.jsonl import append_jsonl, write_jsonl
from packages.harness.mailbox import (
    append_mailbox_record,
    prepare_advisor_consult,
    prepare_advisor_guidance,
    prepare_memory_proposal,
)
from packages.harness.memory import build_memory_summary
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
    max_turns: int = 3,
    max_advisor_calls: int = 3,
) -> RunResult:
    init_workspace(root)
    run_dir = ensure_run_dir(root)
    run_id = run_dir.name
    executor_session_id = "{}_executor".format(run_id)
    write_text(run_dir / "task.md", task + "\n")

    for name, content in (extra_artifacts or {}).items():
        write_text(run_dir / name, content)

    routing_policy = load_policy_summary(root)
    executor = create_adapter(executor_backend)
    advisor = create_adapter(advisor_backend)

    advisor_consults: List[Dict[str, Any]] = []
    advisor_guidance: List[Dict[str, Any]] = []
    memory_proposals: List[Dict[str, Any]] = []
    executor_done: Dict[str, Any] = {}
    status = "max_turns_reached"
    next_prompt = build_executor_prompt(
        task=task,
        memory_summary=build_memory_summary(root),
        routing_policy_summary=routing_policy,
        workflow_context=workflow_context,
    )
    write_text(run_dir / "executor_initial.prompt.md", next_prompt)

    _append_event(
        run_dir,
        {
            "type": "run_started",
            "run_id": run_id,
            "task": task,
            "executor_backend": executor_backend,
            "advisor_backend": advisor_backend,
            "executor_session_id": executor_session_id,
        },
    )

    for turn in range(1, max_turns + 1):
        write_text(run_dir / "executor_turn_{}.prompt.md".format(turn), next_prompt)
        executor_result = executor.run(
            next_prompt,
            cwd=str(root),
            session_id=executor_session_id,
            timeout_seconds=timeout_seconds,
        )
        write_agent_result(run_dir, "executor_turn_{}".format(turn), executor_result)
        write_text(run_dir / "executor_turn_{}.final.md".format(turn), executor_result.final_message)
        _append_event(
            run_dir,
            {
                "type": "executor_turn",
                "turn": turn,
                "exit_code": executor_result.exit_code,
                "final_message": executor_result.final_message,
            },
        )

        raw_memory = parse_json_blocks(executor_result.final_message, "MEMORY_PROPOSAL")
        for raw in raw_memory:
            proposal = prepare_memory_proposal(run_id, raw)
            memory_proposals.append(proposal)
            append_mailbox_record(root, "memory_proposals", proposal)
            _append_event(run_dir, {"type": "memory_proposal", "turn": turn, "proposal": proposal})

        done_blocks = parse_json_blocks(executor_result.final_message, "EXECUTOR_DONE")
        if done_blocks:
            executor_done = done_blocks[0]

        raw_consults = parse_json_blocks(executor_result.final_message, "ADVISOR_CONSULT")
        if not raw_consults:
            status = "completed" if executor_result.exit_code == 0 else "executor_failed"
            break

        if len(advisor_consults) >= max_advisor_calls:
            status = "advisor_call_limit_reached"
            break

        consult = prepare_advisor_consult(run_id, turn, raw_consults[0])
        advisor_consults.append(consult)
        append_mailbox_record(root, "advisor_consults", consult)
        _append_event(run_dir, {"type": "advisor_consult", "turn": turn, "consult": consult})

        session_context = _session_context(run_dir)
        advisor_prompt = build_advisor_prompt(
            run_id=run_id,
            task=task,
            consult=consult,
            session_context=session_context,
            routing_policy_summary=routing_policy,
        )
        write_text(run_dir / "advisor_turn_{}.prompt.md".format(turn), advisor_prompt)
        advisor_result = advisor.run(
            advisor_prompt,
            cwd=str(root),
            timeout_seconds=timeout_seconds,
        )
        write_agent_result(run_dir, "advisor_turn_{}".format(turn), advisor_result)
        write_text(run_dir / "advisor_turn_{}.final.md".format(turn), advisor_result.final_message)

        guidance_blocks = parse_json_blocks(advisor_result.final_message, "ADVISOR_GUIDANCE")
        raw_guidance = guidance_blocks[0] if guidance_blocks else _fallback_guidance(advisor_result.final_message)
        guidance = prepare_advisor_guidance(consult["id"], raw_guidance)
        advisor_guidance.append(guidance)
        append_mailbox_record(root, "advisor_guidance", guidance)
        _append_event(
            run_dir,
            {
                "type": "advisor_guidance",
                "turn": turn,
                "exit_code": advisor_result.exit_code,
                "guidance": guidance,
            },
        )

        if guidance.get("stop_signal"):
            status = "advisor_stop_signal"
            break

        next_prompt = _resume_prompt(task=task, guidance=guidance)
    else:
        status = "completed" if executor_done else "max_turns_reached"

    write_jsonl(run_dir / "advisor_consults.jsonl", advisor_consults)
    write_jsonl(run_dir / "advisor_guidance.jsonl", advisor_guidance)
    write_jsonl(run_dir / "memory_proposals.jsonl", memory_proposals)

    outcome = {
        "run_id": run_id,
        "status": status,
        "executor_backend": executor_backend,
        "advisor_backend": advisor_backend,
        "executor_session_id": executor_session_id,
        "executor_turn_count": min(max_turns, _count_executor_turns(run_dir)),
        "advisor_consult_count": len(advisor_consults),
        "advisor_guidance_count": len(advisor_guidance),
        "memory_proposal_count": len(memory_proposals),
        "max_turns": max_turns,
        "max_advisor_calls": max_advisor_calls,
        "executor_done": executor_done,
    }
    write_outcome(run_dir, outcome)
    _append_event(run_dir, {"type": "run_completed", "outcome": outcome})
    return RunResult(run_id=run_id, run_dir=run_dir, outcome=outcome)


def _append_event(run_dir: Path, event: Dict[str, Any]) -> None:
    payload = dict(event)
    payload.setdefault("created_at", utc_now())
    append_jsonl(run_dir / "session_events.jsonl", payload)


def _session_context(run_dir: Path, max_chars: int = 24000) -> str:
    path = run_dir / "session_events.jsonl"
    if not path.exists():
        return ""
    text = path.read_text(encoding="utf-8")
    if len(text) <= max_chars:
        return text
    return text[-max_chars:]


def _fallback_guidance(final_message: str) -> Dict[str, Any]:
    return {
        "guidance": final_message.strip(),
        "rationale": "Advisor did not emit ADVISOR_GUIDANCE; harness wrapped final message.",
        "stop_signal": False,
    }


def _resume_prompt(*, task: str, guidance: Dict[str, Any]) -> str:
    return """Advisor guidance to Executor:
{guidance}

Continue the original task:
{task}

Apply the guidance if it is consistent with your evidence. If the task is complete, include an EXECUTOR_DONE block. If another hard decision remains, emit one ADVISOR_CONSULT block and stop.
""".format(
        guidance=json.dumps(guidance, indent=2, sort_keys=True),
        task=task,
    )


def _count_executor_turns(run_dir: Path) -> int:
    return len(list(run_dir.glob("executor_turn_*.final.md")))
