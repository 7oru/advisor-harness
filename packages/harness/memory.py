"""Approved memory write path."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict

from packages.harness.artifacts import new_id, utc_now
from packages.harness.jsonl import append_jsonl, read_jsonl


MEMORY_FILES = {
    "fact": "facts.jsonl",
    "decision": "decisions.jsonl",
    "preference": "episodes.jsonl",
    "episode": "episodes.jsonl",
    "anti_pattern": "episodes.jsonl",
}


def memory_file_for(memory_type: str) -> str:
    if memory_type not in MEMORY_FILES:
        return "episodes.jsonl"
    return MEMORY_FILES[memory_type]


def approved_memory_record(
    proposal: Dict[str, Any],
    *,
    run_id: str,
    approved_by: str,
) -> Dict[str, Any]:
    memory_type = str(proposal.get("type") or "episode")
    confidence = proposal.get("confidence", 0.0)
    try:
        confidence = float(confidence)
    except (TypeError, ValueError):
        confidence = 0.0
    confidence = max(0.0, min(1.0, confidence))
    return {
        "id": new_id("mem"),
        "type": memory_type,
        "content": str(proposal.get("content") or ""),
        "source_run": run_id,
        "source_excerpt": str(proposal.get("source_excerpt") or ""),
        "confidence": confidence,
        "approved_by": approved_by,
        "created_at": utc_now(),
        "expires_at": proposal.get("expires_at"),
        "tags": proposal.get("tags") or [],
    }


def write_approved_memory(
    root: Path,
    proposal: Dict[str, Any],
    *,
    run_id: str,
    approved_by: str,
) -> Dict[str, Any]:
    record = approved_memory_record(proposal, run_id=run_id, approved_by=approved_by)
    append_jsonl(root / "memory" / memory_file_for(record["type"]), record)
    return record


def build_memory_summary(root: Path, limit: int = 20) -> str:
    lines = []
    for filename in ("facts.jsonl", "decisions.jsonl", "episodes.jsonl"):
        path = root / "memory" / filename
        for record in read_jsonl(path)[-limit:]:
            content = str(record.get("content") or "").strip()
            if content:
                lines.append("- [{}] {}".format(record.get("type") or "memory", content))
    if not lines:
        return "No approved long-term memory yet."
    return "\n".join(lines[-limit:])
