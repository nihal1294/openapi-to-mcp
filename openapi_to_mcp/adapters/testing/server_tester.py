"""Server testing adapter for MCP servers."""

from __future__ import annotations

import asyncio
import json
import logging
import shlex
from collections.abc import Mapping
from typing import TYPE_CHECKING, Any

import requests
from mcp import (
    ClientSession,
    ListToolsResult,
    McpError,
    StdioServerParameters,
    stdio_client,
)

from openapi_to_mcp.common import OpenApiMcpError

if TYPE_CHECKING:
    from mcp.types import CallToolResult

logger = logging.getLogger(__name__)
DEFAULT_PROTOCOL_VERSION = "2025-11-25"


class UnsupportedMethodError(OpenApiMcpError):
    """Exception raised when an unsupported MCP method is requested."""


class ServerConnectionError(OpenApiMcpError):
    """Exception raised when there's an issue connecting to the MCP server."""


class TransportStrategy:
    """Base class for different transport strategies."""

    async def connect_and_execute(
        self, method: str, params: dict[str, Any] | None, req_id: int
    ) -> dict[str, Any]:
        """Connect to the server and execute the requested method."""
        raise NotImplementedError("Subclasses must implement this method")


class StdioTransport(TransportStrategy):
    """Transport strategy for stdio connections."""

    def __init__(self, server_cmd: str, env: dict[str, str] | None = None) -> None:
        if not server_cmd:
            raise ValueError("server_cmd is required for stdio transport")
        self.server_cmd = server_cmd
        self.env = env

    async def connect_and_execute(
        self, method: str, params: dict[str, Any] | None, req_id: int
    ) -> dict[str, Any]:
        logger.info("Starting server process: %s", self.server_cmd)
        cmd_list = shlex.split(self.server_cmd)
        stdio_params = StdioServerParameters(
            command=cmd_list[0],
            args=cmd_list[1:],
            env=self.env,
        )

        try:
            async with stdio_client(stdio_params) as (read, write):
                logger.info("Stdio client connected.")
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    logger.info("MCP session initialized.")
                    try:
                        response_data = await _perform_mcp_request(
                            session, method, params
                        )
                    except McpError as e:
                        logger.info(
                            "Received MCP error response over stdio: %s",
                            e.error.message,
                        )
                        return _format_mcp_error(e, req_id)
                    logger.info("Received response from MCP server.")
                    return _format_response(response_data, req_id)
        except Exception as e:
            logger.exception("Error during stdio connection")
            raise ServerConnectionError(f"Failed to connect via stdio: {e}") from e


class StreamableHttpTransport(TransportStrategy):
    """Transport strategy for streamable HTTP endpoint calls."""

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
        headers: dict[str, str] = {
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
        except json.JSONDecodeError as exc:
            raise ServerConnectionError(
                f"Invalid JSON response from streamable-http endpoint: {exc}"
            ) from exc

        if not isinstance(response_data, dict):
            raise ServerConnectionError(
                "Unexpected non-object JSON response from streamable-http endpoint"
            )

        return response_data

    def _initialize(self, initialize_req_id: int) -> None:
        initialize_payload: dict[str, Any] = {
            "jsonrpc": "2.0",
            "id": initialize_req_id,
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

        initialize_response = requests.post(
            self.endpoint_url,
            json=initialize_payload,
            timeout=30,
            headers=self._build_headers(),
        )
        initialize_response.raise_for_status()
        session_id = initialize_response.headers.get("Mcp-Session-Id")
        if session_id:
            self._session_id = session_id

        initialize_data = self._parse_json_response(initialize_response)
        if "error" in initialize_data:
            raise ServerConnectionError(
                f"Initialize request failed: {initialize_data['error']}"
            )

        initialized_notification: dict[str, Any] = {
            "jsonrpc": "2.0",
            "method": "notifications/initialized",
            "params": {},
        }
        initialized_response = requests.post(
            self.endpoint_url,
            json=initialized_notification,
            timeout=30,
            headers=self._build_headers(),
        )
        initialized_response.raise_for_status()

    def _post_jsonrpc(
        self, method: str, params: dict[str, Any] | None, req_id: int
    ) -> dict[str, Any]:
        self._initialize(initialize_req_id=req_id * 1000 + 1)
        payload = self._build_jsonrpc_payload(method, params, req_id)
        response = requests.post(
            self.endpoint_url,
            json=payload,
            timeout=30,
            headers=self._build_headers(),
        )
        response.raise_for_status()
        return self._parse_json_response(response)

    async def connect_and_execute(
        self, method: str, params: dict[str, Any] | None, req_id: int
    ) -> dict[str, Any]:
        logger.info("Connecting to streamable-http endpoint at %s", self.endpoint_url)
        try:
            return await asyncio.to_thread(self._post_jsonrpc, method, params, req_id)
        except Exception as e:
            logger.exception("Error during streamable-http connection")
            raise ServerConnectionError(
                f"Failed to connect via streamable-http: {e}"
            ) from e


async def _perform_mcp_request(
    session: ClientSession, method: str, params: dict[str, Any] | None
) -> ListToolsResult | CallToolResult:
    """Perform the requested MCP action using the provided session."""
    if method == "list":
        logger.info("Sending ListTools request")
        return await session.list_tools()

    if method == "call":
        if params is None or "tool_name" not in params:
            raise ValueError("Missing 'tool_name' in params for tool call method.")
        tool_name = params["tool_name"]
        tool_args = params.get("tool_arguments")
        logger.info("Sending CallTool request for tool: %s", tool_name)
        return await session.call_tool(name=tool_name, arguments=tool_args)

    raise UnsupportedMethodError(f"Unsupported method for testing: {method}")


def _format_response(
    response_data: ListToolsResult | CallToolResult | dict[str, Any] | None, req_id: int
) -> dict[str, Any]:
    """Format the MCP response as a dictionary."""
    if response_data is None:
        logger.error("No response data received.")
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "error": {
                "code": -32603,
                "message": "Internal error: No response data received from server.",
            },
        }

    if isinstance(response_data, Mapping):
        response_data_json = dict(response_data)
    else:
        response_data_json = response_data.model_dump(mode="json")

    logger.debug("Received response: %s", response_data_json)
    if "jsonrpc" not in response_data_json:
        response_data_json["jsonrpc"] = "2.0"
    if "id" not in response_data_json:
        response_data_json["id"] = req_id
    return response_data_json


def _format_mcp_error(error: McpError, req_id: int) -> dict[str, Any]:
    """Convert an MCP error exception into a JSON-RPC error payload."""
    return {
        "jsonrpc": "2.0",
        "id": req_id,
        "error": error.error.model_dump(mode="json"),
    }


def _create_transport_strategy(
    transport: str,
    server_cmd: str | None = None,
    endpoint_url: str | None = None,
    env: dict[str, str] | None = None,
) -> TransportStrategy:
    """Create transport strategy from transport type."""
    if transport == "stdio":
        if not server_cmd:
            raise ValueError("server_cmd is required for stdio transport")
        return StdioTransport(server_cmd=server_cmd, env=env)
    if transport == "streamable-http":
        if not endpoint_url:
            raise ValueError("endpoint_url is required for streamable-http transport")
        return StreamableHttpTransport(endpoint_url=endpoint_url)
    raise ValueError(f"Unsupported transport type: {transport}")


async def execute_mcp_server(  # noqa: PLR0913
    transport: str,
    method: str,
    params: dict[str, Any] | None = None,
    req_id: int = 1,
    *,
    server_cmd: str | None = None,
    endpoint_url: str | None = None,
    env: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Test an MCP server using configured transport."""
    logger.info("Testing MCP server via %s transport. Method: %s", transport, method)

    try:
        transport_strategy = _create_transport_strategy(
            transport, server_cmd, endpoint_url, env
        )
        return await transport_strategy.connect_and_execute(method, params, req_id)

    except McpError as e:
        err_msg = f"MCP Error during {transport} test for method '{method}': {e!s}"
        logger.exception(err_msg)
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "error": {
                "code": -32000,
                "message": err_msg,
            },
        }

    except Exception as e:
        err_msg = (
            f"Unexpected error during {transport} MCP test for method '{method}': {e}"
        )
        logger.exception(err_msg)
        raise
