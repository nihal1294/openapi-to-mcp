"""Stdio transport for MCP server tests."""

from __future__ import annotations

import logging
import shlex
from typing import TYPE_CHECKING, Any

from mcp import ClientSession, MCPError, StdioServerParameters, stdio_client

from openapi_to_mcp.adapters.testing.models import (
    ServerConnectionError,
    TransportStrategy,
    UnsupportedMethodError,
)
from openapi_to_mcp.adapters.testing.response_formatting import (
    format_mcp_error,
    format_mcp_response,
)

if TYPE_CHECKING:
    from mcp.types import CallToolResult, ListToolsResult

logger = logging.getLogger(__name__)


async def perform_mcp_request(
    session: ClientSession, method: str, params: dict[str, Any] | None
) -> ListToolsResult | CallToolResult:
    """Perform one tools/list or tools/call request through a client session."""
    if method == "list":
        logger.info("Sending ListTools request")
        return await session.list_tools()
    if method == "call":
        if params is None or "tool_name" not in params:
            raise ValueError("Missing 'tool_name' in params for tool call method.")
        tool_name = params["tool_name"]
        logger.info("Sending CallTool request for tool: %s", tool_name)
        return await session.call_tool(
            name=tool_name,
            arguments=params.get("tool_arguments"),
        )
    raise UnsupportedMethodError(f"Unsupported method for testing: {method}")


class StdioTransport(TransportStrategy):
    """Execute MCP requests through a managed stdio client session."""

    def __init__(self, server_cmd: str, env: dict[str, str] | None = None) -> None:
        if not server_cmd:
            raise ValueError("server_cmd is required for stdio transport")
        self.server_cmd = server_cmd
        self.env = env

    async def connect_and_execute(
        self, method: str, params: dict[str, Any] | None, req_id: int
    ) -> dict[str, Any]:
        """Connect over stdio and return a JSON-RPC response dictionary."""
        command = shlex.split(self.server_cmd)
        stdio_params = StdioServerParameters(
            command=command[0],
            args=command[1:],
            env=self.env,
        )
        try:
            async with (
                stdio_client(stdio_params) as (read, write),
                ClientSession(read, write) as session,
            ):
                await session.initialize()
                result = await perform_mcp_request(session, method, params)
                return format_mcp_response(result, req_id)
        except MCPError as error:
            logger.info(
                "Received MCP error response over stdio: %s",
                error.message,
            )
            return format_mcp_error(error, req_id)
        except Exception as error:
            logger.exception("Error during stdio connection")
            raise ServerConnectionError(
                f"Failed to connect via stdio: {error}"
            ) from error
