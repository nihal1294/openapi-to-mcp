"""Prepare generated tool descriptions and check final names."""

from __future__ import annotations

import json
import re
from copy import deepcopy
from typing import Any

from openapi_to_mcp.common.exceptions import GenerationError

_RECOMMENDED_NAME = re.compile(r"[A-Za-z0-9_.-]{1,128}\Z", re.ASCII)


def apply_description_mode(
    tools: list[dict[str, Any]], mode: str
) -> list[dict[str, Any]]:
    """Return copies with the requested generated top-level descriptions."""
    if mode not in {"spec", "method"}:
        raise GenerationError(f"Unsupported tool description mode {json.dumps(mode)}.")
    result = deepcopy(tools)
    if mode == "method":
        for tool in result:
            tool["description"] = (
                f"Perform an HTTP {tool['_original_method'].upper()} request."
            )
    return result


def validate_tool_names(
    tools: list[dict[str, Any]], policy: str
) -> list[dict[str, str]]:
    """Return warnings for final names, or reject them when validation is enabled."""
    if policy not in {"preserve", "validate"}:
        raise GenerationError(f"Unsupported tool name policy {json.dumps(policy)}.")
    warnings = []
    for tool in tools:
        name = tool["name"]
        if _RECOMMENDED_NAME.fullmatch(name):
            continue
        operation = f"{tool['_original_method'].upper()} {tool['_original_path']}"
        message = (
            f"Tool name {json.dumps(name, ensure_ascii=True)} for operation "
            f"{json.dumps(operation, ensure_ascii=True)} is not recommended; "
            "use a policy rename with 1-128 ASCII letters, digits, underscores, periods, or hyphens."
        )
        if policy == "validate":
            raise GenerationError(message)
        warnings.append(
            {
                "code": "non_recommended_tool_name",
                "reason": "name_must_match_recommended_pattern",
                "name": name,
                "operation": operation,
                "message": message,
            }
        )
    return warnings
