"""Orchestrate requests across MCP server testing transports."""

from __future__ import annotations

import logging
from typing import Any

from mcp import MCPError

from openapi_to_mcp.adapters.testing.models import (
    ConnectionSettings,
    ServerConnectionError,
    ServerTestRequest,
    TransportStrategy,
    UnsupportedMethodError,
)
from openapi_to_mcp.adapters.testing.response_formatting import (
    format_mcp_error,
    format_mcp_response,
)
from openapi_to_mcp.adapters.testing.stdio_transport import (
    StdioTransport,
    perform_mcp_request,
)
from openapi_to_mcp.adapters.testing.streamable_http_transport import (
    DEFAULT_PROTOCOL_VERSION,
    StreamableHttpTransport,
)

logger = logging.getLogger(__name__)

_format_response = format_mcp_response
_format_mcp_error = format_mcp_error
_perform_mcp_request = perform_mcp_request


def _create_transport_strategy(request: ServerTestRequest) -> TransportStrategy:
    """Create the transport strategy selected by a server test request."""
    connection = request.connection
    if request.transport == "stdio":
        if not connection.server_cmd:
            raise ValueError("server_cmd is required for stdio transport")
        return StdioTransport(connection.server_cmd, connection.env)
    if request.transport == "streamable-http":
        if not connection.endpoint_url:
            raise ValueError("endpoint_url is required for streamable-http transport")
        return StreamableHttpTransport(connection.endpoint_url)
    raise ValueError(f"Unsupported transport type: {request.transport}")


async def execute_mcp_server(request: ServerTestRequest) -> dict[str, Any]:
    """Execute one MCP server test request using its configured transport."""
    logger.info(
        "Testing MCP server via %s transport. Method: %s",
        request.transport,
        request.method,
    )
    try:
        strategy = _create_transport_strategy(request)
        return await strategy.connect_and_execute(
            request.method,
            request.params,
            request.req_id,
        )
    except MCPError as error:
        logger.exception(
            "MCP error during %s test for method '%s'",
            request.transport,
            request.method,
        )
        return format_mcp_error(error, request.req_id)
    except Exception:
        logger.exception(
            "Unexpected error during %s MCP test for method '%s'",
            request.transport,
            request.method,
        )
        raise


__all__ = [
    "DEFAULT_PROTOCOL_VERSION",
    "ConnectionSettings",
    "ServerConnectionError",
    "ServerTestRequest",
    "StdioTransport",
    "StreamableHttpTransport",
    "TransportStrategy",
    "UnsupportedMethodError",
    "execute_mcp_server",
]
