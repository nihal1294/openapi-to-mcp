"""Assert generated MCP server behavior for E2E suites."""

from __future__ import annotations

import argparse
import asyncio
import json
from typing import Any

from openapi_to_mcp.adapters.testing import ConnectionSettings, ServerTestRequest
from openapi_to_mcp.adapters.testing.server_tester import execute_mcp_server
from openapi_to_mcp.common.utils import parse_env_source
from scripts.assert_generated_server_suites import SUITES, ToolExpectation


def _extract_result_payload(response: dict[str, Any]) -> dict[str, Any]:
    result = response.get("result")
    return result if isinstance(result, dict) else response


def _extract_text_content(payload: dict[str, Any]) -> str:
    content = payload.get("content")
    if not isinstance(content, list) or not content:
        raise TypeError(json.dumps(payload, indent=2))
    text = content[0].get("text")
    if not isinstance(text, str):
        raise TypeError(json.dumps(payload, indent=2))
    return text


def _extract_json_content(response: dict[str, Any]) -> dict[str, Any]:
    if "error" in response:
        raise AssertionError(json.dumps(response, indent=2))
    payload = _extract_result_payload(response)
    if payload.get("isError") is True:
        raise AssertionError(json.dumps(response, indent=2))
    text = _extract_text_content(payload)
    return json.loads(text)


def _build_connection_settings(args: argparse.Namespace) -> ConnectionSettings:
    if args.transport == "stdio":
        return ConnectionSettings(
            server_cmd=args.server_cmd,
            env=parse_env_source(args.env_source),
        )
    return ConnectionSettings(endpoint_url=args.endpoint_url)


async def _run_request(
    args: argparse.Namespace,
    method: str,
    req_id: int,
    params: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return await execute_mcp_server(
        ServerTestRequest(
            transport=args.transport,
            method=method,
            params=params,
            req_id=req_id,
            connection=_build_connection_settings(args),
        )
    )


async def _assert_list_contains(
    args: argparse.Namespace, expectations: list[ToolExpectation]
) -> None:
    response = await _run_request(args, "list", 1)
    payload = _extract_result_payload(response)
    tools = payload.get("tools", [])
    names = [tool["name"] for tool in tools]
    expected_names = [expectation.name for expectation in expectations]
    missing = [name for name in expected_names if name not in names]
    if missing:
        raise AssertionError(f"Missing tools: {missing}. Found: {names}")


def _assert_success_payload(
    response: dict[str, Any], expected: dict[str, Any] | None
) -> None:
    payload = _extract_json_content(response)
    if expected is None:
        return
    for key, value in expected.items():
        if payload.get(key) != value:
            raise AssertionError(json.dumps(payload, indent=2))


def _extract_error_meta(response: dict[str, Any]) -> dict[str, Any] | None:
    error = response.get("error")
    if isinstance(error, dict):
        data = error.get("data")
        return data if isinstance(data, dict) else None
    payload = _extract_result_payload(response)
    meta = payload.get("meta")
    if not isinstance(meta, dict):
        return None
    error_meta = meta.get("error")
    return error_meta if isinstance(error_meta, dict) else None


def _assert_error_payload(
    response: dict[str, Any],
    expected_error: str,
    expected_error_meta: dict[str, Any] | None,
) -> None:
    error = response.get("error")
    if isinstance(error, dict):
        message = str(error.get("message", ""))
    else:
        payload = _extract_result_payload(response)
        if payload.get("isError") is not True:
            raise TypeError(json.dumps(response, indent=2))
        message = _extract_text_content(payload)
    if expected_error not in message:
        raise AssertionError(json.dumps(response, indent=2))
    if expected_error_meta is None:
        return
    actual_meta = _extract_error_meta(response)
    if not isinstance(actual_meta, dict):
        raise TypeError(json.dumps(response, indent=2))
    for key, value in expected_error_meta.items():
        if actual_meta.get(key) != value:
            raise AssertionError(json.dumps(response, indent=2))


async def _assert_tool(
    args: argparse.Namespace, req_id: int, expectation: ToolExpectation
) -> None:
    response = await _run_request(
        args,
        "call",
        req_id,
        {
            "tool_name": expectation.name,
            "tool_arguments": expectation.arguments,
        },
    )
    if expectation.expected_error:
        _assert_error_payload(
            response,
            expectation.expected_error,
            expectation.expected_error_meta,
        )
        return
    _assert_success_payload(response, expectation.expected)


async def _run_suite(args: argparse.Namespace) -> None:
    expectations = SUITES[args.suite]
    await _assert_list_contains(args, expectations)
    for req_id, expectation in enumerate(expectations, start=2):
        await _assert_tool(args, req_id, expectation)


def main() -> None:
    """Parse CLI arguments and run the selected generated-server suite."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--suite", choices=sorted(SUITES), required=True)
    parser.add_argument(
        "--transport", choices=["stdio", "streamable-http"], required=True
    )
    parser.add_argument("--server-cmd")
    parser.add_argument("--env-source")
    parser.add_argument("--endpoint-url")
    args = parser.parse_args()
    asyncio.run(_run_suite(args))


if __name__ == "__main__":
    main()
