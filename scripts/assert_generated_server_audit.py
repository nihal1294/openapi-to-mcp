"""Assert generated audit-log redaction behavior for one streamable-http tool call."""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from typing import Any

import requests

DEFAULT_PROTOCOL_VERSION = "2025-11-25"
REDACTED = "[REDACTED]"


class StreamableHttpSession:
    """Keep one MCP streamable-http session alive for one audit assertion."""

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

    def call_tool(self, tool_name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        response = requests.post(
            self.endpoint_url,
            json=_jsonrpc_payload(
                "tools/call", 2, {"name": tool_name, "arguments": arguments}
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
        "clientInfo": {"name": "openapi-to-mcp-audit-tester", "version": "0.1.0"},
    }


def _extract_request_id(payload: dict[str, Any]) -> str:
    result = payload.get("result")
    if not isinstance(result, dict):
        raise TypeError(json.dumps(payload, indent=2))
    meta = result.get("meta")
    if not isinstance(meta, dict) or not isinstance(meta.get("requestId"), str):
        raise TypeError(json.dumps(payload, indent=2))
    return meta["requestId"]


def _load_matching_events(
    log_file: Path, request_id: str
) -> tuple[dict[str, Any], dict[str, Any]]:
    for _ in range(20):
        request_event: dict[str, Any] | None = None
        response_event: dict[str, Any] | None = None
        for line in log_file.read_text(encoding="utf-8").splitlines():
            try:
                payload = json.loads(line)
            except json.JSONDecodeError:
                continue
            if payload.get("requestId") != request_id:
                continue
            if payload.get("event") == "tool_audit_request":
                request_event = payload
            if payload.get("event") == "tool_audit_response":
                response_event = payload
        if request_event and response_event:
            return request_event, response_event
        time.sleep(0.25)
    raise AssertionError(log_file.read_text(encoding="utf-8"))


def _lookup_path(payload: dict[str, Any], path: str) -> object:
    current: object = payload
    for segment in path.split("."):
        if not isinstance(current, dict) or segment not in current:
            raise AssertionError(json.dumps(payload, indent=2))
        current = current[segment]
    return current


def _assert_redacted(value: object, payload: dict[str, Any]) -> None:
    if value != REDACTED:
        raise AssertionError(json.dumps(payload, indent=2))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--endpoint-url", required=True)
    parser.add_argument("--tool-name", required=True)
    parser.add_argument("--tool-arguments", required=True)
    parser.add_argument("--log-file", required=True)
    args = parser.parse_args()

    session = StreamableHttpSession(args.endpoint_url)
    session.initialize()
    response = session.call_tool(args.tool_name, json.loads(args.tool_arguments))
    request_id = _extract_request_id(response)
    request_event, response_event = _load_matching_events(
        Path(args.log_file), request_id
    )

    _assert_redacted(request_event["headers"]["Authorization"], request_event)
    _assert_redacted(request_event["query"]["status"], request_event)
    _assert_redacted(
        _lookup_path(request_event["requestBody"], "credentials.token"),
        request_event,
    )
    _assert_redacted(
        _lookup_path(request_event["requestBody"], "profile.email"),
        request_event,
    )
    if response_event["outcome"] != "success":
        raise AssertionError(json.dumps(response_event, indent=2))
    _assert_redacted(
        _lookup_path(response_event["responseBody"], "echoed.credentials.token"),
        response_event,
    )
    _assert_redacted(
        _lookup_path(response_event["responseBody"], "echoed.profile.email"),
        response_event,
    )


if __name__ == "__main__":
    main()
