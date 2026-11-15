"""Helpers for building comparable MCP tool surfaces."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from openapi_to_mcp.commands.generation_models import GenerationBehavior
from openapi_to_mcp.common import MappingError
from openapi_to_mcp.mapping.preparation import prepare_tools

if TYPE_CHECKING:
    from openapi_to_mcp.policy.models import PolicyConfig

_SKIPPED_OPERATION_PREVIEW_LIMIT = 3


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
    metadata: dict[str, Any] | None = None
    execution: dict[str, Any] | None = None

    @property
    def operation_key(self) -> tuple[str, str]:
        """Return a stable operation identity."""
        return (self.method.upper(), self.path)


def build_tool_surfaces(
    spec: dict[str, Any],
    *,
    policy: PolicyConfig | None = None,
    tool_grouping: str | None = None,
    tool_descriptions: str | None = None,
    tool_name_policy: str | None = None,
) -> dict[str, ToolSurface]:
    """Return comparable tool surfaces keyed by tool name."""
    defaults = policy.generation if policy else None
    behavior = GenerationBehavior(
        tool_grouping=tool_grouping
        or (defaults.tool_grouping if defaults else None)
        or "none",
        tool_descriptions=tool_descriptions
        or (defaults.tool_descriptions if defaults else None)
        or "spec",
        tool_name_policy=tool_name_policy
        or (defaults.tool_name_policy if defaults else None)
        or "preserve",
        telemetry="off",
        strict=False,
        runtime_validation="input",
        on_mapping_error="fail",
        on_schema_error="skip",
    )
    prepared = prepare_tools(spec, behavior=behavior, policy=policy)
    _raise_if_mapper_skipped_operations(prepared.report)
    runtime_tools = prepared.runtime_registry
    return {
        tool["name"]: ToolSurface(
            name=tool["name"],
            method=_require_string(runtime_tools, tool["name"], "method"),
            path=_require_string(runtime_tools, tool["name"], "path"),
            input_schema=tool["inputSchema"],
            output_schema=tool.get("outputSchema"),
            security=_require_security(runtime_tools, tool["name"]),
            security_schemes=_require_security_schemes(runtime_tools, tool["name"]),
            metadata={
                key: tool[key]
                for key in ("description", "title", "annotations")
                if key in tool
            },
            execution={"execution": runtime_tools[tool["name"]]["execution"]}
            if "execution" in runtime_tools[tool["name"]]
            else {},
        )
        for tool in prepared.public_tools
    }


def canonicalize(value: object) -> str:
    """Return a stable string representation for diff comparisons."""
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def _raise_if_mapper_skipped_operations(report: dict[str, Any]) -> None:
    skipped = report.get("skipped_operations")
    if not isinstance(skipped, list) or not skipped:
        return
    summary = ", ".join(
        f"{item['method']} {item['path']}"
        for item in skipped[:_SKIPPED_OPERATION_PREVIEW_LIMIT]
        if isinstance(item, dict)
        and isinstance(item.get("method"), str)
        and isinstance(item.get("path"), str)
    )
    suffix = "..." if len(skipped) > _SKIPPED_OPERATION_PREVIEW_LIMIT else ""
    raise MappingError(
        "Spec mapping skipped operation schema(s) during diff: "
        f"{summary}{suffix}. Run `openapi-to-mcp doctor` first."
    )


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
