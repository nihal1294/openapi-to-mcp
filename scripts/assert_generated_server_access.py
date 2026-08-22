"""Assert generated MCP server tool-access behavior for streamable-http."""

from __future__ import annotations

import argparse
import json
from typing import Any

from assert_generated_server_common import (
    StreamableHttpSession,
    extract_result_payload,
    extract_text,
    extract_wire_meta,
    payload_error,
)


def _assert_tool_list(
    response: dict[str, Any], tool_name: str, *, expected_listed: bool
) -> None:
    payload = extract_result_payload(response)
    tools = payload.get("tools", [])
    names = [tool["name"] for tool in tools]
    present = tool_name in names
    if present != expected_listed:
        raise AssertionError(
            f"Expected listed={expected_listed} for {tool_name}. Found: {names}"
        )


def _assert_allowed(response: dict[str, Any], expected: dict[str, Any]) -> None:
    payload = extract_result_payload(response)
    if payload.get("isError") is True:
        payload_error(response)
    body = json.loads(extract_text(payload))
    for key, value in expected.items():
        if body.get(key) != value:
            raise AssertionError(json.dumps(body, indent=2))


def _assert_denied(response: dict[str, Any], tool_name: str) -> None:
    payload = extract_result_payload(response)
    if payload.get("isError") is not True:
        payload_error(response)
    message = extract_text(payload)
    if f"Tool '{tool_name}' is not available" not in message:
        payload_error(response)
    meta = extract_wire_meta(response)
    error_meta = meta.get("error")
    if not isinstance(error_meta, dict):
        payload_error(response)
    if error_meta.get("code") != "tool_not_allowed":
        payload_error(response)
    if error_meta.get("source") != "auth":
        payload_error(response)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--suite", choices=["allowed", "denied"], required=True)
    parser.add_argument("--endpoint-url", required=True)
    parser.add_argument("--tool-name", required=True)
    parser.add_argument("--identity-header")
    parser.add_argument("--identity-value")
    args = parser.parse_args()

    session = StreamableHttpSession(
        args.endpoint_url,
        "openapi-to-mcp-access-tester",
        args.identity_header,
        args.identity_value,
    )
    session.initialize()

    if args.suite == "allowed":
        _assert_tool_list(session.list_tools(), args.tool_name, expected_listed=True)
        _assert_allowed(
            session.call_tool(args.tool_name, {"status": "available"}, 2),
            {"status": "available"},
        )
        return

    _assert_tool_list(session.list_tools(), args.tool_name, expected_listed=False)
    _assert_denied(
        session.call_tool(args.tool_name, {"status": "available"}, 2),
        args.tool_name,
    )


if __name__ == "__main__":
    main()
