"""Pulling a JSON object out of whatever a model actually returned."""

from __future__ import annotations

import re

_THINK_BLOCK = re.compile(r"^\s*<think>.*?</think>", re.DOTALL | re.IGNORECASE)
_FENCE = re.compile(r"```(?:json)?\s*(.*?)\s*```", re.DOTALL | re.IGNORECASE)


def extract_json_object(content: str) -> str:
    """Dig one JSON object out of model output. Returns the input unchanged when it cannot."""
    text = _THINK_BLOCK.sub("", content).strip()

    fenced = _FENCE.search(text)
    if fenced:
        text = fenced.group(1).strip()

    start = text.find("{")
    if start == -1:
        return text

    depth = 0
    in_string = False
    escaped = False
    for i in range(start, len(text)):
        char = text[i]
        if escaped:
            escaped = False
            continue
        if char == "\\":
            escaped = True
        elif char == '"':
            in_string = not in_string
        elif not in_string:
            if char == "{":
                depth += 1
            elif char == "}":
                depth -= 1
                if depth == 0:
                    return text[start : i + 1]
    return text[start:]
