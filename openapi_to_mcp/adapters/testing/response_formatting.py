"""JSON-RPC response formatting for MCP server tests."""

from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, Protocol, TypeGuard, cast

from mcp.types import CallToolResult, ListToolsResult

if TYPE_CHECKING:
    from mcp import MCPError

McpResult = ListToolsResult | CallToolResult | Mapping[str, Any]


class _ModelLike(Protocol):
    def model_dump(self, *, mode: str, by_alias: bool) -> dict[str, Any]:
        """Serialize model fields with their declared aliases."""
        ...


def _is_model_like(value: object) -> TypeGuard[_ModelLike]:
    fields = getattr(type(value), "model_fields", None)
    return callable(getattr(value, "model_dump", None)) and isinstance(fields, Mapping)


def _model_fields(value: _ModelLike) -> Mapping[str, object]:
    return cast(
        "Mapping[str, object]",
        type(value).model_fields,
    )


def _field_alias(field_name: str, field: object) -> str:
    serialization_alias = getattr(field, "serialization_alias", None)
    if isinstance(serialization_alias, str):
        return serialization_alias
    alias = getattr(field, "alias", None)
    return alias if isinstance(alias, str) else field_name


def _serialize_model_member(value: object, dumped: object) -> object:
    if _is_model_like(value):
        return _serialize_model(value)
    if isinstance(value, list) and isinstance(dumped, list):
        return [
            _serialize_model_member(item, serialized)
            for item, serialized in zip(value, dumped, strict=True)
        ]
    return dumped


def _serialize_model(value: _ModelLike) -> dict[str, Any]:
    payload = cast(
        "dict[str, Any]",
        value.model_dump(mode="json", by_alias=True),
    )
    for field_name, field in _model_fields(value).items():
        alias = _field_alias(field_name, field)
        if alias not in payload:
            continue
        output_key = "meta" if alias == "_meta" else alias
        serialized = _serialize_model_member(
            getattr(value, field_name),
            payload[alias],
        )
        if output_key != alias:
            del payload[alias]
        payload[output_key] = serialized
    return payload


def format_mcp_response(value: McpResult | None, req_id: int) -> dict[str, Any]:
    """Serialize an MCP result into a JSON-RPC response dictionary."""
    if value is None:
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "error": {
                "code": -32603,
                "message": "Internal error: No response data received from server.",
            },
        }
    response = dict(value) if isinstance(value, Mapping) else _serialize_model(value)
    response.setdefault("jsonrpc", "2.0")
    response.setdefault("id", req_id)
    return response


def format_mcp_error(error: MCPError, req_id: int) -> dict[str, Any]:
    """Serialize an MCP protocol error into a JSON-RPC error response."""
    payload: dict[str, Any] = {"code": error.code, "message": error.message}
    payload["data"] = error.data
    return {"jsonrpc": "2.0", "id": req_id, "error": payload}
