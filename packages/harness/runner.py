"""Main advisor strategy harness runner."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

from packages.adapters import create_adapter
from packages.harness.artifacts import ensure_run_dir, utc_now, write_agent_result, write_outcome, write_text
from packages.harness.database import RunDatabase
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
    db = RunDatabase.for_root(root)
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
    malformed_blocks: List[Dict[str, Any]] = []
    executor_done: Dict[str, Any] = {}
    status = "max_turns_reached"
    next_prompt = build_executor_prompt(
        task=task,
        memory_summary=build_memory_summary(root),
        routing_policy_summary=routing_policy,
        workflow_context=workflow_context,
    )
    write_text(run_dir / "executor_initial.prompt.md", next_prompt)

    run_started_at = utc_now()
    db.record_run_started(
        run_id=run_id,
        task=task,
        executor_backend=executor_backend,
        advisor_backend=advisor_backend,
        executor_session_id=executor_session_id,
        max_turns=max_turns,
        max_advisor_calls=max_advisor_calls,
        created_at=run_started_at,
    )
    _append_event(
        run_dir,
        {
            "type": "run_started",
            "run_id": run_id,
            "task": task,
            "executor_backend": executor_backend,
            "advisor_backend": advisor_backend,
            "executor_session_id": executor_session_id,
            "created_at": run_started_at,
        },
        db=db,
        run_id=run_id,
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
        _record_agent_turn(
            db=db,
            root=root,
            run_dir=run_dir,
            run_id=run_id,
            role="executor",
            turn=turn,
            prompt_text=next_prompt,
            prefix="executor_turn_{}".format(turn),
            result=executor_result,
        )
        _append_event(
            run_dir,
            {
                "type": "executor_turn",
                "turn": turn,
                "exit_code": executor_result.exit_code,
                "final_message": executor_result.final_message,
            },
            db=db,
            run_id=run_id,
        )

        raw_memory = _parse_json_blocks(
            executor_result.final_message,
            "MEMORY_PROPOSAL",
            run_dir=run_dir,
            run_id=run_id,
            turn=turn,
            db=db,
            malformed_blocks=malformed_blocks,
        )
        if malformed_blocks:
            status = "malformed_block"
            break
        for raw in raw_memory:
            proposal = prepare_memory_proposal(run_id, raw)
            memory_proposals.append(proposal)
            append_mailbox_record(root, "memory_proposals", proposal)
            db.record_memory_proposal(proposal)
            _append_event(
                run_dir,
                {"type": "memory_proposal", "turn": turn, "proposal": proposal},
                db=db,
                run_id=run_id,
            )

        done_blocks = _parse_json_blocks(
            executor_result.final_message,
            "EXECUTOR_DONE",
            run_dir=run_dir,
            run_id=run_id,
            turn=turn,
            db=db,
            malformed_blocks=malformed_blocks,
        )
        if malformed_blocks:
            status = "malformed_block"
            break
        raw_consults = _parse_json_blocks(
            executor_result.final_message,
            "ADVISOR_CONSULT",
            run_dir=run_dir,
            run_id=run_id,
            turn=turn,
            db=db,
            malformed_blocks=malformed_blocks,
        )
        if malformed_blocks:
            status = "malformed_block"
            break
        if not raw_consults:
            if executor_result.exit_code != 0:
                status = "executor_failed"
            elif done_blocks:
                executor_done = done_blocks[0]
                status = "completed"
            else:
                status = "executor_stopped_without_done"
            break

        if len(advisor_consults) >= max_advisor_calls:
            status = "advisor_call_limit_reached"
            break

        consult = prepare_advisor_consult(run_id, turn, raw_consults[0])
        advisor_consults.append(consult)
        append_mailbox_record(root, "advisor_consults", consult)
        db.record_advisor_consult(consult)
        _append_event(
            run_dir,
            {"type": "advisor_consult", "turn": turn, "consult": consult},
            db=db,
            run_id=run_id,
        )

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
        _record_agent_turn(
            db=db,
            root=root,
            run_dir=run_dir,
            run_id=run_id,
            role="advisor",
            turn=turn,
            prompt_text=advisor_prompt,
            prefix="advisor_turn_{}".format(turn),
            result=advisor_result,
        )

        if advisor_result.exit_code != 0:
            status = "advisor_failed"
            break

        guidance_blocks = _parse_json_blocks(
            advisor_result.final_message,
            "ADVISOR_GUIDANCE",
            run_dir=run_dir,
            run_id=run_id,
            turn=turn,
            db=db,
            malformed_blocks=malformed_blocks,
        )
        if malformed_blocks:
            status = "malformed_block"
            break
        raw_guidance = guidance_blocks[0] if guidance_blocks else _fallback_guidance(advisor_result.final_message)
        guidance = prepare_advisor_guidance(consult["id"], raw_guidance)
        advisor_guidance.append(guidance)
        append_mailbox_record(root, "advisor_guidance", guidance)
        db.record_advisor_guidance(run_id=run_id, turn=turn, guidance=guidance)
        _append_event(
            run_dir,
            {
                "type": "advisor_guidance",
                "turn": turn,
                "exit_code": advisor_result.exit_code,
                "guidance": guidance,
            },
            db=db,
            run_id=run_id,
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
    write_jsonl(run_dir / "malformed_blocks.jsonl", malformed_blocks)

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
        "malformed_block_count": len(malformed_blocks),
        "malformed_blocks": malformed_blocks,
        "max_turns": max_turns,
        "max_advisor_calls": max_advisor_calls,
        "executor_done": executor_done,
        "completed_at": utc_now(),
    }
    write_outcome(run_dir, outcome)
    db.record_outcome(outcome)
    _append_event(run_dir, {"type": "run_completed", "outcome": outcome}, db=db, run_id=run_id)
    return RunResult(run_id=run_id, run_dir=run_dir, outcome=outcome)


def _parse_json_blocks(
    text: str,
    tag: str,
    *,
    run_dir: Path,
    run_id: str,
    turn: int,
    db: RunDatabase,
    malformed_blocks: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    try:
        return parse_json_blocks(text, tag)
    except ValueError as exc:
        record = {
            "tag": tag,
            "turn": turn,
            "error": str(exc),
        }
        malformed_blocks.append(record)
        db.record_malformed_block(run_id=run_id, turn=turn, block=record)
        _append_event(
            run_dir,
            {"type": "malformed_block", "turn": turn, "block": record},
            db=db,
            run_id=run_id,
        )
        return []


def _append_event(
    run_dir: Path,
    event: Dict[str, Any],
    *,
    db: Optional[RunDatabase] = None,
    run_id: Optional[str] = None,
) -> None:
    payload = dict(event)
    payload.setdefault("created_at", utc_now())
    if run_id:
        payload.setdefault("run_id", run_id)
    append_jsonl(run_dir / "session_events.jsonl", payload)
    if db is not None and run_id:
        db.record_session_event(run_id, payload)


def _record_agent_turn(
    *,
    db: RunDatabase,
    root: Path,
    run_dir: Path,
    run_id: str,
    role: str,
    turn: int,
    prompt_text: str,
    prefix: str,
    result: Any,
) -> None:
    raw_payload = {
        "exit_code": result.exit_code,
        "events_path": result.events_path,
        "session_id": result.session_id,
        "raw_artifacts": result.raw_artifacts,
    }
    db.record_agent_turn(
        run_id=run_id,
        role=role,
        turn=turn,
        exit_code=result.exit_code,
        prompt_text=prompt_text,
        final_message=result.final_message,
        stdout_text=result.stdout,
        stderr_text=result.stderr,
        raw_payload=raw_payload,
        prompt_path=_relative_artifact_path(root, run_dir / "{}.prompt.md".format(prefix)),
        stdout_path=_relative_artifact_path(root, run_dir / "{}.stdout.txt".format(prefix)),
        stderr_path=_relative_artifact_path(root, run_dir / "{}.stderr.txt".format(prefix)),
        raw_path=_relative_artifact_path(root, run_dir / "{}.raw.json".format(prefix)),
    )


def _relative_artifact_path(root: Path, path: Path) -> str:
    try:
        return str(path.relative_to(root))
    except ValueError:
        return str(path)


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
