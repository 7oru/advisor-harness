"""Kimi CLI adapter."""

from __future__ import annotations

from typing import Optional

from packages.adapters.base import AgentAdapter, AgentResult, command_version, resolve_executable, run_command


class KimiCliAdapter(AgentAdapter):
    name = "kimi"

    def __init__(self, executable: str = "kimi") -> None:
        self.executable = executable

    @classmethod
    def version(cls) -> str:
        return command_version("kimi")

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
        command = [
            exe,
            "--work-dir",
            cwd,
        ]
        if session_id:
            command.extend(["--session", session_id])
        command.extend(["--print", "--final-message-only", "--prompt", prompt])

        result = run_command(command, cwd=cwd, timeout_seconds=timeout_seconds)
        result.session_id = session_id
        result.raw_artifacts["backend"] = self.name
        if output_schema:
            result.raw_artifacts["output_schema_ignored"] = output_schema
        return result
