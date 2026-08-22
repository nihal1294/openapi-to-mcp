from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import requests

from openapi_to_mcp.adapters.testing.server_tester import (
    DEFAULT_PROTOCOL_VERSION,
    ServerConnectionError,
    StreamableHttpTransport,
    UnsupportedMethodError,
    _perform_mcp_request,
)


def _json_response(payload: object, headers: dict[str, str] | None = None) -> MagicMock:
    response = MagicMock()
    response.raise_for_status.return_value = None
    response.json.return_value = payload
    response.headers = headers or {}
    return response


def test_streamable_payload_builder_uses_tools_wire_methods() -> None:
    transport = StreamableHttpTransport("http://localhost:8080/mcp")

    assert transport._build_jsonrpc_payload("list", None, 1) == {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/list",
        "params": {},
    }
    assert transport._build_jsonrpc_payload(
        "call",
        {"tool_name": "echo", "tool_arguments": {"value": 1}},
        2,
    ) == {
        "jsonrpc": "2.0",
        "id": 2,
        "method": "tools/call",
        "params": {"name": "echo", "arguments": {"value": 1}},
    }


def test_streamable_payload_builder_requires_tool_name() -> None:
    transport = StreamableHttpTransport("http://localhost:8080/mcp")

    with pytest.raises(ValueError, match="Missing 'tool_name'"):
        transport._build_jsonrpc_payload("call", {}, 3)


def test_streamable_post_jsonrpc_initializes_session() -> None:
    transport = StreamableHttpTransport("http://localhost:8080/mcp")
    init_response = _json_response(
        {"jsonrpc": "2.0", "id": 1001, "result": {"serverInfo": {}}},
        headers={"Mcp-Session-Id": "session-123"},
    )
    notification_response = _json_response({})
    list_response = _json_response(
        {
            "jsonrpc": "2.0",
            "id": 1,
            "result": {"tools": [{"name": "echo", "inputSchema": {"type": "object"}}]},
        }
    )

    with patch(
        "openapi_to_mcp.adapters.testing.streamable_http_transport.requests.post",
        side_effect=[init_response, notification_response, list_response],
    ) as mock_post:
        response = transport._post_jsonrpc("list", None, 1)

    assert response["result"]["tools"][0]["name"] == "echo"
    assert mock_post.call_count == 3
    init_call, notification_call, list_call = mock_post.call_args_list
    assert init_call.kwargs["json"]["params"]["protocolVersion"] == (
        DEFAULT_PROTOCOL_VERSION
    )
    assert notification_call.kwargs["headers"]["Mcp-Session-Id"] == "session-123"
    assert list_call.kwargs["json"]["method"] == "tools/list"
    assert list_call.kwargs["headers"]["MCP-Protocol-Version"] == "2025-11-25"


def test_streamable_initialize_error_raises() -> None:
    transport = StreamableHttpTransport("http://localhost:8080/mcp")
    init_error = _json_response(
        {
            "jsonrpc": "2.0",
            "id": 1001,
            "error": {"code": -32600, "message": "init failed"},
        }
    )

    with (
        patch(
            "openapi_to_mcp.adapters.testing.streamable_http_transport.requests.post",
            return_value=init_error,
        ),
        pytest.raises(ServerConnectionError, match="Initialize request failed"),
    ):
        transport._post_jsonrpc("list", None, 1)


def test_streamable_parse_json_response_rejects_non_object() -> None:
    transport = StreamableHttpTransport("http://localhost:8080/mcp")

    with pytest.raises(ServerConnectionError, match="Unexpected non-object JSON"):
        transport._parse_json_response(_json_response([{"jsonrpc": "2.0"}]))


def test_streamable_parse_json_response_invalid_json_raises() -> None:
    transport = StreamableHttpTransport("http://localhost:8080/mcp")
    response = MagicMock()
    response.json.side_effect = json.JSONDecodeError("bad", "", 0)

    with pytest.raises(ServerConnectionError, match="Invalid JSON response"):
        transport._parse_json_response(response)


@pytest.mark.asyncio
async def test_streamable_connect_wraps_request_failures() -> None:
    transport = StreamableHttpTransport("http://localhost:8080/mcp")

    with (
        patch.object(
            transport,
            "_post_jsonrpc",
            side_effect=requests.RequestException("boom"),
        ),
        pytest.raises(
            ServerConnectionError, match="Failed to connect via streamable-http"
        ),
    ):
        await transport.connect_and_execute("list", None, 1)


def test_streamable_payload_builder_rejects_unsupported_method() -> None:
    transport = StreamableHttpTransport("http://localhost:8080/mcp")

    with pytest.raises(UnsupportedMethodError, match="Unsupported method"):
        transport._build_jsonrpc_payload("ping", None, 1)


@pytest.mark.asyncio
async def test_perform_mcp_request_rejects_unsupported_method() -> None:
    session = AsyncMock()

    with pytest.raises(UnsupportedMethodError, match="Unsupported method"):
        await _perform_mcp_request(session, "ping", None)
