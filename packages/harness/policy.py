"""Routing policy helpers."""

from __future__ import annotations

from pathlib import Path
from typing import Dict, List


def load_policy_summary(root: Path) -> str:
    path = root / "policy" / "routing_policy.md"
    if not path.exists():
        return "No routing policy file found."
    return path.read_text(encoding="utf-8")


def advisor_reasons(advice_requests: List[Dict[str, object]], memory_proposals: List[Dict[str, object]]) -> List[str]:
    reasons: List[str] = []
    for request in advice_requests:
        reasons.append(str(request.get("reason") or "advice_request"))
    for _proposal in memory_proposals:
        reasons.append("memory_proposal_review")
    return reasons


def should_call_advisor(
    advice_requests: List[Dict[str, object]],
    memory_proposals: List[Dict[str, object]],
) -> bool:
    return bool(advice_requests or memory_proposals)
