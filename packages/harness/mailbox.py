"""Structured mailbox queues for agent-to-harness packets."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Iterable, List

from packages.harness.artifacts import new_id, utc_now
from packages.harness.jsonl import append_jsonl, read_jsonl


def mailbox_path(root: Path, name: str) -> Path:
    return root / "mailbox" / "{}.jsonl".format(name)


def append_mailbox_record(root: Path, name: str, record: Dict[str, Any]) -> Dict[str, Any]:
    append_jsonl(mailbox_path(root, name), record)
    return record


def read_mailbox(root: Path, name: str) -> List[Dict[str, Any]]:
    return read_jsonl(mailbox_path(root, name))


def prepare_advice_request(run_id: str, raw: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "id": raw.get("id") or new_id("adv_req"),
        "run_id": run_id,
        "reason": raw.get("reason") or "unspecified",
        "task": raw.get("task") or "",
        "packet": raw.get("packet") or {},
        "created_at": raw.get("created_at") or utc_now(),
    }


def prepare_advice_response(request_id: str, raw: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "id": raw.get("id") or new_id("adv_res"),
        "request_id": request_id,
        "decision": raw.get("decision") or "escalate_to_human",
        "rationale": raw.get("rationale") or "",
        "suggested_change": raw.get("suggested_change") or "",
        "created_at": raw.get("created_at") or utc_now(),
        "memory_decision": raw.get("memory_decision"),
    }


def prepare_memory_proposal(run_id: str, raw: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "id": raw.get("id") or new_id("mem_prop"),
        "run_id": run_id,
        "type": raw.get("type") or "episode",
        "content": raw.get("content") or "",
        "source_excerpt": raw.get("source_excerpt") or "",
        "confidence": raw.get("confidence", 0.0),
        "expires_at": raw.get("expires_at"),
        "tags": raw.get("tags") or [],
        "created_at": raw.get("created_at") or utc_now(),
    }


def append_many(root: Path, name: str, records: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
    written = []
    for record in records:
        append_mailbox_record(root, name, record)
        written.append(record)
    return written
