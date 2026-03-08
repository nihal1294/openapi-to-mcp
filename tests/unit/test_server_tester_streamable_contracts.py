from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import requests

from openapi_to_mcp.adapters.testing.server_tester import (
    ServerConnectionError,
    StreamableHttpTransport,
    UnsupportedMethodError,
    _perform_mcp_request,
)


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
