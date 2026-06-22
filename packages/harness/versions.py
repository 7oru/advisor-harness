"""Version metadata for run prompts, schemas, and policies."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any, Dict, Optional

from packages.harness.artifacts import utc_now
from packages.harness.defaults import MEMORY_SCHEMA_VERSION
from packages.roles.advisor import ADVISOR_PROMPT_VERSION
from packages.roles.executor import EXECUTOR_PROMPT_VERSION


RUN_VERSION_MANIFEST_VERSION = "run-version-manifest.v1"
EXECUTOR_RESUME_PROMPT_VERSION = "executor-resume.v1"


def build_run_version_manifest(root: Path) -> Dict[str, Any]:
    """Return auditable version metadata captured at run start."""
    return {
        "schema_version": RUN_VERSION_MANIFEST_VERSION,
        "created_at": utc_now(),
        "prompt_versions": {
            "executor_start": EXECUTOR_PROMPT_VERSION,
            "advisor_guidance": ADVISOR_PROMPT_VERSION,
            "executor_resume": EXECUTOR_RESUME_PROMPT_VERSION,
        },
        "memory_schema": {
            "version": MEMORY_SCHEMA_VERSION,
            "path": "memory/schema.json",
            "sha256": _file_sha256(root / "memory" / "schema.json"),
        },
        "policy_files": {
            "routing_policy": _file_manifest(root / "policy" / "routing_policy.md"),
            "post_run_review": _file_manifest(root / "policy" / "post_run_review.md"),
        },
    }


def _file_manifest(path: Path) -> Dict[str, Optional[str]]:
    return {
        "path": _display_path(path),
        "sha256": _file_sha256(path),
    }


def _file_sha256(path: Path) -> Optional[str]:
    if not path.exists() or not path.is_file():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _display_path(path: Path) -> str:
    parts = path.parts
    if "policy" in parts:
        index = parts.index("policy")
        return str(Path(*parts[index:]))
    if "memory" in parts:
        index = parts.index("memory")
        return str(Path(*parts[index:]))
    return str(path)

