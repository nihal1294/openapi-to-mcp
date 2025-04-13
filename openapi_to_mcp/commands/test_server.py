import asyncio
import json
import logging
import sys
from typing import Any

import click

from openapi_to_mcp.adapters.testing import execute_mcp_server
from openapi_to_mcp.common.utils import parse_env_source

logger = logging.getLogger(__name__)


@click.command(name="test-server")
@click.option(
    "--transport",
    required=True,
    type=click.Choice(["sse", "stdio"], case_sensitive=False),
    help="Transport mechanism (sse or stdio).",
)
@click.option("--host", default="localhost", help="Hostname for SSE transport.")
@click.option("--port", type=int, default=8080, help="Port for SSE transport.")
@click.option("--list-tools", is_flag=True, help="Perform a ListTools request.")
@click.option(
    "--server-cmd",
    help="Command to start the server (required for stdio transport). Example: 'node ./build/index.js'",
)
@click.option("--tool-name", help="Name of the tool to call with CallTool.")
@click.option(
    "--tool-args",
    help='JSON string containing the arguments for the tool call. Example: \'{"userId": "123"}\'',
)
@click.option(
    "--env-source",
    help="Environment variables for stdio transport, as JSON string OR path to .json/.env file.",
)
def test_server(
    transport: str,
    host: str,
    port: int,
    *,  # Enforce keyword-only arguments after this
    list_tools: bool = False,
    server_cmd: str | None = None,
    tool_name: str | None = None,
    tool_args: str | None = None,
    env_source: str | None = None,
) -> None:
    """Tests a running MCP server via SSE or Stdio."""

    # Run the async logic within the synchronous Click command
    try:
        asyncio.run(
            _run_test(
                transport,
                host,
                port,
                list_tools=list_tools,
                server_cmd=server_cmd,
                tool_name=tool_name,
                tool_args=tool_args,
                env_source=env_source,
            )
        )
    except Exception as e:
        logger.critical(
            "An unexpected error occurred during testing: %s", e, exc_info=True
        )
        sys.exit(1)


def _parse_tool_args(tool_args: str | None) -> dict[str, Any]:
    """Parses the tool arguments JSON string."""
    if not tool_args:
        return {}
    try:
        tool_arguments = json.loads(tool_args) if tool_args else None
        if not isinstance(tool_arguments, dict):
            raise TypeError("Tool arguments must be a JSON object.")
    except (json.JSONDecodeError, TypeError) as e:
        logger.exception("Invalid JSON in --tool-args")
        click.echo(f"Error: Invalid JSON provided for --tool-args: {e}", err=True)
        raise click.BadParameter(
            f"Tool arguments must be a valid JSON object: {e}"
        ) from e
    else:
        return tool_arguments


async def _run_test(
    transport: str,
    host: str,
    port: int,
    *,  # Enforce keyword-only arguments
    list_tools: bool,
    server_cmd: str | None,
    tool_name: str | None,
    tool_args: str | None,
    env_source: str | None,
) -> None:
    env_vars = parse_env_source(env_source)

    if transport == "stdio" and not server_cmd:
        raise click.UsageError("--server-cmd is required for stdio transport.")
    if tool_name and not tool_args:
        logger.warning(
            "--tool-name provided without --tool-args. Sending empty arguments."
        )
    if tool_args and not tool_name:
        raise click.UsageError("--tool-args requires --tool-name to be specified.")
    if not list_tools and not tool_name:
        raise click.UsageError("Either --list-tools or --tool-name must be specified.")

    response = None
    req_id_counter = 1

    # --- ListTools Request ---
    if list_tools:
        click.echo("--- Sending ListTools Request ---")
        response = await execute_mcp_server(
            transport=transport,
            method="list",
            req_id=req_id_counter,
            server_cmd=server_cmd,
            sse_url=f"http://{host}:{port}" if transport == "sse" else None,
            env=env_vars if transport == "stdio" else None,
        )
        req_id_counter += 1
        click.echo("--- ListTools Response ---")
        click.echo(json.dumps(response, indent=2))
        click.echo("-" * 30)

    # --- CallTool Request ---
    if tool_name:
        click.echo(f"--- Sending CallTool Request for '{tool_name}' ---")
        tool_arguments = _parse_tool_args(tool_args)
        calltool_params = {"tool_name": tool_name, "tool_arguments": tool_arguments}

        response = await execute_mcp_server(
            transport=transport,
            method="call",
            params=calltool_params,
            req_id=req_id_counter,
            server_cmd=server_cmd,
            sse_url=f"http://{host}:{port}" if transport == "sse" else None,
            env=env_vars if transport == "stdio" else None,
        )
        req_id_counter += 1
        click.echo(f"--- CallTool Response for '{tool_name}' ---")
        click.echo(json.dumps(response, indent=2))
        click.echo("-" * 30)
