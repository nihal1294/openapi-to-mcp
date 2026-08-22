"""Streamable HTTP transport for MCP server tests."""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

import requests
from mcp.types import CallToolResult, ListToolsResult

from openapi_to_mcp.adapters.testing.models import (
    ServerConnectionError,
    TransportStrategy,
    UnsupportedMethodError,
)
from openapi_to_mcp.adapters.testing.response_formatting import format_mcp_response

logger = logging.getLogger(__name__)
DEFAULT_PROTOCOL_VERSION = "2025-11-25"


def _normalize_result(
    response: dict[str, Any], method: str, req_id: int
) -> dict[str, Any]:
    if "error" in response or not isinstance(response.get("result"), dict):
        return response
    model_type = ListToolsResult if method == "list" else CallToolResult
    model = model_type.model_validate(response["result"])
    formatted = format_mcp_response(model, req_id)
    normalized = dict(response)
    normalized["result"] = {
        key: value for key, value in formatted.items() if key not in {"jsonrpc", "id"}
    }
    return normalized


class StreamableHttpTransport(TransportStrategy):
    """Execute MCP JSON-RPC requests through streamable HTTP."""

    def __init__(self, endpoint_url: str) -> None:
        if not endpoint_url:
            raise ValueError("endpoint_url is required for streamable-http transport")
        self.endpoint_url = endpoint_url
        self._session_id: str | None = None
        self._protocol_version = DEFAULT_PROTOCOL_VERSION

    def _build_jsonrpc_payload(
        self, method: str, params: dict[str, Any] | None, req_id: int
    ) -> dict[str, Any]:
        if method == "list":
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "method": "tools/list",
                "params": {},
            }
        if method == "call":
            if params is None or "tool_name" not in params:
                raise ValueError("Missing 'tool_name' in params for tool call method.")
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "method": "tools/call",
                "params": {
                    "name": params["tool_name"],
                    "arguments": params.get("tool_arguments", {}),
                },
            }
        raise UnsupportedMethodError(f"Unsupported method for testing: {method}")

    def _build_headers(self) -> dict[str, str]:
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
            "MCP-Protocol-Version": self._protocol_version,
        }
        if self._session_id:
            headers["Mcp-Session-Id"] = self._session_id
        return headers

    def _parse_json_response(self, response: requests.Response) -> dict[str, Any]:
        try:
            response_data = response.json()
        except json.JSONDecodeError as error:
            raise ServerConnectionError(
                f"Invalid JSON response from streamable-http endpoint: {error}"
            ) from error
        if not isinstance(response_data, dict):
            raise ServerConnectionError(
                "Unexpected non-object JSON response from streamable-http endpoint"
            )
        return response_data

    def _initialize(self, req_id: int) -> None:
        payload = {
            "jsonrpc": "2.0",
            "id": req_id,
            "method": "initialize",
            "params": {
                "protocolVersion": self._protocol_version,
                "capabilities": {},
                "clientInfo": {
                    "name": "openapi-to-mcp-tester",
                    "version": "0.1.0",
                },
            },
        }
        response = requests.post(
            self.endpoint_url,
            json=payload,
            timeout=30,
            headers=self._build_headers(),
        )
        response.raise_for_status()
        self._session_id = response.headers.get("Mcp-Session-Id")
        response_data = self._parse_json_response(response)
        if "error" in response_data:
            raise ServerConnectionError(
                f"Initialize request failed: {response_data['error']}"
            )
        self._send_initialized_notification()

    def _send_initialized_notification(self) -> None:
        response = requests.post(
            self.endpoint_url,
            json={
                "jsonrpc": "2.0",
                "method": "notifications/initialized",
                "params": {},
            },
            timeout=30,
            headers=self._build_headers(),
        )
        response.raise_for_status()

    def _post_jsonrpc(
        self, method: str, params: dict[str, Any] | None, req_id: int
    ) -> dict[str, Any]:
        self._initialize(req_id=req_id * 1000 + 1)
        response = requests.post(
            self.endpoint_url,
            json=self._build_jsonrpc_payload(method, params, req_id),
            timeout=30,
            headers=self._build_headers(),
        )
        response.raise_for_status()
        response_data = self._parse_json_response(response)
        return _normalize_result(response_data, method, req_id)

    async def connect_and_execute(
        self, method: str, params: dict[str, Any] | None, req_id: int
    ) -> dict[str, Any]:
        """Connect over streamable HTTP and return the JSON-RPC response."""
        logger.info("Connecting to streamable-http endpoint at %s", self.endpoint_url)
        try:
            return await asyncio.to_thread(self._post_jsonrpc, method, params, req_id)
        except Exception as error:
            logger.exception("Error during streamable-http connection")
            raise ServerConnectionError(
                f"Failed to connect via streamable-http: {error}"
            ) from error
