"""Structured block parsing for agent output."""

from __future__ import annotations

import json
import re
from typing import Any, Dict, List


def extract_blocks(text: str, tag: str) -> List[str]:
    pattern = re.compile(
        r"<{tag}>\s*(.*?)\s*</{tag}>".format(tag=re.escape(tag)),
        re.IGNORECASE | re.DOTALL,
    )
    return [match.group(1).strip() for match in pattern.finditer(text)]


def parse_json_blocks(text: str, tag: str) -> List[Dict[str, Any]]:
    parsed: List[Dict[str, Any]] = []
    for block in extract_blocks(text, tag):
        try:
            value = json.loads(_strip_json_fence(block))
        except json.JSONDecodeError as exc:
            try:
                value = json.loads(_extract_json_object(block))
            except json.JSONDecodeError:
                raise ValueError("invalid JSON in <{}> block: {}".format(tag, exc)) from exc
        if not isinstance(value, dict):
            raise ValueError("<{}> block must contain a JSON object".format(tag))
        parsed.append(value)
    return parsed


def _strip_json_fence(block: str) -> str:
    stripped = block.strip()
    if not stripped.startswith("```"):
        return stripped
    lines = stripped.splitlines()
    if lines and lines[0].startswith("```"):
        lines = lines[1:]
    if lines and lines[-1].strip() == "```":
        lines = lines[:-1]
    return "\n".join(lines).strip()


def _extract_json_object(block: str) -> str:
    stripped = _strip_json_fence(block)
    start = stripped.find("{")
    end = stripped.rfind("}")
    if start == -1 or end == -1 or end < start:
        return stripped
    return stripped[start : end + 1]
