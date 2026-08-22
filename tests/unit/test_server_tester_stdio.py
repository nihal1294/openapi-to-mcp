from __future__ import annotations

from contextlib import asynccontextmanager
from typing import Self
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from mcp import MCPError
from mcp.types import CallToolResult, TextContent

from openapi_to_mcp.adapters.testing.server_tester import (
    ServerConnectionError,
    StdioTransport,
)
from openapi_to_mcp.adapters.testing.stdio_transport import perform_mcp_request


@asynccontextmanager
async def _fake_stdio_client(_params: object):
    yield MagicMock(), MagicMock()


class _FakeClientSession:
    def __init__(self, *_args: object) -> None:
        self.initialize = AsyncMock()

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(
        self,
        _exc_type: object,
        _exc: object,
        _tb: object,
    ) -> None:
        pass


@pytest.mark.asyncio
async def test_stdio_transport_returns_jsonrpc_error_for_protocol_tool_errors() -> None:
    transport = StdioTransport("node build/index.js")
    mcp_error = MCPError(-32602, "Input validation failed")

    with (
        patch(
            "openapi_to_mcp.adapters.testing.stdio_transport.stdio_client",
            _fake_stdio_client,
        ),
        patch(
            "openapi_to_mcp.adapters.testing.stdio_transport.ClientSession",
            _FakeClientSession,
        ),
        patch(
            "openapi_to_mcp.adapters.testing.stdio_transport.perform_mcp_request",
            side_effect=mcp_error,
        ),
    ):
        response = await transport.connect_and_execute(
            "call",
            {"tool_name": "testConversionTool", "tool_arguments": {"status": 123}},
            9,
        )

    assert response == {
        "jsonrpc": "2.0",
        "id": 9,
        "error": {
            "code": -32602,
            "message": "Input validation failed",
            "data": None,
        },
    }


@pytest.mark.asyncio
async def test_stdio_transport_preserves_initialization_protocol_errors() -> None:
    transport = StdioTransport("node build/index.js")
    session = _FakeClientSession()
    session.initialize.side_effect = MCPError(
        -32002,
        "Session initialization failed",
        {"phase": "initialize"},
    )

    with (
        patch(
            "openapi_to_mcp.adapters.testing.stdio_transport.stdio_client",
            _fake_stdio_client,
        ),
        patch(
            "openapi_to_mcp.adapters.testing.stdio_transport.ClientSession",
            return_value=session,
        ),
    ):
        response = await transport.connect_and_execute("list", None, 11)

    assert response == {
        "jsonrpc": "2.0",
        "id": 11,
        "error": {
            "code": -32002,
            "message": "Session initialization failed",
            "data": {"phase": "initialize"},
        },
    }


@pytest.mark.asyncio
async def test_stdio_transport_wraps_non_protocol_connection_errors() -> None:
    transport = StdioTransport("node build/index.js")

    with (
        patch(
            "openapi_to_mcp.adapters.testing.stdio_transport.stdio_client",
            side_effect=RuntimeError("broken pipe"),
        ),
        pytest.raises(ServerConnectionError, match="broken pipe") as captured,
    ):
        await transport.connect_and_execute("list", None, 12)

    assert isinstance(captured.value.__cause__, RuntimeError)


@pytest.mark.asyncio
async def test_stdio_transport_returns_in_band_tool_errors_unchanged() -> None:
    transport = StdioTransport("node build/index.js")
    tool_error_result = CallToolResult(
        content=[TextContent(type="text", text="Upstream request failed")],
        _meta={
            "error": {
                "code": "api_server_error",
                "source": "upstream",
                "retryable": True,
                "httpStatus": 503,
            }
        },
        isError=True,
    )

    with (
        patch(
            "openapi_to_mcp.adapters.testing.stdio_transport.stdio_client",
            _fake_stdio_client,
        ),
        patch(
            "openapi_to_mcp.adapters.testing.stdio_transport.ClientSession",
            _FakeClientSession,
        ),
        patch(
            "openapi_to_mcp.adapters.testing.stdio_transport.perform_mcp_request",
            return_value=tool_error_result,
        ),
    ):
        response = await transport.connect_and_execute(
            "call",
            {"tool_name": "testConversionTool", "tool_arguments": {"status": "x"}},
            10,
        )

    assert response["jsonrpc"] == "2.0"
    assert response["id"] == 10
    assert response["content"][0]["text"] == "Upstream request failed"
    assert response["isError"] is True
    assert response["meta"] == {
        "error": {
            "code": "api_server_error",
            "source": "upstream",
            "retryable": True,
            "httpStatus": 503,
        }
    }


@pytest.mark.asyncio
async def test_perform_mcp_request_list_and_call() -> None:
    session = AsyncMock()
    session.list_tools.return_value = list_result = MagicMock()
    session.call_tool.return_value = call_result = MagicMock()

    assert await perform_mcp_request(session, "list", None) is list_result
    params = {"tool_name": "echo", "tool_arguments": {"x": 1}}
    assert await perform_mcp_request(session, "call", params) is call_result
    session.call_tool.assert_called_once_with(name="echo", arguments={"x": 1})


@pytest.mark.asyncio
async def test_perform_mcp_request_rejects_missing_tool_name() -> None:
    session = AsyncMock()

    with pytest.raises(ValueError, match="Missing 'tool_name'"):
        await perform_mcp_request(session, "call", None)
