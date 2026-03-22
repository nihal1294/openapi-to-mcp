"""Assert generated MCP server cache and rate-limit behavior for E2E suites."""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from typing import Any

from assert_generated_server_common import (
    StreamableHttpSession,
    assert_list_contains,
    extract_result_payload,
    extract_text,
    payload_error,
)

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
        ToolStep({"status": "cached"}, {"status": "cached", "call_count": 1}),
        ToolStep({"status": "cached"}, {"status": "cached", "call_count": 1}),
    ],
    "rate-limited": [
        ToolStep(
            {"status": "rate_limited"}, {"status": "rate_limited", "call_count": 1}
        ),
        ToolStep(
            {"status": "rate_limited"},
            expected_error="Tool rate limit exceeded",
            expected_error_meta=RATE_LIMIT_ERROR_META,
        ),
    ],
    "cached-rate-limited": [
        ToolStep(
            {"status": "cached_rate_limited"},
            {"status": "cached_rate_limited", "call_count": 1},
        ),
        ToolStep(
            {"status": "cached_rate_limited"},
            expected_error="Tool rate limit exceeded",
            expected_error_meta=RATE_LIMIT_ERROR_META,
        ),
    ],
    "preset-cached": [
        ToolStep(
            {"status": "preset_cached"},
            {"status": "preset_cached", "call_count": 1},
        ),
        ToolStep(
            {"status": "preset_cached"},
            {"status": "preset_cached", "call_count": 1},
        ),
    ],
    "preset-uncached": [
        ToolStep(
            {"status": "preset_uncached"},
            {"status": "preset_uncached", "call_count": 1},
        ),
        ToolStep(
            {"status": "preset_uncached"},
            {"status": "preset_uncached", "call_count": 2},
        ),
    ],
}


def _assert_success(response: dict[str, Any], expected: dict[str, Any]) -> None:
    payload = extract_result_payload(response)
    if payload.get("isError") is True:
        payload_error(response)
    body = json.loads(extract_text(payload))
    for key, value in expected.items():
        if body.get(key) != value:
            raise AssertionError(json.dumps(body, indent=2))


def _assert_error(
    response: dict[str, Any], expected_error: str, expected_error_meta: dict[str, Any]
) -> None:
    payload = extract_result_payload(response)
    if payload.get("isError") is not True:
        payload_error(response)
    message = extract_text(payload)
    if expected_error not in message:
        raise AssertionError(json.dumps(response, indent=2))
    meta = payload.get("meta")
    if not isinstance(meta, dict):
        payload_error(response)
    error_meta = meta.get("error")
    if not isinstance(error_meta, dict):
        payload_error(response)
    for key, value in expected_error_meta.items():
        if error_meta.get(key) != value:
            raise AssertionError(json.dumps(error_meta, indent=2))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--suite", choices=sorted(SUITES), required=True)
    parser.add_argument("--endpoint-url", required=True)
    parser.add_argument("--tool-name", default=DEFAULT_TOOL_NAME)
    args = parser.parse_args()

    session = StreamableHttpSession(
        args.endpoint_url, "openapi-to-mcp-performance-tester"
    )
    session.initialize()
    assert_list_contains(session.list_tools(), args.tool_name)

    for req_id, step in enumerate(SUITES[args.suite], start=2):
        response = session.post_jsonrpc(
            "tools/call", {"name": args.tool_name, "arguments": step.arguments}, req_id
        )
        if step.expected_error:
            _assert_error(response, step.expected_error, step.expected_error_meta or {})
            continue
        _assert_success(response, step.expected or {})


if __name__ == "__main__":
    main()
