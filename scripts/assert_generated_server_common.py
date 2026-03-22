"""Shared helpers for generated-server streamable-http assertion scripts."""

from __future__ import annotations

import json
from typing import Any

import requests

DEFAULT_PROTOCOL_VERSION = "2025-11-25"


class StreamableHttpSession:
    """Keep one MCP streamable-http session alive across a test suite."""

    def __init__(self, endpoint_url: str, client_name: str) -> None:
        self.client_name = client_name
        self.endpoint_url = endpoint_url
        self.session_id: str | None = None

    def initialize(self) -> None:
        response = requests.post(
            self.endpoint_url,
            json={
                "jsonrpc": "2.0",
                "id": 1001,
                "method": "initialize",
                "params": {
                    "protocolVersion": DEFAULT_PROTOCOL_VERSION,
                    "capabilities": {},
                    "clientInfo": {"name": self.client_name, "version": "0.1.0"},
                },
            },
            timeout=30,
            headers=self._headers(),
        )
        response.raise_for_status()
        self.session_id = response.headers.get("Mcp-Session-Id")
        initialized = requests.post(
            self.endpoint_url,
            json={
                "jsonrpc": "2.0",
                "method": "notifications/initialized",
                "params": {},
            },
            timeout=30,
            headers=self._headers(),
        )
        initialized.raise_for_status()

    def list_tools(self) -> dict[str, Any]:
        return self.post_jsonrpc("tools/list", {}, 1)

    def post_jsonrpc(
        self, method: str, params: dict[str, Any], req_id: int
    ) -> dict[str, Any]:
        response = requests.post(
            self.endpoint_url,
            json={"jsonrpc": "2.0", "id": req_id, "method": method, "params": params},
            timeout=30,
            headers=self._headers(),
        )
        response.raise_for_status()
        return response.json()

    def _headers(self) -> dict[str, str]:
        headers = {
            "Accept": "application/json, text/event-stream",
            "Content-Type": "application/json",
            "MCP-Protocol-Version": DEFAULT_PROTOCOL_VERSION,
        }
        if self.session_id:
            headers["Mcp-Session-Id"] = self.session_id
        return headers


def payload_error(payload: dict[str, Any]) -> None:
    """Raise a readable assertion error for malformed responses."""
    raise AssertionError(json.dumps(payload, indent=2))


def extract_result_payload(response: dict[str, Any]) -> dict[str, Any]:
    """Return the JSON-RPC result payload when present."""
    result = response.get("result")
    return result if isinstance(result, dict) else response


def extract_text(payload: dict[str, Any]) -> str:
    """Return the first text content item from a tool response."""
    content = payload.get("content")
    if not isinstance(content, list) or not content:
        payload_error(payload)
    text = content[0].get("text")
    if not isinstance(text, str):
        payload_error(payload)
    return text


def assert_list_contains(response: dict[str, Any], tool_name: str) -> None:
    """Assert that the listed tool names include the expected tool."""
    payload = extract_result_payload(response)
    tools = payload.get("tools", [])
    names = [tool["name"] for tool in tools]
    if tool_name not in names:
        raise AssertionError(f"Missing tool in list output: {names}")
