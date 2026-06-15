"""Routing policy helpers."""

from __future__ import annotations

from pathlib import Path
from typing import Dict, List


def load_policy_summary(root: Path) -> str:
    path = root / "policy" / "routing_policy.md"
    if not path.exists():
        return "No routing policy file found."
    return path.read_text(encoding="utf-8")


def advisor_reasons(advisor_consults: List[Dict[str, object]], memory_proposals: List[Dict[str, object]]) -> List[str]:
    reasons: List[str] = []
    for consult in advisor_consults:
        urgency = str(consult.get("urgency") or "normal")
        reasons.append("advisor_consult:{}".format(urgency))
    for _proposal in memory_proposals:
        reasons.append("memory_proposal")
    return reasons


def should_call_advisor(
    advisor_consults: List[Dict[str, object]],
    memory_proposals: List[Dict[str, object]],
) -> bool:
    return bool(advisor_consults or memory_proposals)
