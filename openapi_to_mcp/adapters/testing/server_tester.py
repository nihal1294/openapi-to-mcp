"""Server testing adapter for MCP servers."""

import logging
import shlex
from typing import Any

from mcp import (
    ClientSession,
    ListToolsResult,
    McpError,
    StdioServerParameters,
    stdio_client,
)
from mcp.client.sse import sse_client
from mcp.types import CallToolResult

from openapi_to_mcp.common import OpenApiMcpError

logger = logging.getLogger(__name__)


class UnsupportedMethodError(OpenApiMcpError):
    """Exception raised when an unsupported MCP method is requested."""


class ServerConnectionError(OpenApiMcpError):
    """Exception raised when there's an issue connecting to the MCP server."""


class TransportStrategy:
    """Base class for different transport strategies."""

    async def connect_and_execute(
        self, method: str, params: dict[str, Any] | None, req_id: int
    ) -> dict[str, Any]:
        """
        Connect to the server and execute the requested method.

        Args:
            method: The method name ('list' or 'call')
            params: Parameters for the method
            req_id: Request ID

        Returns:
            Response data as a dictionary

        Raises:
            OpenApiMcpError: If connection or execution fails
        """
        raise NotImplementedError("Subclasses must implement this method")


class StdioTransport(TransportStrategy):
    """Transport strategy for stdio connections."""

    def __init__(self, server_cmd: str, env: dict[str, str] | None = None) -> None:
        """
        Initialize the stdio transport.

        Args:
            server_cmd: Command to start the server process
            env: Optional environment variables for the server process
        """
        if not server_cmd:
            raise ValueError("server_cmd is required for stdio transport")
        self.server_cmd = server_cmd
        self.env = env

    async def connect_and_execute(
        self, method: str, params: dict[str, Any] | None, req_id: int
    ) -> dict[str, Any]:
        """
        Connect to the server via stdio and execute the requested method.

        Args:
            method: The method name ('list' or 'call')
            params: Parameters for the method
            req_id: Request ID

        Returns:
            Response data as a dictionary

        Raises:
            OpenApiMcpError: If connection or execution fails
        """
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
                    response_data = await _perform_mcp_request(session, method, params)
                    logger.info("Received response from MCP server.")
                    return _format_response(response_data, req_id)
        except Exception as e:
            logger.exception("Error during stdio connection")
            raise ServerConnectionError(f"Failed to connect via stdio: {e}") from e


class SseTransport(TransportStrategy):
    """Transport strategy for SSE connections."""

    def __init__(self, sse_url: str) -> None:
        """
        Initialize the SSE transport.

        Args:
            sse_url: Base URL for the SSE server
        """
        if not sse_url:
            raise ValueError("sse_url is required for SSE transport")
        self.sse_url = f"{sse_url}/sse"

    async def connect_and_execute(
        self, method: str, params: dict[str, Any] | None, req_id: int
    ) -> dict[str, Any]:
        """
        Connect to the server via SSE and execute the requested method.

        Args:
            method: The method name ('list' or 'call')
            params: Parameters for the method
            req_id: Request ID

        Returns:
            Response data as a dictionary

        Raises:
            OpenApiMcpError: If connection or execution fails
        """
        logger.info("Connecting to SSE server at %s", self.sse_url)
        try:
            async with sse_client(self.sse_url) as streams:
                logger.info("SSE client connected.")
                async with ClientSession(streams[0], streams[1]) as session:
                    await session.initialize()
                    logger.info("MCP session initialized.")
                    response_data = await _perform_mcp_request(session, method, params)
                    logger.info("Received response from MCP server.")
                    return _format_response(response_data, req_id)
        except Exception as e:
            logger.exception("Error during SSE connection")
            raise ServerConnectionError(f"Failed to connect via SSE: {e}") from e


async def _perform_mcp_request(
    session: ClientSession, method: str, params: dict[str, Any] | None
) -> ListToolsResult | CallToolResult:
    """
    Perform the requested MCP action using the provided session.

    Args:
        session: Active MCP client session
        method: Method name ('list' or 'call')
        params: Parameters for the method

    Returns:
        The result object from the MCP request

    Raises:
        ValueError: If an unsupported method is requested
    """
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

    # Support for test prompts, resources, etc. will be added in the future
    raise UnsupportedMethodError(f"Unsupported method for testing: {method}")


def _format_response(
    response_data: ListToolsResult | CallToolResult | None, req_id: int
) -> dict[str, Any]:
    """
    Format the MCP response as a dictionary.

    Args:
        response_data: The response from the MCP request
        req_id: Request ID

    Returns:
        Dictionary with the formatted response
    """
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

    response_data_json = response_data.model_dump(mode="json")
    logger.debug("Received response: %s", response_data_json)
    if "error" not in response_data_json:
        if "jsonrpc" not in response_data_json:
            response_data_json["jsonrpc"] = "2.0"
        if "id" not in response_data_json:
            response_data_json["id"] = req_id
    return response_data_json


def _create_transport_strategy(
    transport: str,
    server_cmd: str | None = None,
    sse_url: str | None = None,
    env: dict[str, str] | None = None,
) -> TransportStrategy:
    """
    Create the appropriate transport strategy based on the transport type.

    Args:
        transport: The transport type ('stdio' or 'sse')
        server_cmd: Command to start the server process (required for stdio)
        sse_url: Base URL for the SSE server (required for sse)
        env: Optional environment variables for the server process

    Returns:
        The appropriate transport strategy

    Raises:
        ValueError: If required parameters for the transport are missing
    """
    if transport == "stdio":
        if not server_cmd:
            raise ValueError("server_cmd is required for stdio transport")
        return StdioTransport(server_cmd=server_cmd, env=env)
    if transport == "sse":
        if not sse_url:
            raise ValueError("sse_url is required for sse transport")
        return SseTransport(sse_url=sse_url)
    raise ValueError(f"Unsupported transport type: {transport}")


async def execute_mcp_server(
    transport: str,
    method: str,
    params: dict[str, Any] | None = None,
    req_id: int = 1,
    *,
    server_cmd: str | None = None,
    sse_url: str | None = None,
    env: dict[str, str] | None = None,
) -> dict[str, Any]:
    """
    Test an MCP server using the Python SDK.

    Connects via the specified transport, sends a request, and returns the response
    or a JSON-RPC error dictionary.

    Args:
        transport: 'stdio' or 'sse'
        method: The method name ('list' or 'call')
        params: Optional parameters for the method
        req_id: Request ID
        server_cmd: Command to start the server (for stdio)
        sse_url: Base URL for the SSE server (for sse)
        env: Optional dictionary of environment variables for stdio transport

    Returns:
        The parsed JSON-RPC response dictionary from the server, or a
        JSON-RPC error dictionary if an error occurs

    Raises:
        ValueError: If required transport arguments are missing
    """
    logger.info("Testing MCP server via %s transport. Method: %s", transport, method)

    try:
        transport_strategy = _create_transport_strategy(
            transport, server_cmd, sse_url, env
        )
        return await transport_strategy.connect_and_execute(method, params, req_id)

    except McpError as e:
        err_msg = f"MCP Error during {transport} test for method '{method}': {e!s}"
        logger.exception(err_msg)
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "error": {
                "code": -32000,  # Generic server error code
                "message": err_msg,
            },
        }

    except Exception as e:
        err_msg = (
            f"Unexpected error during {transport} MCP test for method '{method}': {e}"
        )
        logger.exception(err_msg)
        raise
