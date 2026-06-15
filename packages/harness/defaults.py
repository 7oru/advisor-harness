"""Default local files used by ``maa init``."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable, Tuple


DEFAULT_DIRECTORIES = (
    "apps/security_questionnaire/prompts",
    "apps/security_questionnaire/workflows",
    "apps/security_questionnaire/sample_inputs",
    "apps/security_questionnaire/sample_outputs",
    "policy",
    "memory",
    "mailbox",
    "runs",
)

ROUTING_POLICY_MD = """# Routing Policy

Advisor should be invoked when any of the following are present:

- Executor explicitly emits an advice request.
- Executor emits a memory proposal.
- A security questionnaire answer makes a high-risk security, privacy, compliance, or legal-adjacent claim.
- An answer is affirmative but has no evidence.
- Sources conflict or appear stale.
- Executor marks low confidence.
- Post-run review is requested.

Advisor packets must be narrow and structured. Do not send an unbounded transcript when a focused packet is enough.
"""

POST_RUN_REVIEW_MD = """# Post-Run Review Policy

The advisor reviews completed runs for:

- missed advisor opportunities
- unnecessary advisor calls
- bad memory proposals
- risky or unsupported claims
- suggested routing policy improvements

Policy patch proposals are advisory only. The harness must not auto-edit policy files.
"""

MEMORY_README_MD = """# Memory

Long-term memory is not a transcript. It stores reusable facts, decisions, preferences, episodes, and anti-patterns only after review.

Runtime memory JSONL files are gitignored by default:

- `facts.jsonl`
- `decisions.jsonl`
- `episodes.jsonl`

Every approved memory record must include a source run, source excerpt, confidence, approver, and timestamp.
"""

MEMORY_SCHEMA = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "title": "Multi-Agent Advisor Memory Record",
    "type": "object",
    "required": [
        "id",
        "type",
        "content",
        "source_run",
        "source_excerpt",
        "confidence",
        "approved_by",
        "created_at",
        "expires_at",
        "tags",
    ],
    "properties": {
        "id": {"type": "string"},
        "type": {
            "type": "string",
            "enum": ["fact", "decision", "preference", "episode", "anti_pattern"],
        },
        "content": {"type": "string"},
        "source_run": {"type": "string"},
        "source_excerpt": {"type": "string"},
        "confidence": {"type": "number", "minimum": 0, "maximum": 1},
        "approved_by": {"type": "string"},
        "created_at": {"type": "string"},
        "expires_at": {"type": ["string", "null"]},
        "tags": {"type": "array", "items": {"type": "string"}},
    },
}


def default_files() -> Iterable[Tuple[str, str]]:
    """Return relative paths and contents for idempotent init writes."""
    yield "policy/routing_policy.md", ROUTING_POLICY_MD
    yield "policy/post_run_review.md", POST_RUN_REVIEW_MD
    yield "memory/README.md", MEMORY_README_MD
    yield "memory/schema.json", json.dumps(MEMORY_SCHEMA, indent=2, sort_keys=True) + "\n"


def init_workspace(root: Path) -> Tuple[int, int]:
    """Create local workspace directories and default files.

    Existing files are never overwritten. Returns ``(directories_seen, files_created)``.
    """
    directories_seen = 0
    for rel_path in DEFAULT_DIRECTORIES:
        (root / rel_path).mkdir(parents=True, exist_ok=True)
        directories_seen += 1

    files_created = 0
    for rel_path, contents in default_files():
        path = root / rel_path
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.exists():
            continue
        path.write_text(contents, encoding="utf-8")
        files_created += 1

    return directories_seen, files_created
