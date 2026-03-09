"""Assert generated runtime request-id behavior for one tool call."""

from __future__ import annotations

import argparse
import asyncio
import json
from typing import Any

from openapi_to_mcp.adapters.testing.server_tester import execute_mcp_server
from openapi_to_mcp.common.utils import parse_env_source


def _payload_error(payload: dict[str, Any]) -> None:
    raise AssertionError(json.dumps(payload, indent=2))


def _transport_kwargs(args: argparse.Namespace) -> dict[str, Any]:
    if args.transport == "stdio":
        return {
            "server_cmd": args.server_cmd,
            "env": parse_env_source(args.env_source),
        }
    return {"endpoint_url": args.endpoint_url}


def _extract_payload(response: dict[str, Any]) -> dict[str, Any]:
    result = response.get("result")
    return result if isinstance(result, dict) else response


def _extract_request_id(payload: dict[str, Any]) -> str:
    meta = payload.get("meta")
    if not isinstance(meta, dict) or not isinstance(meta.get("requestId"), str):
        _payload_error(payload)
    return meta["requestId"]


def _extract_text(payload: dict[str, Any]) -> str:
    content = payload.get("content")
    if not isinstance(content, list) or not content:
        _payload_error(payload)
    text = content[0].get("text")
    if not isinstance(text, str):
        raise TypeError(json.dumps(payload, indent=2))
    return text


def _assert_success_correlation(payload: dict[str, Any], request_id: str) -> None:
    text = _extract_text(payload)
    body = json.loads(text)
    if body.get("request_id") != request_id:
        _payload_error(payload)


def _assert_error_request_id(payload: dict[str, Any]) -> None:
    if payload.get("isError") is not True:
        _payload_error(payload)


async def _main(args: argparse.Namespace) -> None:
    response = await execute_mcp_server(
        transport=args.transport,
        method="call",
        req_id=1,
        params={
            "tool_name": args.tool_name,
            "tool_arguments": json.loads(args.tool_arguments),
        },
        **_transport_kwargs(args),
    )
    payload = _extract_payload(response)
    request_id = _extract_request_id(payload)
    if args.expect_error:
        _assert_error_request_id(payload)
        return
    _assert_success_correlation(payload, request_id)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--transport", choices=["stdio", "streamable-http"], required=True
    )
    parser.add_argument("--server-cmd")
    parser.add_argument("--env-source")
    parser.add_argument("--endpoint-url")
    parser.add_argument("--tool-name", required=True)
    parser.add_argument("--tool-arguments", required=True)
    parser.add_argument("--expect-error", action="store_true")
    asyncio.run(_main(parser.parse_args()))


if __name__ == "__main__":
    main()
