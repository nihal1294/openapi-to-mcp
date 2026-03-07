"""Commands component for the openapi-to-mcp package."""

from openapi_to_mcp.commands.generate import generate
from openapi_to_mcp.commands.run import run_server as run
from openapi_to_mcp.commands.test_server import run_test_server as test_server

__all__ = [
    "generate",
    "run",
    "test_server",
]
