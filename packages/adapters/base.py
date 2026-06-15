"""Common adapter types and subprocess helpers."""

from __future__ import annotations

import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Sequence


@dataclass
class AgentResult:
    stdout: str
    stderr: str
    final_message: str
    events_path: Optional[str]
    exit_code: int
    session_id: Optional[str]
    raw_artifacts: Dict[str, object] = field(default_factory=dict)


class AgentAdapter:
    name = "base"

    def run(
        self,
        prompt: str,
        *,
        cwd: str,
        session_id: Optional[str] = None,
        output_schema: Optional[str] = None,
        timeout_seconds: Optional[int] = None,
    ) -> AgentResult:
        raise NotImplementedError

    @classmethod
    def version(cls) -> str:
        return "unknown"


def resolve_executable(command: str) -> str:
    exe = shutil.which(command)
    if not exe:
        raise FileNotFoundError("executable not found: {}".format(command))
    return exe


def command_version(command: str) -> str:
    exe = shutil.which(command)
    if not exe:
        return "not found"
    try:
        result = subprocess.run(
            [exe, "--version"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=False,
            timeout=15,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return "found, version check failed: {}".format(exc)
    return (result.stdout or result.stderr).strip() or "found"


def run_command(
    command: Sequence[str],
    *,
    cwd: str,
    timeout_seconds: Optional[int],
) -> AgentResult:
    try:
        result = subprocess.run(
            list(command),
            cwd=str(Path(cwd)),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=False,
            timeout=timeout_seconds,
        )
    except subprocess.TimeoutExpired as exc:
        stdout = exc.stdout if isinstance(exc.stdout, str) else ""
        stderr = exc.stderr if isinstance(exc.stderr, str) else ""
        stderr = (stderr + "\n" if stderr else "") + "command timed out after {} seconds".format(
            timeout_seconds
        )
        return AgentResult(
            stdout=stdout,
            stderr=stderr,
            final_message=stdout.strip(),
            events_path=None,
            exit_code=124,
            session_id=None,
            raw_artifacts={"command": safe_command(command), "timed_out": True},
        )
    except OSError as exc:
        return AgentResult(
            stdout="",
            stderr=str(exc),
            final_message="",
            events_path=None,
            exit_code=127,
            session_id=None,
            raw_artifacts={"command": safe_command(command), "os_error": True},
        )

    return AgentResult(
        stdout=result.stdout,
        stderr=result.stderr,
        final_message=result.stdout.strip(),
        events_path=None,
        exit_code=result.returncode,
        session_id=None,
        raw_artifacts={"command": safe_command(command), "timed_out": False},
    )


def safe_command(command: Sequence[str]) -> List[str]:
    """Return command argv without shell interpolation or secret expansion."""
    return [str(part) for part in command]
