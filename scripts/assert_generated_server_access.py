"""Assert generated MCP server tool-access behavior for streamable-http."""

from __future__ import annotations

import argparse
import json
from typing import Any

import requests

DEFAULT_PROTOCOL_VERSION = "2025-11-25"


class StreamableHttpSession:
    """Keep one MCP streamable-http session alive across one access check."""

    def __init__(
        self,
        endpoint_url: str,
        identity_header: str | None,
        identity_value: str | None,
    ) -> None:
        self.endpoint_url = endpoint_url
        self.identity_header = identity_header
        self.identity_value = identity_value
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
                    "clientInfo": {
                        "name": "openapi-to-mcp-access-tester",
                        "version": "0.1.0",
                    },
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
        # Streamable HTTP commonly returns 202 here with no body; only HTTP status matters.
        initialized.raise_for_status()

    def list_tools(self) -> dict[str, Any]:
        return self._post_jsonrpc("tools/list", {}, 1)

    def call_tool(self, tool_name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        return self._post_jsonrpc(
            "tools/call", {"name": tool_name, "arguments": arguments}, 2
        )

    def _headers(self) -> dict[str, str]:
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
            "MCP-Protocol-Version": DEFAULT_PROTOCOL_VERSION,
        }
        if self.session_id:
            headers["Mcp-Session-Id"] = self.session_id
        if self.identity_header and self.identity_value:
            headers[self.identity_header] = self.identity_value
        return headers

    def _post_jsonrpc(
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


def _payload_error(payload: dict[str, Any]) -> None:
    raise AssertionError(json.dumps(payload, indent=2))


def _extract_result_payload(response: dict[str, Any]) -> dict[str, Any]:
    result = response.get("result")
    return result if isinstance(result, dict) else response


def _extract_text(payload: dict[str, Any]) -> str:
    content = payload.get("content")
    if not isinstance(content, list) or not content:
        _payload_error(payload)
    text = content[0].get("text")
    if not isinstance(text, str):
        _payload_error(payload)
    return text


def _assert_tool_list(
    response: dict[str, Any], tool_name: str, *, expected_listed: bool
) -> None:
    payload = _extract_result_payload(response)
    tools = payload.get("tools", [])
    names = [tool["name"] for tool in tools]
    present = tool_name in names
    if present != expected_listed:
        raise AssertionError(
            f"Expected listed={expected_listed} for {tool_name}. Found: {names}"
        )


def _assert_allowed(response: dict[str, Any], expected: dict[str, Any]) -> None:
    payload = _extract_result_payload(response)
    if payload.get("isError") is True:
        _payload_error(response)
    body = json.loads(_extract_text(payload))
    for key, value in expected.items():
        if body.get(key) != value:
            raise AssertionError(json.dumps(body, indent=2))


def _assert_denied(response: dict[str, Any], tool_name: str) -> None:
    payload = _extract_result_payload(response)
    if payload.get("isError") is not True:
        _payload_error(response)
    message = _extract_text(payload)
    if f"Tool '{tool_name}' is not available" not in message:
        _payload_error(response)
    meta = payload.get("meta")
    if not isinstance(meta, dict):
        _payload_error(response)
    error_meta = meta.get("error")
    if not isinstance(error_meta, dict):
        _payload_error(response)
    if error_meta.get("code") != "tool_not_allowed":
        _payload_error(response)
    if error_meta.get("source") != "auth":
        _payload_error(response)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--suite", choices=["allowed", "denied"], required=True)
    parser.add_argument("--endpoint-url", required=True)
    parser.add_argument("--tool-name", required=True)
    parser.add_argument("--identity-header")
    parser.add_argument("--identity-value")
    args = parser.parse_args()

    session = StreamableHttpSession(
        args.endpoint_url, args.identity_header, args.identity_value
    )
    session.initialize()

    if args.suite == "allowed":
        _assert_tool_list(session.list_tools(), args.tool_name, expected_listed=True)
        _assert_allowed(
            session.call_tool(args.tool_name, {"status": "available"}),
            {"status": "available"},
        )
        return

    _assert_tool_list(session.list_tools(), args.tool_name, expected_listed=False)
    _assert_denied(
        session.call_tool(args.tool_name, {"status": "available"}),
        args.tool_name,
    )


if __name__ == "__main__":
    main()
