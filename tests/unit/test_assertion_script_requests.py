from __future__ import annotations

import argparse
import json
from unittest.mock import AsyncMock

import pytest

from openapi_to_mcp.adapters.testing import ConnectionSettings, ServerTestRequest
from scripts import assert_generated_server, assert_runtime_observability


@pytest.mark.asyncio
async def test_generated_server_passes_one_stdio_request(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    response = {"result": {"tools": []}}
    execute = AsyncMock(return_value=response)
    monkeypatch.setattr(assert_generated_server, "execute_mcp_server", execute)
    args = argparse.Namespace(
        transport="stdio",
        server_cmd="node build/index.js",
        env_source='{"TARGET_API_BASE_URL": "http://localhost:4010"}',
        endpoint_url=None,
    )
    params = {"tool_name": "lookup", "tool_arguments": {"id": 42}}

    result = await assert_generated_server._run_request(args, "call", 7, params)

    assert result == response
    execute.assert_awaited_once_with(
        ServerTestRequest(
            transport="stdio",
            method="call",
            params=params,
            req_id=7,
            connection=ConnectionSettings(
                server_cmd="node build/index.js",
                env={"TARGET_API_BASE_URL": "http://localhost:4010"},
            ),
        )
    )


@pytest.mark.asyncio
async def test_runtime_observability_passes_one_http_request(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    request_id = "request-123"
    execute = AsyncMock(
        return_value={
            "result": {
                "meta": {"requestId": request_id},
                "content": [
                    {
                        "type": "text",
                        "text": json.dumps({"request_id": request_id}),
                    }
                ],
            }
        }
    )
    monkeypatch.setattr(assert_runtime_observability, "execute_mcp_server", execute)
    args = argparse.Namespace(
        transport="streamable-http",
        server_cmd=None,
        env_source=None,
        endpoint_url="http://127.0.0.1:3000/mcp",
        tool_name="lookup",
        tool_arguments='{"id": 42}',
        expect_error=False,
    )

    await assert_runtime_observability._main(args)

    execute.assert_awaited_once_with(
        ServerTestRequest(
            transport="streamable-http",
            method="call",
            params={"tool_name": "lookup", "tool_arguments": {"id": 42}},
            req_id=1,
            connection=ConnectionSettings(endpoint_url="http://127.0.0.1:3000/mcp"),
        )
    )
