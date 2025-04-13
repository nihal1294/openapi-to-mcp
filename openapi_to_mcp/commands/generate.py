import logging
import sys
from collections.abc import Callable
from typing import Any

import click

from openapi_to_mcp.adapters.generator import Generator
from openapi_to_mcp.adapters.spec_loader import SpecLoader
from openapi_to_mcp.common.exceptions import (
    GenerationError,
    MappingError,
    SpecLoaderError,
)
from openapi_to_mcp.mapping import Mapper

logger = logging.getLogger(__name__)


# Options common to the generate command
generate_options = [
    click.option(
        "--openapi-json",
        "-o",
        required=True,
        help="Path or URL to OpenAPI specification JSON or YAML file.",
    ),
    click.option(
        "--output-dir",
        "-d",
        required=True,
        type=click.Path(file_okay=False, writable=True),
        help="Output directory for generated files.",
    ),
    click.option(
        "--mcp-server-name",
        "-n",
        help="Name for the generated MCP server (uses OpenAPI Spec title if not provided).",
    ),
    click.option(
        "--mcp-server-version",
        "-v",
        help="Version for the generated MCP server (uses OpenAPI Spec version if not provided).",
    ),
    click.option(
        "--transport",
        "-t",
        required=True,
        type=click.Choice(["stdio", "sse"], case_sensitive=False),
        help="Transport mechanism for the generated server.",
    ),
    click.option(
        "--port",
        "-p",
        type=int,
        help="Port for HTTP/SSE transport (required if transport is not stdio).",
    ),
]


def add_options(options: list[click.Option]) -> Callable:
    """Decorator to add a list of click options."""

    def _add_options(func: Callable) -> Callable:
        for option in reversed(options):
            func = option(func)
        return func

    return _add_options


def _determine_server_name(provided_name: str | None, spec_info: dict[str, Any]) -> str:
    """Determines the final server name, using spec title as fallback."""
    if provided_name:
        return provided_name
    spec_title = spec_info.get("title")
    if spec_title:
        logger.info("Using server name from OpenAPI spec info.title: %s", spec_title)
        return spec_title
    default_name = "openapi-mcp-server"
    logger.warning(
        "Server name not provided and not found in spec title. Using default: %s",
        default_name,
    )
    return default_name


def _determine_server_version(
    provided_version: str | None, spec_info: dict[str, Any]
) -> str:
    """Determines the final server version, using spec version as fallback."""
    if provided_version:
        return provided_version
    spec_version = spec_info.get("version")
    if spec_version:
        logger.info(
            "Using server version from OpenAPI spec info.version: %s", spec_version
        )
        return spec_version
    default_version = "1.0.0"
    logger.warning(
        "Server version not provided and not found in spec version. Using default: %s",
        default_version,
    )
    return default_version


def _extract_base_url(spec: dict[str, Any]) -> str:
    """Extracts the base URL from the first server entry, or returns a placeholder."""
    servers_list = spec.get("servers", [])
    default_url = "YOUR_API_BASE_URL_HERE"
    if isinstance(servers_list, list) and servers_list:
        first_server = servers_list[0]
        if isinstance(first_server, dict) and isinstance(first_server.get("url"), str):
            url = first_server["url"]
            logger.info("Using base URL from spec servers[0].url: %s", url)
            return url
        logger.warning(
            "First server object in spec lacks a valid 'url' string. Using placeholder for .env."
        )
    else:
        logger.warning(
            "No 'servers' array found or it's empty in the spec. Using placeholder for .env."
        )
    return default_url


def _prepare_template_context(
    spec: dict[str, Any],
    mcp_server_name: str | None,
    mcp_server_version: str | None,
    transport: str,
    port: int | None,
    mcp_tools: list[dict[str, Any]],
) -> dict[str, Any]:
    """Prepares the context dictionary for Jinja2 rendering."""
    spec_info = spec.get("info", {})
    final_name = _determine_server_name(mcp_server_name, spec_info)
    final_version = _determine_server_version(mcp_server_version, spec_info)
    api_base_url = _extract_base_url(spec)

    return {
        "server_name": final_name,
        "server_version": final_version,
        "transport": transport,
        "port": port,
        "tools": mcp_tools,
        "api_base_url_comment": api_base_url,
        "server_description": spec_info.get("description", ""),
    }


@click.command()
@add_options(generate_options)
def generate(
    openapi_json: str,
    output_dir: str,
    mcp_server_name: str | None,
    mcp_server_version: str | None,
    transport: str,
    port: int | None,
) -> None:
    """Generates a Node.js/TypeScript MCP server from an OpenAPI specification."""
    logger.info(
        "Starting MCP server generation...",
        extra={
            "params": {
                "openapi_source": openapi_json,
                "output_dir": output_dir,
                "name": mcp_server_name,
                "version": mcp_server_version,
                "transport": transport,
                "port": port,
            },
        },
    )

    try:
        logger.info("Loading OpenAPI spec from: %s", openapi_json)
        loader = SpecLoader(source=openapi_json)
        spec = loader.load_and_validate()
        logger.info("OpenAPI spec loaded and validated successfully.")

        # Validate port requirement for SSE transport
        if transport == "sse" and port is None:
            raise click.UsageError(
                "Option '--port'/-p is required when transport is 'sse'."
            )

        logger.info("Mapping OpenAPI paths to MCP tools...")
        mapper = Mapper(spec=spec)
        mcp_tools = mapper.map_tools()
        logger.info("Mapped %d tools.", len(mcp_tools))

        if not mcp_tools:
            logger.warning(
                "No tools were mapped from the OpenAPI spec. Aborting generation.",
            )
            sys.exit(0)

        logger.debug("Preparing template context.")
        template_context = _prepare_template_context(
            spec,
            mcp_server_name,
            mcp_server_version,
            transport,
            port,
            mcp_tools,
        )

        logger.info("Generating files in: %s", output_dir)
        generator = Generator(output_dir=output_dir, context=template_context)
        generator.generate_files()
        logger.info("File generation complete.")

        logger.info("MCP server generation successful.")
        # Use click.echo for user-facing messages that aren't logs
        click.echo("\n" + "=" * 30)
        click.echo("MCP Server Generation Successful!")
        click.echo(f"Files generated in: {output_dir}")
        click.echo(
            "Please check the README file in the output directory for instructions."
        )
        click.echo("=" * 30 + "\n")

    except (SpecLoaderError, MappingError, GenerationError):
        logger.exception("Generation failed")
        sys.exit(1)
    except Exception as e:
        logger.critical("An unexpected critical error occurred: %s", e, exc_info=True)
        sys.exit(1)
