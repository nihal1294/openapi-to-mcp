"""Assert generated MCP server cache and rate-limit behavior for E2E suites."""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from typing import Any

import requests

DEFAULT_PROTOCOL_VERSION = "2025-11-25"
DEFAULT_TOOL_NAME = "testConversionTool"
RATE_LIMIT_ERROR_META = {
    "code": "tool_rate_limited",
    "source": "runtime",
    "retryable": True,
}


@dataclass(frozen=True)
class ToolStep:
    arguments: dict[str, Any]
    expected: dict[str, Any] | None = None
    expected_error: str | None = None
    expected_error_meta: dict[str, Any] | None = None


SUITES = {
    "cached": [
        ToolStep(
            arguments={"status": "cached"},
            expected={"status": "cached", "call_count": 1},
        ),
        ToolStep(
            arguments={"status": "cached"},
            expected={"status": "cached", "call_count": 1},
        ),
    ],
    "rate-limited": [
        ToolStep(
            arguments={"status": "rate_limited"},
            expected={"status": "rate_limited", "call_count": 1},
        ),
        ToolStep(
            arguments={"status": "rate_limited"},
            expected_error="Tool rate limit exceeded",
            expected_error_meta=RATE_LIMIT_ERROR_META,
        ),
    ],
    "cached-rate-limited": [
        ToolStep(
            arguments={"status": "cached_rate_limited"},
            expected={"status": "cached_rate_limited", "call_count": 1},
        ),
        ToolStep(
            arguments={"status": "cached_rate_limited"},
            expected_error="Tool rate limit exceeded",
            expected_error_meta=RATE_LIMIT_ERROR_META,
        ),
    ],
}


class StreamableHttpSession:
    """Keep one MCP streamable-http session alive across a test suite."""

    def __init__(self, endpoint_url: str) -> None:
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
                    "clientInfo": {
                        "name": "openapi-to-mcp-performance-tester",
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
        initialized.raise_for_status()

    def list_tools(self) -> dict[str, Any]:
        return self._post_jsonrpc("tools/list", {}, 1)

    def call_tool(
        self, req_id: int, tool_name: str, arguments: dict[str, Any]
    ) -> dict[str, Any]:
        return self._post_jsonrpc(
            "tools/call", {"name": tool_name, "arguments": arguments}, req_id
        )

    def _headers(self) -> dict[str, str]:
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
            "MCP-Protocol-Version": DEFAULT_PROTOCOL_VERSION,
        }
        if self.session_id:
            headers["Mcp-Session-Id"] = self.session_id
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


def _assert_list_contains(response: dict[str, Any], tool_name: str) -> None:
    payload = _extract_result_payload(response)
    tools = payload.get("tools", [])
    names = [tool["name"] for tool in tools]
    if tool_name not in names:
        raise AssertionError(f"Missing tool in list output: {names}")


def _assert_success(response: dict[str, Any], expected: dict[str, Any]) -> None:
    payload = _extract_result_payload(response)
    if payload.get("isError") is True:
        _payload_error(response)
    body = json.loads(_extract_text(payload))
    for key, value in expected.items():
        if body.get(key) != value:
            raise AssertionError(json.dumps(body, indent=2))


def _assert_error(
    response: dict[str, Any], expected_error: str, expected_error_meta: dict[str, Any]
) -> None:
    payload = _extract_result_payload(response)
    if payload.get("isError") is not True:
        _payload_error(response)
    message = _extract_text(payload)
    if expected_error not in message:
        raise AssertionError(json.dumps(response, indent=2))
    meta = payload.get("meta")
    if not isinstance(meta, dict):
        _payload_error(response)
    error_meta = meta.get("error")
    if not isinstance(error_meta, dict):
        _payload_error(response)
    for key, value in expected_error_meta.items():
        if error_meta.get(key) != value:
            raise AssertionError(json.dumps(error_meta, indent=2))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--suite", choices=sorted(SUITES), required=True)
    parser.add_argument("--endpoint-url", required=True)
    parser.add_argument("--tool-name", default=DEFAULT_TOOL_NAME)
    args = parser.parse_args()

    session = StreamableHttpSession(args.endpoint_url)
    session.initialize()
    _assert_list_contains(session.list_tools(), args.tool_name)

    for req_id, step in enumerate(SUITES[args.suite], start=2):
        response = session.call_tool(req_id, args.tool_name, step.arguments)
        if step.expected_error:
            _assert_error(response, step.expected_error, step.expected_error_meta or {})
            continue
        _assert_success(response, step.expected or {})


if __name__ == "__main__":
    main()
