"""Models and contracts for MCP server testing."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from openapi_to_mcp.common import OpenApiMcpError


@dataclass(frozen=True, slots=True)
class ConnectionSettings:
    """Connection details for an MCP server test."""

    server_cmd: str | None = None
    endpoint_url: str | None = None
    env: dict[str, str] | None = None


@dataclass(frozen=True, slots=True)
class ServerTestRequest:
    """Describe one MCP request and its connection settings."""

    transport: str
    method: str
    params: dict[str, Any] | None = None
    req_id: int = 1
    connection: ConnectionSettings = field(default_factory=ConnectionSettings)


class UnsupportedMethodError(OpenApiMcpError):
    """Raised when an unsupported MCP method is requested."""


class ServerConnectionError(OpenApiMcpError):
    """Raised when an MCP server connection fails."""


class TransportStrategy:
    """Base contract for MCP testing transports."""

    async def connect_and_execute(
        self, method: str, params: dict[str, Any] | None, req_id: int
    ) -> dict[str, Any]:
        """Connect to the server and execute the requested method."""
        raise NotImplementedError("Subclasses must implement this method")
