"""Post-run review command support."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Optional

from packages.adapters import create_adapter
from packages.harness.artifacts import write_agent_result, write_json, write_text
from packages.harness.improvements import extract_improvement_proposals, improvement_proposals_markdown
from packages.harness.jsonl import read_jsonl
from packages.harness.policy import load_policy_summary


def review_run(
    *,
    root: Path,
    run_id: str,
    advisor_backend: str = "codex",
    timeout_seconds: Optional[int] = 240,
) -> Dict[str, Any]:
    run_dir = root / "runs" / run_id
    if not run_dir.exists():
        raise FileNotFoundError("run not found: {}".format(run_id))

    prompt = build_post_run_review_prompt(root, run_dir, run_id)
    write_text(run_dir / "post_run_review.prompt.md", prompt)
    advisor = create_adapter(advisor_backend)
    result = advisor.run(prompt, cwd=str(root), timeout_seconds=timeout_seconds)
    write_agent_result(run_dir, "post_run_review_advisor", result)
    write_text(run_dir / "post_run_review.md", result.final_message)
    write_text(run_dir / "policy_patch_proposal.md", _extract_policy_patch(result.final_message))
    improvement_packet = extract_improvement_proposals(result.final_message, run_id=run_id)
    write_json(run_dir / "improvement_proposals.json", improvement_packet)
    write_text(run_dir / "improvement_proposals.md", improvement_proposals_markdown(improvement_packet))
    outcome = {
        "run_id": run_id,
        "advisor_backend": advisor_backend,
        "advisor_exit_code": result.exit_code,
        "improvement_proposal_count": len(improvement_packet.get("proposals") or []),
        "improvement_proposals_valid": bool(improvement_packet.get("validation", {}).get("valid")),
        "status": "completed" if result.exit_code == 0 else "advisor_failed",
    }
    write_json(run_dir / "post_run_review_outcome.json", outcome)
    return outcome


def build_post_run_review_prompt(root: Path, run_dir: Path, run_id: str) -> str:
    packet = {
        "run_id": run_id,
        "task": _read_optional(run_dir / "task.md"),
        "outcome": _read_json_optional(run_dir / "outcome.json"),
        "session_events": read_jsonl(run_dir / "session_events.jsonl"),
        "advisor_consults": read_jsonl(run_dir / "advisor_consults.jsonl"),
        "advisor_guidance": read_jsonl(run_dir / "advisor_guidance.jsonl"),
        "memory_proposals": read_jsonl(run_dir / "memory_proposals.jsonl"),
        "version_manifest": _read_json_optional(run_dir / "version_manifest.json"),
        "memory_schema": _read_json_optional(root / "memory" / "schema.json"),
        "executor_initial_prompt": _read_optional(run_dir / "executor_initial.prompt.md"),
        "latest_advisor_prompt": _read_latest_optional(run_dir, "advisor_turn_*.prompt.md"),
    }
    return """You are the Advisor doing a post-run review.

Post-run review request:
{packet}

Routing policy:
{policy}

Review for missed advisor opportunities, unnecessary advisor calls, poor guidance application, bad memory proposals, risky unsupported claims, and routing policy improvements.

Write Markdown with these sections:

## Post-Run Review

## Suggested Routing Policy Patch

Then return exactly one valid JSON object inside this block:

<IMPROVEMENT_PROPOSALS>
{{
  "schema_version": "improvement-proposals.v1",
  "summary": "...",
  "proposals": [
    {{
      "id": "mem_schema_1",
      "target": "memory_schema",
      "title": "...",
      "rationale": "...",
      "evidence": "...",
      "proposed_change": "...",
      "validation_plan": "...",
      "requires_human_approval": true,
      "status": "proposed"
    }},
    {{
      "id": "executor_prompt_1",
      "target": "executor_prompt",
      "title": "...",
      "rationale": "...",
      "evidence": "...",
      "proposed_change": "...",
      "validation_plan": "...",
      "requires_human_approval": true,
      "status": "proposed"
    }},
    {{
      "id": "advisor_prompt_1",
      "target": "advisor_prompt",
      "title": "...",
      "rationale": "...",
      "evidence": "...",
      "proposed_change": "...",
      "validation_plan": "...",
      "requires_human_approval": true,
      "status": "proposed"
    }}
  ]
}}
</IMPROVEMENT_PROPOSALS>

Include one proposal for each target: memory_schema, executor_prompt, and advisor_prompt. Use "No change recommended" as the proposed_change when a target does not need changes. These proposals are advisory only and require human approval; do not claim that any file was changed.
""".format(
        packet=json.dumps(packet, indent=2, sort_keys=True),
        policy=load_policy_summary(root),
    )


def _read_optional(path: Path) -> str:
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8")


def _read_json_optional(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {}
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return value if isinstance(value, dict) else {}


def _read_latest_optional(directory: Path, pattern: str) -> str:
    paths = sorted(directory.glob(pattern))
    if not paths:
        return ""
    return _read_optional(paths[-1])


def _extract_policy_patch(text: str) -> str:
    marker = "## Suggested Routing Policy Patch"
    index = text.find(marker)
    if index == -1:
        return "# Suggested Routing Policy Patch\n\nNo explicit policy patch section found.\n"
    return text[index:].strip() + "\n"
