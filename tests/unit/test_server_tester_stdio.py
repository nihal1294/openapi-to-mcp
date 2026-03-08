from __future__ import annotations

from contextlib import asynccontextmanager
from typing import Self
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from mcp import McpError
from mcp.types import ErrorData

from openapi_to_mcp.adapters.testing.server_tester import StdioTransport


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
    mcp_error = McpError(
        ErrorData(code=-32602, message="Input validation failed", data=None)
    )

    with (
        patch(
            "openapi_to_mcp.adapters.testing.server_tester.stdio_client",
            _fake_stdio_client,
        ),
        patch(
            "openapi_to_mcp.adapters.testing.server_tester.ClientSession",
            _FakeClientSession,
        ),
        patch(
            "openapi_to_mcp.adapters.testing.server_tester._perform_mcp_request",
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
async def test_stdio_transport_returns_in_band_tool_errors_unchanged() -> None:
    transport = StdioTransport("node build/index.js")
    tool_error_result = MagicMock()
    tool_error_result.model_dump.return_value = {
        "content": [{"type": "text", "text": "Upstream request failed"}],
        "meta": {
            "error": {
                "code": "api_server_error",
                "source": "upstream",
                "retryable": True,
                "httpStatus": 503,
            }
        },
        "isError": True,
    }

    with (
        patch(
            "openapi_to_mcp.adapters.testing.server_tester.stdio_client",
            _fake_stdio_client,
        ),
        patch(
            "openapi_to_mcp.adapters.testing.server_tester.ClientSession",
            _FakeClientSession,
        ),
        patch(
            "openapi_to_mcp.adapters.testing.server_tester._perform_mcp_request",
            return_value=tool_error_result,
        ),
    ):
        response = await transport.connect_and_execute(
            "call",
            {"tool_name": "testConversionTool", "tool_arguments": {"status": "x"}},
            10,
        )

    assert response == {
        "jsonrpc": "2.0",
        "id": 10,
        "content": [{"type": "text", "text": "Upstream request failed"}],
        "meta": {
            "error": {
                "code": "api_server_error",
                "source": "upstream",
                "retryable": True,
                "httpStatus": 503,
            }
        },
        "isError": True,
    }
