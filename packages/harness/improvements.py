"""Structured post-run improvement proposal extraction and validation."""

from __future__ import annotations

import json
from typing import Any, Dict, List, Set

from packages.harness.parser import parse_json_blocks


IMPROVEMENT_PROPOSAL_SCHEMA_VERSION = "improvement-proposals.v1"
IMPROVEMENT_PROPOSAL_TAG = "IMPROVEMENT_PROPOSALS"
REQUIRED_TARGETS = ("memory_schema", "executor_prompt", "advisor_prompt")
ALLOWED_TARGETS = set(REQUIRED_TARGETS)


def extract_improvement_proposals(text: str, *, run_id: str) -> Dict[str, Any]:
    """Extract and validate a structured improvement proposal packet."""
    errors: List[str] = []
    raw: Dict[str, Any] = {}
    try:
        blocks = parse_json_blocks(text, IMPROVEMENT_PROPOSAL_TAG)
    except ValueError as exc:
        blocks = []
        errors.append(str(exc))
    if blocks:
        raw = blocks[0]
    else:
        errors.append("missing <{}> block".format(IMPROVEMENT_PROPOSAL_TAG))
    return normalize_improvement_packet(raw, run_id=run_id, initial_errors=errors)


def normalize_improvement_packet(
    raw: Dict[str, Any],
    *,
    run_id: str,
    initial_errors: List[str] = None,
) -> Dict[str, Any]:
    errors = list(initial_errors or [])
    proposals = raw.get("proposals") if isinstance(raw, dict) else None
    if not isinstance(proposals, list):
        errors.append("proposals must be a list")
        proposals = []

    normalized = []
    seen_targets: Set[str] = set()
    for index, proposal in enumerate(proposals, start=1):
        if not isinstance(proposal, dict):
            errors.append("proposals[{}] must be an object".format(index - 1))
            continue
        item = _normalize_proposal(proposal, index)
        normalized.append(item)
        target = item.get("target")
        if target in ALLOWED_TARGETS:
            seen_targets.add(target)
        _validate_proposal(item, index, errors)

    missing_targets = [target for target in REQUIRED_TARGETS if target not in seen_targets]
    for target in missing_targets:
        errors.append("missing proposal target: {}".format(target))

    schema_version = str(raw.get("schema_version") or IMPROVEMENT_PROPOSAL_SCHEMA_VERSION)
    if schema_version != IMPROVEMENT_PROPOSAL_SCHEMA_VERSION:
        errors.append(
            "schema_version expected {!r}, got {!r}".format(
                IMPROVEMENT_PROPOSAL_SCHEMA_VERSION,
                schema_version,
            )
        )

    packet = {
        "schema_version": schema_version,
        "source_run_id": str(raw.get("source_run_id") or run_id),
        "summary": str(raw.get("summary") or ""),
        "proposals": normalized,
        "validation": {
            "valid": not errors,
            "errors": errors,
            "required_targets": list(REQUIRED_TARGETS),
        },
    }
    return packet


def improvement_proposals_markdown(packet: Dict[str, Any]) -> str:
    lines = [
        "# Improvement Proposals",
        "",
        "- Schema version: `{}`".format(packet.get("schema_version") or ""),
        "- Source run: `{}`".format(packet.get("source_run_id") or ""),
        "- Valid: `{}`".format(packet.get("validation", {}).get("valid")),
        "",
    ]
    summary = str(packet.get("summary") or "").strip()
    if summary:
        lines.extend(["## Summary", "", summary, ""])

    errors = packet.get("validation", {}).get("errors") or []
    lines.extend(["## Validation", ""])
    if errors:
        for error in errors:
            lines.append("- {}".format(error))
    else:
        lines.append("- No validation errors.")

    lines.extend(["", "## Proposals", ""])
    proposals = packet.get("proposals") or []
    if not proposals:
        lines.append("- None")
    for proposal in proposals:
        lines.extend(
            [
                "### {}: {}".format(proposal.get("target"), proposal.get("title")),
                "",
                "- Status: `{}`".format(proposal.get("status")),
                "- Requires human approval: `{}`".format(proposal.get("requires_human_approval")),
                "- Rationale: {}".format(proposal.get("rationale")),
                "- Evidence: {}".format(proposal.get("evidence")),
                "- Proposed change: {}".format(proposal.get("proposed_change")),
                "- Validation plan: {}".format(proposal.get("validation_plan")),
                "",
            ]
        )
    lines.extend(["## JSON", "", "```json", json.dumps(packet, indent=2, sort_keys=True), "```"])
    return "\n".join(lines) + "\n"


def _normalize_proposal(proposal: Dict[str, Any], index: int) -> Dict[str, Any]:
    target = str(proposal.get("target") or "")
    return {
        "id": str(proposal.get("id") or "{}_{}".format(target or "proposal", index)),
        "target": target,
        "title": str(proposal.get("title") or ""),
        "rationale": str(proposal.get("rationale") or ""),
        "evidence": str(proposal.get("evidence") or ""),
        "proposed_change": str(proposal.get("proposed_change") or ""),
        "validation_plan": str(proposal.get("validation_plan") or ""),
        "requires_human_approval": bool(proposal.get("requires_human_approval")),
        "status": str(proposal.get("status") or "proposed"),
    }


def _validate_proposal(item: Dict[str, Any], index: int, errors: List[str]) -> None:
    prefix = "proposals[{}]".format(index - 1)
    if item["target"] not in ALLOWED_TARGETS:
        errors.append("{}.target must be one of {}".format(prefix, sorted(ALLOWED_TARGETS)))
    for key in ("title", "rationale", "evidence", "proposed_change", "validation_plan"):
        if not item[key].strip():
            errors.append("{}.{} must be a non-empty string".format(prefix, key))
    if item["requires_human_approval"] is not True:
        errors.append("{}.requires_human_approval must be true".format(prefix))
    if item["status"] != "proposed":
        errors.append("{}.status must be 'proposed'".format(prefix))

