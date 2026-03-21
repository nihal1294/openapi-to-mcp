"""Helpers for shaping MCP tool descriptions from OpenAPI operations."""

from __future__ import annotations

import re
from typing import Any

_IDENTIFIER_PARTS = re.compile(r"[A-Z]+(?=[A-Z][a-z]|\d|$)|[A-Z]?[a-z]+|\d+")
_SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+|\n+")
_VERSION_SEGMENT = re.compile(r"^v\d+$", re.IGNORECASE)


def build_tool_description(method: str, path: str, operation: dict[str, Any]) -> str:
    """Build a concise MCP tool description from OpenAPI operation metadata."""
    summary = _clean_text(operation.get("summary"))
    if _is_useful_text(summary):
        return _ensure_sentence(summary)

    description = _first_sentence(_clean_text(operation.get("description")))
    if _is_useful_text(description):
        return _ensure_sentence(description)

    operation_id = operation.get("operationId")
    if isinstance(operation_id, str):
        humanized = _humanize_identifier(operation_id)
        if _is_useful_text(humanized):
            return _ensure_sentence(humanized.capitalize())

    return _synthesize_from_path(method, path)


def _clean_text(value: object) -> str:
    if not isinstance(value, str):
        return ""
    return " ".join(value.split()).strip()


def _first_sentence(text: str) -> str:
    if not text:
        return ""
    parts = [part.strip() for part in _SENTENCE_SPLIT.split(text) if part.strip()]
    return parts[0] if parts else text


def _is_useful_text(text: str) -> bool:
    return bool(text)


def _humanize_identifier(identifier: str) -> str:
    normalized = identifier.replace("-", " ").replace("_", " ")
    spaced_words: list[str] = []
    for chunk in normalized.split():
        parts = _IDENTIFIER_PARTS.findall(chunk)
        spaced_words.extend(parts or [chunk])
    return " ".join(word.lower() for word in spaced_words if word)


def _synthesize_from_path(method: str, path: str) -> str:
    verb = _verb_for_method(method, path)
    resource = _resource_for_path(path)
    qualifier = _qualifier_for_path(path)
    sentence = f"{verb} {resource}"
    if qualifier:
        sentence = f"{sentence} {qualifier}"
    return _ensure_sentence(sentence)


def _verb_for_method(method: str, path: str) -> str:
    lowered = method.lower()
    has_path_params = "{" in path and "}" in path
    if lowered == "get":
        return "Retrieve" if has_path_params else "List"
    return {
        "post": "Create",
        "put": "Update",
        "patch": "Update",
        "delete": "Delete",
        "head": "Inspect",
        "options": "Inspect options for",
        "trace": "Trace",
    }.get(lowered, lowered.upper())


def _resource_for_path(path: str) -> str:
    segments = [segment for segment in path.strip("/").split("/") if segment]
    resource_words = [
        segment.replace("-", " ").replace("_", " ")
        for segment in segments
        if not segment.startswith("{") and not _VERSION_SEGMENT.match(segment)
    ]
    if not resource_words:
        if any(segment.startswith("{") for segment in segments):
            return "resource"
        return "the API root"
    return resource_words[-1]


def _qualifier_for_path(path: str) -> str:
    params = [
        segment.strip("{}") for segment in path.split("/") if segment.startswith("{")
    ]
    if not params:
        return ""
    return "by " + ", ".join(params)


def _ensure_sentence(text: str) -> str:
    stripped = text.strip()
    if not stripped:
        return stripped
    if stripped[-1] in ".!?":
        return stripped
    return f"{stripped}."
