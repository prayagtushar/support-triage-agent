"""Pulling a JSON object out of whatever a model actually returned."""

from __future__ import annotations

import re

_THINK_BLOCK = re.compile(r"^\s*<think>.*?</think>", re.DOTALL | re.IGNORECASE)
_FENCE = re.compile(r"```(?:json)?\s*(.*?)\s*```", re.DOTALL | re.IGNORECASE)


def extract_json_object(content: str) -> str:
    """Best-effort recovery of a single JSON object from model output.

    Handles reasoning preambles, fenced code blocks, and prose either side of
    the object. Returns the input unchanged when nothing better is found, so
    the caller's schema validation produces the error message.
    """
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
