import logging

import click

from openapi_to_mcp.commands import generate, test_server
from openapi_to_mcp.common import configure_logger

logger = logging.getLogger(__name__)


# Define the main group
@click.group()
def cli() -> None:
    """A CLI tool to generate and test MCP servers from OpenAPI specs."""
    configure_logger()


cli.add_command(generate)
cli.add_command(test_server)


if __name__ == "__main__":
    cli()
