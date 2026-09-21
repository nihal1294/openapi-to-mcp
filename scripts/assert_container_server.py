"""Verify a generated container server through real MCP list and call requests."""

from __future__ import annotations

import asyncio
import json
import sys
from urllib.parse import urlsplit, urlunsplit

import requests

from openapi_to_mcp.adapters.testing import ConnectionSettings, ServerTestRequest
from openapi_to_mcp.adapters.testing.server_tester import execute_mcp_server


def _listener_base_url(endpoint: str) -> str:
    """Return the listener origin for an MCP endpoint URL."""
    parsed = urlsplit(endpoint)
    if not parsed.scheme or not parsed.netloc:
        raise ValueError(f"Endpoint must be an absolute URL: {endpoint}")
    return urlunsplit((parsed.scheme, parsed.netloc, "", "", ""))


def _assert_probe(
    base_url: str, path: str, expected_status: int, expected_body: dict[str, str]
) -> None:
    response = requests.get(f"{base_url}{path}", allow_redirects=False, timeout=5)
    if response.status_code != expected_status:
        raise AssertionError(
            f"Expected {path} status {expected_status}, received "
            f"{response.status_code}: {response.text}"
        )
    if response.json() != expected_body:
        raise AssertionError(
            f"Unexpected {path} response: {response.text}; expected {expected_body}"
        )
    if response.headers.get("Cache-Control", "").lower() != "no-store":
        raise AssertionError(
            f"Expected {path} Cache-Control: no-store, received "
            f"{response.headers.get('Cache-Control')}"
        )


async def _assert_health_endpoints(endpoint: str) -> None:
    """Check local health and readiness without MCP or upstream credentials."""
    base_url = _listener_base_url(endpoint)
    await asyncio.to_thread(_assert_probe, base_url, "/healthz", 200, {"status": "ok"})
    await asyncio.to_thread(
        _assert_probe, base_url, "/readyz", 200, {"status": "ready"}
    )


async def verify(endpoint: str) -> None:
    """Check tool discovery and authenticated execution against the Compose API."""
    await _assert_health_endpoints(endpoint)
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
    sys.stdout.write(
        "Container health/readiness, MCP discovery, and authenticated tool call passed.\n"
    )


if __name__ == "__main__":
    asyncio.run(verify(sys.argv[1]))
