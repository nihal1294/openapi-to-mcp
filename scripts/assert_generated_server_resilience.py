"""Assert generated MCP server retry and circuit-breaker behavior for E2E suites."""

from __future__ import annotations

import argparse
import json
import time
from typing import Any

import requests
from assert_generated_server_common import (
    StreamableHttpSession,
    assert_list_contains,
    extract_result_payload,
    extract_text,
    extract_wire_meta,
)

ONE_CALL, TWO_CALLS, THIRD_ATTEMPT = 1, 2, 3


def _call_status(
    session: StreamableHttpSession, req_id: int, tool_name: str, status: str
) -> dict[str, Any]:
    return session.call_tool(tool_name, {"status": status}, req_id)


def _assert_success(response: dict[str, Any], status: str) -> None:
    payload = extract_result_payload(response)
    if payload.get("isError") is True:
        raise AssertionError(json.dumps(response, indent=2))
    if json.loads(extract_text(payload)).get("status") != status:
        raise AssertionError(json.dumps(response, indent=2))


def _assert_error(
    response: dict[str, Any], expected_text: str, expected_meta: dict[str, Any]
) -> dict[str, Any]:
    payload = extract_result_payload(response)
    if payload.get("isError") is not True or expected_text not in extract_text(payload):
        raise AssertionError(json.dumps(response, indent=2))
    meta = extract_wire_meta(response).get("error")
    if not isinstance(meta, dict):
        raise TypeError(json.dumps(response, indent=2))
    for key, value in expected_meta.items():
        if meta.get(key) != value:
            raise AssertionError(json.dumps(meta, indent=2))
    return meta


def _assert_retry_after(meta: dict[str, Any]) -> None:
    retry_after_ms = meta.get("retryAfterMs")
    if not isinstance(retry_after_ms, int) or retry_after_ms <= 0:
        raise AssertionError(json.dumps(meta, indent=2))


def _call_count(mock_base_url: str, query_string: str) -> int:
    response = requests.get(
        f"{mock_base_url}/call-count",
        params={"path": "/test", "query": query_string},
        timeout=30,
    )
    response.raise_for_status()
    return int(response.json()["call_count"])


def _assert_call_count(mock_base_url: str, query_string: str, expected: int) -> None:
    actual = _call_count(mock_base_url, query_string)
    if actual != expected:
        raise AssertionError(
            f"Unexpected call count for {query_string}: {actual} != {expected}"
        )


def run_retry_recovers(
    session: StreamableHttpSession, mock_base_url: str, tool_name: str, _: int
) -> None:
    _assert_success(_call_status(session, 3, tool_name, "flaky_once"), "flaky_once")
    _assert_call_count(mock_base_url, "status=flaky_once", TWO_CALLS)


def run_retry_budget_exhausted(
    session: StreamableHttpSession, mock_base_url: str, tool_name: str, _: int
) -> None:
    meta = _assert_error(
        _call_status(session, 3, tool_name, "flaky_twice"),
        "Retry budget exhausted",
        {"code": "retry_budget_exhausted", "source": "runtime", "retryable": True},
    )
    _assert_retry_after(meta)
    if meta.get("attempts") != THIRD_ATTEMPT:
        raise AssertionError(json.dumps(meta, indent=2))
    _assert_call_count(mock_base_url, "status=flaky_twice", TWO_CALLS)


def run_circuit_breaker_open(
    session: StreamableHttpSession, mock_base_url: str, tool_name: str, _: int
) -> None:
    expected_meta = {
        "code": "api_server_error",
        "source": "upstream",
        "retryable": True,
    }
    _assert_error(
        _call_status(session, 3, tool_name, "breaker_error"),
        "API server error (503)",
        expected_meta,
    )
    _assert_error(
        _call_status(session, 4, tool_name, "client_error"),
        "API bad request",
        {"code": "api_bad_request", "source": "upstream", "retryable": False},
    )
    _assert_error(
        _call_status(session, 5, tool_name, "breaker_error"),
        "API server error (503)",
        expected_meta,
    )
    meta = _assert_error(
        _call_status(session, 6, tool_name, "breaker_error"),
        "Circuit breaker is open",
        {"code": "circuit_breaker_open", "source": "runtime", "retryable": True},
    )
    _assert_retry_after(meta)
    _assert_call_count(mock_base_url, "status=breaker_error", TWO_CALLS)
    _assert_call_count(mock_base_url, "status=client_error", ONE_CALL)


def run_circuit_breaker_recovery(
    session: StreamableHttpSession, mock_base_url: str, tool_name: str, cooldown_ms: int
) -> None:
    success_status = "breaker_recovery_ok"
    expected_meta = {
        "code": "api_server_error",
        "source": "upstream",
        "retryable": True,
    }
    _assert_error(
        _call_status(session, 3, tool_name, "breaker_recovery_error"),
        "API server error (503)",
        expected_meta,
    )
    _assert_error(
        _call_status(session, 4, tool_name, success_status),
        "Circuit breaker is open",
        {"code": "circuit_breaker_open", "source": "runtime", "retryable": True},
    )
    time.sleep((cooldown_ms + 250) / 1000)
    _assert_success(_call_status(session, 5, tool_name, success_status), success_status)
    _assert_success(_call_status(session, 6, tool_name, success_status), success_status)
    _assert_call_count(mock_base_url, "status=breaker_recovery_error", ONE_CALL)
    _assert_call_count(mock_base_url, f"status={success_status}", TWO_CALLS)


SUITES = {
    "retry-recovers": run_retry_recovers,
    "retry-budget-exhausted": run_retry_budget_exhausted,
    "circuit-breaker-open": run_circuit_breaker_open,
    "circuit-breaker-recovery": run_circuit_breaker_recovery,
}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--suite", choices=sorted(SUITES), required=True)
    parser.add_argument("--endpoint-url", required=True)
    parser.add_argument("--mock-base-url", required=True)
    parser.add_argument("--tool-name", default="testConversionTool")
    parser.add_argument("--cooldown-ms", type=int, default=2000)
    args = parser.parse_args()

    session = StreamableHttpSession(args.endpoint_url, "resilience-tester")
    session.initialize()
    assert_list_contains(session.list_tools(), args.tool_name)
    SUITES[args.suite](session, args.mock_base_url, args.tool_name, args.cooldown_ms)


if __name__ == "__main__":
    main()
