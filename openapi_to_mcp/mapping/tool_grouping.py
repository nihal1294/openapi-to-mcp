"""Optional grouped tool naming for model-oriented discoverability."""

from __future__ import annotations

import re
from typing import Any

from openapi_to_mcp.common.exceptions import GenerationError

TOOL_GROUPING_MODES = frozenset({"none", "tag-prefix"})


def apply_tool_grouping(
    mcp_tools: list[dict[str, Any]],
    tool_grouping: str,
) -> list[dict[str, Any]]:
    """Return mapped tools after applying an optional grouping strategy."""
    if tool_grouping == "none":
        return mcp_tools
    if tool_grouping != "tag-prefix":
        raise GenerationError(f"Unsupported tool grouping mode `{tool_grouping}`.")

    grouped_tools = [{**tool} for tool in mcp_tools]
    for tool in grouped_tools:
        _apply_tag_prefix(tool)
    _ensure_unique_names(grouped_tools)
    return grouped_tools


def _apply_tag_prefix(tool: dict[str, Any]) -> None:
    original_name = _original_name(tool)
    if _was_renamed(tool, original_name):
        return
    tag_prefix = _first_tag_prefix(tool)
    if tag_prefix is None:
        return
    tool["name"] = f"{tag_prefix}_{original_name}"


def _was_renamed(tool: dict[str, Any], original_name: str) -> bool:
    return _tool_name(tool) != original_name


def _first_tag_prefix(tool: dict[str, Any]) -> str | None:
    tags = tool.get("_original_tags")
    if not isinstance(tags, list):
        return None
    for tag in tags:
        if not isinstance(tag, str) or not tag.strip():
            continue
        normalized = _normalize_group_prefix(tag)
        if normalized:
            return normalized
    return None


def _normalize_group_prefix(value: str) -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9_]", "_", value.strip().lower())
    normalized = re.sub(r"_+", "_", cleaned).strip("_")
    if normalized and normalized[0].isdigit():
        return f"group_{normalized}"
    return normalized


def _ensure_unique_names(mcp_tools: list[dict[str, Any]]) -> None:
    seen: set[str] = set()
    for tool in mcp_tools:
        tool_name = _tool_name(tool)
        if tool_name in seen:
            raise GenerationError(
                f"Tool grouping produced duplicate tool name `{tool_name}`."
            )
        seen.add(tool_name)


def _tool_name(tool: dict[str, Any]) -> str:
    name = tool.get("name")
    if isinstance(name, str) and name:
        return name
    raise GenerationError(f"Mapped tool is missing a valid name: {tool!r}")


def _original_name(tool: dict[str, Any]) -> str:
    original_name = tool.get("_original_name")
    if isinstance(original_name, str) and original_name:
        return original_name
    return _tool_name(tool)
