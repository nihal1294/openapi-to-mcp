"""Helpers for separating public MCP tools from runtime-only metadata."""

from __future__ import annotations

from typing import Any

from openapi_to_mcp.common.exceptions import GenerationError

# Keep this in sync with Mapper._map_operation_to_tool runtime-only fields.
_RUNTIME_FIELD_MAP = {
    "_original_method": "method",
    "_original_path": "path",
    "_original_parameters": "parameters",
    "_original_request_body": "requestBody",
    "_original_security": "security",
    "_original_security_schemes": "securitySchemes",
    "_policy_execution": "execution",
}


def build_public_tools(mcp_tools: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Return only public MCP tool fields.

    Any underscore-prefixed keys are treated as internal implementation detail.
    """
    return [
        {key: value for key, value in tool.items() if not key.startswith("_")}
        for tool in mcp_tools
    ]


def _require_tool_name(tool: dict[str, Any]) -> str:
    """Return the tool name or raise a generation error."""
    tool_name = tool.get("name")
    if isinstance(tool_name, str) and tool_name:
        return tool_name
    raise GenerationError(f"Mapped tool is missing a valid 'name': {tool!r}")


def build_runtime_tool_registry(
    mcp_tools: list[dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    """Return runtime execution metadata keyed by tool name."""
    return {
        _require_tool_name(tool): {
            target_key: tool[source_key]
            for source_key, target_key in _RUNTIME_FIELD_MAP.items()
            if source_key in tool
        }
        for tool in mcp_tools
    }


def derive_auth_env_vars(
    runtime_tools: dict[str, dict[str, Any]],
) -> list[str]:
    """Collect auth-related env variable names required by runtime metadata."""
    env_vars: set[str] = set()
    for metadata in runtime_tools.values():
        security_schemes = metadata.get("securitySchemes", {})
        if not isinstance(security_schemes, dict):
            continue
        for scheme_name, scheme_def in security_schemes.items():
            if not isinstance(scheme_name, str) or not isinstance(scheme_def, dict):
                continue
            normalized = "".join(
                c if c.isalnum() else "_" for c in scheme_name.upper()
            ).strip("_")
            normalized = "_".join(part for part in normalized.split("_") if part)
            if not normalized:
                continue
            scheme_type = str(scheme_def.get("type", "")).lower()
            http_scheme = str(scheme_def.get("scheme", "")).lower()
            if scheme_type == "apikey":
                env_vars.add(f"AUTH_{normalized}_API_KEY")
            elif (scheme_type == "http" and http_scheme == "bearer") or scheme_type in {
                "oauth2",
                "openidconnect",
            }:
                env_vars.add(f"AUTH_{normalized}_TOKEN")
    return sorted(env_vars)
