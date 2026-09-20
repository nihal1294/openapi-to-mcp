"""Verify a generated container server through real MCP list and call requests."""

from __future__ import annotations

import asyncio
import json
import sys

from openapi_to_mcp.adapters.testing import ConnectionSettings, ServerTestRequest
from openapi_to_mcp.adapters.testing.server_tester import execute_mcp_server


async def verify(endpoint: str) -> None:
    """Check tool discovery and authenticated execution against the Compose API."""
    connection = ConnectionSettings(endpoint_url=endpoint)
    listed = await execute_mcp_server(
        ServerTestRequest(
            transport="streamable-http", method="list", connection=connection
        )
    )
    payload = listed.get("result", listed)
    names = {tool["name"] for tool in payload.get("tools", [])}
    if "getWidget" not in names:
        raise AssertionError(f"Expected getWidget, received {listed}")
    called = await execute_mcp_server(
        ServerTestRequest(
            transport="streamable-http",
            method="call",
            params={"tool_name": "getWidget", "tool_arguments": {"widgetId": "42"}},
            connection=connection,
        )
    )
    result = called.get("result", called)
    if "error" in called or result.get("isError"):
        raise AssertionError(f"Tool execution failed: {called}")
    content = json.loads(result["content"][0]["text"])
    if content != {"id": "42", "source": "compose-mock"}:
        raise AssertionError(f"Unexpected upstream result: {content}")
    sys.stdout.write("Container MCP discovery and authenticated tool call passed.\n")


if __name__ == "__main__":
    asyncio.run(verify(sys.argv[1]))
