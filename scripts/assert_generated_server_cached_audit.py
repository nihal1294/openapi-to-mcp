"""Assert cached tool calls still emit paired audit events."""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from typing import Any

from assert_generated_server_common import StreamableHttpSession, extract_wire_meta


def _extract_request_id(payload: dict[str, Any]) -> str:
    meta = extract_wire_meta(payload)
    if not isinstance(meta.get("requestId"), str):
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

    session = StreamableHttpSession(args.endpoint_url, "openapi-to-mcp-cached-audit")
    session.initialize()
    arguments = json.loads(args.tool_arguments)
    first_request_id = _extract_request_id(
        session.call_tool(args.tool_name, arguments, 2)
    )
    second_request_id = _extract_request_id(
        session.call_tool(args.tool_name, arguments, 3)
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
