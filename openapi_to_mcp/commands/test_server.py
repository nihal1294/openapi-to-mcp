"""CLI command for testing an MCP server."""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any, TypedDict, Unpack

import rich_click as click

from openapi_to_mcp.adapters.testing import (
    ConnectionSettings,
    ServerTestRequest,
    execute_mcp_server,
)
from openapi_to_mcp.common.terminal import print_error, print_json_panel, print_section
from openapi_to_mcp.common.utils import parse_env_source

logger = logging.getLogger(__name__)


class TestServerClickOptions(TypedDict):
    """Typed options supplied by Click to the test-server command."""

    transport: str
    host: str
    port: int
    mcp_endpoint: str
    list_tools: bool
    server_cmd: str | None
    tool_name: str | None
    tool_args: str | None
    env_source: str | None


@click.command(name="test-server")
@click.option(
    "--transport",
    required=True,
    type=click.Choice(["streamable-http", "stdio"], case_sensitive=False),
    help="Transport mechanism (streamable-http or stdio).",
)
@click.option("--host", default="localhost", help="Hostname for streamable-http.")
@click.option("--port", type=int, default=8080, help="Port for streamable-http.")
@click.option(
    "--mcp-endpoint",
    default="/mcp",
    help="HTTP endpoint path for streamable-http transport.",
)
@click.option("--list-tools", is_flag=True, help="Perform a ListTools request.")
@click.option(
    "--server-cmd",
    help="Command to start the server (required for stdio transport).",
)
@click.option("--tool-name", help="Name of the tool to call with CallTool.")
@click.option(
    "--tool-args",
    help="JSON object containing the arguments for the tool call.",
)
@click.option(
    "--env-source",
    help="Environment variables as JSON or a path to a .json/.env file.",
)
def run_test_server(**options: Unpack[TestServerClickOptions]) -> None:
    """Test a running MCP server via streamable HTTP or stdio."""
    try:
        asyncio.run(_run_test(options))
    except click.ClickException:
        raise
    except Exception as error:
        logger.error(  # noqa: TRY400
            "An unexpected error occurred during testing: %s", error
        )
        raise click.ClickException(
            f"Unexpected error during testing: {error}"
        ) from error


def _parse_tool_args(tool_args: str | None) -> dict[str, Any]:
    """Parse tool arguments from a JSON object string."""
    if not tool_args:
        return {}
    try:
        tool_arguments = json.loads(tool_args)
        if not isinstance(tool_arguments, dict):
            raise TypeError("Tool arguments must be a JSON object.")  # noqa: TRY301
    except (json.JSONDecodeError, TypeError) as error:
        logger.exception("Invalid JSON in --tool-args")
        print_error(f"Invalid JSON provided for --tool-args: {error}")
        raise click.BadParameter(
            f"Tool arguments must be a valid JSON object: {error}"
        ) from error
    return tool_arguments


def _validate_options(options: TestServerClickOptions) -> None:
    if options["transport"] == "stdio" and not options["server_cmd"]:
        raise click.UsageError("--server-cmd is required for stdio transport.")
    if options["transport"] == "streamable-http" and not options[
        "mcp_endpoint"
    ].startswith("/"):
        raise click.UsageError("--mcp-endpoint must start with '/'.")
    if options["tool_args"] and not options["tool_name"]:
        raise click.UsageError("--tool-args requires --tool-name to be specified.")
    if not options["list_tools"] and not options["tool_name"]:
        raise click.UsageError("Either --list-tools or --tool-name must be specified.")


def _connection_settings(
    options: TestServerClickOptions, env_vars: dict[str, str] | None
) -> ConnectionSettings:
    endpoint_url = None
    if options["transport"] == "streamable-http":
        endpoint_url = (
            f"http://{options['host']}:{options['port']}{options['mcp_endpoint']}"
        )
    return ConnectionSettings(
        server_cmd=options["server_cmd"],
        endpoint_url=endpoint_url,
        env=env_vars if options["transport"] == "stdio" else None,
    )


async def _run_test(options: TestServerClickOptions) -> None:
    env_vars = parse_env_source(options["env_source"])
    _validate_options(options)
    connection = _connection_settings(options, env_vars)
    req_id = 1
    if options["list_tools"]:
        print_section("Sending tools/list request")
        response = await execute_mcp_server(
            ServerTestRequest(
                transport=options["transport"],
                method="list",
                req_id=req_id,
                connection=connection,
            )
        )
        print_json_panel("tools/list response", response)
        req_id += 1
    if options["tool_name"]:
        if not options["tool_args"]:
            logger.warning(
                "--tool-name provided without --tool-args. Sending empty arguments."
            )
        print_section(f"Sending tools/call request for '{options['tool_name']}'")
        response = await execute_mcp_server(
            ServerTestRequest(
                transport=options["transport"],
                method="call",
                params={
                    "tool_name": options["tool_name"],
                    "tool_arguments": _parse_tool_args(options["tool_args"]),
                },
                req_id=req_id,
                connection=connection,
            )
        )
        print_json_panel(f"tools/call response: {options['tool_name']}", response)
