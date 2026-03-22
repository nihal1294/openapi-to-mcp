"""Assert generated MCP server retry and circuit-breaker behavior for E2E suites."""

from __future__ import annotations

import argparse
import json
import time
from typing import Any

import requests

PROTOCOL_VERSION = "2025-11-25"
ONE_CALL, TWO_CALLS, THIRD_ATTEMPT = 1, 2, 3


class StreamableHttpSession:
    def __init__(self, endpoint_url: str) -> None:
        self.endpoint_url = endpoint_url
        self.session_id: str | None = None

    def initialize(self) -> None:
        response = requests.post(
            self.endpoint_url,
            json={
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": PROTOCOL_VERSION,
                    "capabilities": {},
                    "clientInfo": {"name": "resilience-tester", "version": "0.1.0"},
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
        return self._post_jsonrpc("tools/list", {}, 2)

    def call_tool(self, req_id: int, tool_name: str, status: str) -> dict[str, Any]:
        return self._post_jsonrpc(
            "tools/call",
            {"name": tool_name, "arguments": {"status": status}},
            req_id,
        )

    def _headers(self) -> dict[str, str]:
        headers = {
            "Accept": "application/json, text/event-stream",
            "Content-Type": "application/json",
            "MCP-Protocol-Version": PROTOCOL_VERSION,
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


def _result_payload(response: dict[str, Any]) -> dict[str, Any]:
    result = response.get("result")
    return result if isinstance(result, dict) else response


def _text_content(payload: dict[str, Any]) -> str:
    content = payload.get("content")
    if not isinstance(content, list) or not content:
        raise AssertionError(json.dumps(payload, indent=2))
    text = content[0].get("text")
    if not isinstance(text, str):
        raise TypeError(json.dumps(payload, indent=2))
    return text


def _assert_list_contains(response: dict[str, Any], tool_name: str) -> None:
    tools = _result_payload(response).get("tools", [])
    names = [tool["name"] for tool in tools]
    if tool_name not in names:
        raise AssertionError(f"Missing tool in list output: {names}")


def _assert_success(response: dict[str, Any], status: str) -> None:
    payload = _result_payload(response)
    if payload.get("isError") is True:
        raise AssertionError(json.dumps(response, indent=2))
    if json.loads(_text_content(payload)).get("status") != status:
        raise AssertionError(json.dumps(response, indent=2))


def _assert_error(
    response: dict[str, Any], expected_text: str, expected_meta: dict[str, Any]
) -> dict[str, Any]:
    payload = _result_payload(response)
    if payload.get("isError") is not True or expected_text not in _text_content(
        payload
    ):
        raise AssertionError(json.dumps(response, indent=2))
    meta = payload.get("meta", {}).get("error")
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
    _assert_success(session.call_tool(3, tool_name, "flaky_once"), "flaky_once")
    _assert_call_count(mock_base_url, "status=flaky_once", TWO_CALLS)


def run_retry_budget_exhausted(
    session: StreamableHttpSession, mock_base_url: str, tool_name: str, _: int
) -> None:
    meta = _assert_error(
        session.call_tool(3, tool_name, "flaky_twice"),
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
        session.call_tool(3, tool_name, "breaker_error"),
        "API server error (503)",
        expected_meta,
    )
    _assert_error(
        session.call_tool(4, tool_name, "client_error"),
        "API bad request",
        {"code": "api_bad_request", "source": "upstream", "retryable": False},
    )
    _assert_error(
        session.call_tool(5, tool_name, "breaker_error"),
        "API server error (503)",
        expected_meta,
    )
    meta = _assert_error(
        session.call_tool(6, tool_name, "breaker_error"),
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
        session.call_tool(3, tool_name, "breaker_recovery_error"),
        "API server error (503)",
        expected_meta,
    )
    _assert_error(
        session.call_tool(4, tool_name, success_status),
        "Circuit breaker is open",
        {"code": "circuit_breaker_open", "source": "runtime", "retryable": True},
    )
    time.sleep((cooldown_ms + 250) / 1000)
    _assert_success(session.call_tool(5, tool_name, success_status), success_status)
    _assert_success(session.call_tool(6, tool_name, success_status), success_status)
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

    session = StreamableHttpSession(args.endpoint_url)
    session.initialize()
    _assert_list_contains(session.list_tools(), args.tool_name)
    SUITES[args.suite](session, args.mock_base_url, args.tool_name, args.cooldown_ms)


if __name__ == "__main__":
    main()
