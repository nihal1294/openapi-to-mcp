"""Assert cached tool calls still emit paired audit events."""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from typing import Any

import requests

DEFAULT_PROTOCOL_VERSION = "2025-11-25"


class StreamableHttpSession:
    """Keep one MCP streamable-http session alive for one cached-audit assertion."""

    def __init__(self, endpoint_url: str) -> None:
        self.endpoint_url = endpoint_url
        self.session_id: str | None = None

    def initialize(self) -> None:
        response = requests.post(
            self.endpoint_url,
            json=_jsonrpc_payload("initialize", 1001, _initialize_params()),
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

    def call_tool(
        self, req_id: int, tool_name: str, arguments: dict[str, Any]
    ) -> dict[str, Any]:
        response = requests.post(
            self.endpoint_url,
            json=_jsonrpc_payload(
                "tools/call", req_id, {"name": tool_name, "arguments": arguments}
            ),
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


def _jsonrpc_payload(
    method: str, req_id: int, params: dict[str, Any]
) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": req_id, "method": method, "params": params}


def _initialize_params() -> dict[str, Any]:
    return {
        "protocolVersion": DEFAULT_PROTOCOL_VERSION,
        "capabilities": {},
        "clientInfo": {"name": "openapi-to-mcp-cached-audit", "version": "0.1.0"},
    }


def _extract_request_id(payload: dict[str, Any]) -> str:
    result = payload.get("result")
    if not isinstance(result, dict):
        raise TypeError(json.dumps(payload, indent=2))
    meta = result.get("meta")
    if not isinstance(meta, dict) or not isinstance(meta.get("requestId"), str):
        raise TypeError(json.dumps(payload, indent=2))
    return meta["requestId"]


def _load_events(log_file: Path) -> list[dict[str, Any]]:
    for _ in range(20):
        events: list[dict[str, Any]] = []
        for line in log_file.read_text(encoding="utf-8").splitlines():
            try:
                events.append(json.loads(line))
            except json.JSONDecodeError:
                continue
        if events:
            return events
        time.sleep(0.25)
    raise AssertionError(log_file.read_text(encoding="utf-8"))


def _find_event(
    events: list[dict[str, Any]], request_id: str, event_name: str
) -> dict[str, Any]:
    for event in events:
        if event.get("requestId") == request_id and event.get("event") == event_name:
            return event
    raise AssertionError(json.dumps(events, indent=2))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--endpoint-url", required=True)
    parser.add_argument("--tool-name", required=True)
    parser.add_argument("--tool-arguments", required=True)
    parser.add_argument("--log-file", required=True)
    args = parser.parse_args()

    session = StreamableHttpSession(args.endpoint_url)
    session.initialize()
    arguments = json.loads(args.tool_arguments)
    first_request_id = _extract_request_id(
        session.call_tool(2, args.tool_name, arguments)
    )
    second_request_id = _extract_request_id(
        session.call_tool(3, args.tool_name, arguments)
    )
    events = _load_events(Path(args.log_file))

    first_request = _find_event(events, first_request_id, "tool_audit_request")
    first_response = _find_event(events, first_request_id, "tool_audit_response")
    second_request = _find_event(events, second_request_id, "tool_audit_request")
    second_response = _find_event(events, second_request_id, "tool_audit_response")

    if first_response.get("cacheHit") is True:
        raise AssertionError(json.dumps(first_response, indent=2))
    if second_response.get("cacheHit") is not True:
        raise AssertionError(json.dumps(second_response, indent=2))
    if first_request.get("event") != "tool_audit_request":
        raise AssertionError(json.dumps(first_request, indent=2))
    if second_request.get("event") != "tool_audit_request":
        raise AssertionError(json.dumps(second_request, indent=2))


if __name__ == "__main__":
    main()
