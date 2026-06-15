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
            value = json.loads(block)
        except json.JSONDecodeError as exc:
            raise ValueError("invalid JSON in <{}> block: {}".format(tag, exc)) from exc
        if not isinstance(value, dict):
            raise ValueError("<{}> block must contain a JSON object".format(tag))
        parsed.append(value)
    return parsed
