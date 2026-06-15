"""Codex CLI adapter."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path
from typing import Optional

from packages.adapters.base import AgentAdapter, AgentResult, command_version, resolve_executable, run_command


class CodexCliAdapter(AgentAdapter):
    name = "codex"

    def __init__(self, executable: str = "codex") -> None:
        self.executable = executable

    @classmethod
    def version(cls) -> str:
        return command_version("codex")

    def run(
        self,
        prompt: str,
        *,
        cwd: str,
        session_id: Optional[str] = None,
        output_schema: Optional[str] = None,
        timeout_seconds: Optional[int] = None,
    ) -> AgentResult:
        exe = resolve_executable(self.executable)
        fd, last_message_path = tempfile.mkstemp(prefix="maa-codex-last-", suffix=".txt")
        os.close(fd)
        command = [
            exe,
            "exec",
            "--cd",
            cwd,
            "--json",
            "--output-last-message",
            last_message_path,
        ]
        if output_schema:
            command.extend(["--output-schema", output_schema])
        command.append(prompt)

        result = run_command(command, cwd=cwd, timeout_seconds=timeout_seconds)
        final_message = ""
        try:
            final_message = Path(last_message_path).read_text(encoding="utf-8").strip()
        except OSError:
            final_message = ""
        try:
            os.unlink(last_message_path)
        except OSError:
            pass

        if final_message:
            result.final_message = final_message
        result.session_id = session_id
        result.raw_artifacts["backend"] = self.name
        result.raw_artifacts["codex_json_stdout"] = True
        return result
