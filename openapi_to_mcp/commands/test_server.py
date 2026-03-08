import asyncio
import json
import logging
from typing import Any

import rich_click as click

from openapi_to_mcp.adapters.testing import execute_mcp_server
from openapi_to_mcp.common.terminal import print_error, print_json_panel, print_section
from openapi_to_mcp.common.utils import parse_env_source

logger = logging.getLogger(__name__)


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
def run_test_server(  # noqa: PLR0913
    transport: str,
    host: str,
    port: int,
    mcp_endpoint: str,
    *,  # Enforce keyword-only arguments after this
    list_tools: bool = False,
    server_cmd: str | None = None,
    tool_name: str | None = None,
    tool_args: str | None = None,
    env_source: str | None = None,
) -> None:
    """Tests a running MCP server via streamable-http or stdio."""

    try:
        asyncio.run(
            _run_test(
                transport,
                host,
                port,
                mcp_endpoint,
                list_tools=list_tools,
                server_cmd=server_cmd,
                tool_name=tool_name,
                tool_args=tool_args,
                env_source=env_source,
            )
        )
    except click.ClickException:
        raise
    except Exception as e:
        logger.error(  # noqa: TRY400
            "An unexpected error occurred during testing: %s", e
        )
        raise click.ClickException(f"Unexpected error during testing: {e}") from e


def _parse_tool_args(tool_args: str | None) -> dict[str, Any]:
    """Parses the tool arguments JSON string."""
    if not tool_args:
        return {}
    try:
        tool_arguments = json.loads(tool_args) if tool_args else None
        if not isinstance(tool_arguments, dict):
            raise TypeError("Tool arguments must be a JSON object.")  # noqa: TRY301
    except (json.JSONDecodeError, TypeError) as e:
        logger.exception("Invalid JSON in --tool-args")
        print_error(f"Invalid JSON provided for --tool-args: {e}")
        raise click.BadParameter(
            f"Tool arguments must be a valid JSON object: {e}"
        ) from e
    else:
        return tool_arguments


async def _run_test(  # noqa: PLR0913
    transport: str,
    host: str,
    port: int,
    mcp_endpoint: str,
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
    if transport == "streamable-http" and not mcp_endpoint.startswith("/"):
        raise click.UsageError("--mcp-endpoint must start with '/'.")
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

    endpoint_url = (
        f"http://{host}:{port}{mcp_endpoint}"
        if transport == "streamable-http"
        else None
    )

    if list_tools:
        print_section("Sending tools/list request")
        response = await execute_mcp_server(
            transport=transport,
            method="list",
            req_id=req_id_counter,
            server_cmd=server_cmd,
            endpoint_url=endpoint_url,
            env=env_vars if transport == "stdio" else None,
        )
        req_id_counter += 1
        print_json_panel("tools/list response", response)

    if tool_name:
        print_section(f"Sending tools/call request for '{tool_name}'")
        tool_arguments = _parse_tool_args(tool_args)
        calltool_params = {"tool_name": tool_name, "tool_arguments": tool_arguments}

        response = await execute_mcp_server(
            transport=transport,
            method="call",
            params=calltool_params,
            req_id=req_id_counter,
            server_cmd=server_cmd,
            endpoint_url=endpoint_url,
            env=env_vars if transport == "stdio" else None,
        )
        print_json_panel(f"tools/call response: {tool_name}", response)
