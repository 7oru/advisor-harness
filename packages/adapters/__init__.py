"""Agent backend adapters."""

from __future__ import annotations

from packages.adapters.base import AgentAdapter, AgentResult
from packages.adapters.codex_cli import CodexCliAdapter
from packages.adapters.fake import FakeAdapter
from packages.adapters.kimi_cli import KimiCliAdapter


def create_adapter(name: str) -> AgentAdapter:
    normalized = name.strip().lower()
    if normalized == "kimi":
        return KimiCliAdapter()
    if normalized == "codex":
        return CodexCliAdapter()
    if normalized == "fake":
        return FakeAdapter()
    raise ValueError("unknown adapter backend: {}".format(name))


__all__ = [
    "AgentAdapter",
    "AgentResult",
    "CodexCliAdapter",
    "FakeAdapter",
    "KimiCliAdapter",
    "create_adapter",
]
