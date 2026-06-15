"""Run artifact helpers."""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

from packages.adapters import AgentResult


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def new_id(prefix: str) -> str:
    return "{}_{}".format(prefix, uuid.uuid4().hex[:12])


def new_run_id() -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return "run_{}_{}".format(stamp, uuid.uuid4().hex[:8])


def ensure_run_dir(root: Path, run_id: Optional[str] = None) -> Path:
    run = run_id or new_run_id()
    run_dir = root / "runs" / run
    run_dir.mkdir(parents=True, exist_ok=False)
    return run_dir


def write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def write_json(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_agent_result(run_dir: Path, prefix: str, result: AgentResult) -> None:
    write_text(run_dir / "{}.stdout.txt".format(prefix), result.stdout)
    write_text(run_dir / "{}.stderr.txt".format(prefix), result.stderr)
    write_json(
        run_dir / "{}.raw.json".format(prefix),
        {
            "exit_code": result.exit_code,
            "events_path": result.events_path,
            "session_id": result.session_id,
            "raw_artifacts": result.raw_artifacts,
        },
    )


def write_outcome(run_dir: Path, payload: Dict[str, Any]) -> None:
    payload = dict(payload)
    payload.setdefault("completed_at", utc_now())
    write_json(run_dir / "outcome.json", payload)
