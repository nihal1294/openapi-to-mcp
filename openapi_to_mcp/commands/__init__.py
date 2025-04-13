"""Commands component for the openapi-to-mcp package."""

from openapi_to_mcp.commands.generate import generate
from openapi_to_mcp.commands.test_server import test_server

__all__ = [
    "generate",
    "test_server",
]
