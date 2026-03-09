"""Helpers for building comparable MCP tool surfaces."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from openapi_to_mcp.common import MappingError
from openapi_to_mcp.common.tool_runtime import (
    build_public_tools,
    build_runtime_tool_registry,
)
from openapi_to_mcp.mapping.mapper import Mapper


@dataclass(frozen=True)
class ToolSurface:
    """Comparable MCP-facing and runtime-facing tool data."""

    name: str
    method: str
    path: str
    input_schema: dict[str, Any]
    output_schema: dict[str, Any] | None
    security: list[dict[str, Any]] | None
    security_schemes: dict[str, dict[str, Any]]

    @property
    def operation_key(self) -> tuple[str, str]:
        """Return a stable operation identity."""
        return (self.method.upper(), self.path)


def build_tool_surfaces(spec: dict[str, Any]) -> dict[str, ToolSurface]:
    """Return comparable tool surfaces keyed by tool name."""
    mapper = Mapper(
        spec,
        strict=False,
        on_mapping_error="fail",
        on_schema_error="skip",
    )
    mapped_tools = mapper.map_tools()
    public_tools = build_public_tools(mapped_tools)
    runtime_tools = build_runtime_tool_registry(mapped_tools)
    return {
        tool["name"]: ToolSurface(
            name=tool["name"],
            method=_require_string(runtime_tools, tool["name"], "method"),
            path=_require_string(runtime_tools, tool["name"], "path"),
            input_schema=tool["inputSchema"],
            output_schema=tool.get("outputSchema"),
            security=_require_security(runtime_tools, tool["name"]),
            security_schemes=_require_security_schemes(runtime_tools, tool["name"]),
        )
        for tool in public_tools
    }


def canonicalize(value: object) -> str:
    """Return a stable string representation for diff comparisons."""
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def _require_string(
    runtime_tools: dict[str, dict[str, Any]], tool_name: str, field_name: str
) -> str:
    value = runtime_tools.get(tool_name, {}).get(field_name)
    if isinstance(value, str) and value:
        return value
    raise MappingError(
        f"Mapped tool `{tool_name}` is missing runtime field `{field_name}`."
    )


def _require_security(
    runtime_tools: dict[str, dict[str, Any]], tool_name: str
) -> list[dict[str, Any]] | None:
    value = runtime_tools.get(tool_name, {}).get("security")
    return value if isinstance(value, list) else None


def _require_security_schemes(
    runtime_tools: dict[str, dict[str, Any]], tool_name: str
) -> dict[str, dict[str, Any]]:
    value = runtime_tools.get(tool_name, {}).get("securitySchemes")
    if isinstance(value, dict):
        return value
    return {}
