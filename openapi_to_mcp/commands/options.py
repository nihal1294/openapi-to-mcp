"""Shared Click option sets for CLI commands."""

from __future__ import annotations

from typing import TYPE_CHECKING

import rich_click as click

if TYPE_CHECKING:
    from collections.abc import Callable

ERROR_MODE_CHOICE = click.Choice(["fail", "skip"], case_sensitive=False)
RUNTIME_VALIDATION_CHOICE = click.Choice(["none", "input"], case_sensitive=False)


def add_options(options: list[click.Option]) -> Callable:
    """Decorator to apply a sequence of Click option decorators."""

    def _add_options(func: Callable) -> Callable:
        for option in reversed(options):
            func = option(func)
        return func

    return _add_options


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
        default="streamable-http",
        show_default=True,
        type=click.Choice(["stdio", "streamable-http"], case_sensitive=False),
        help="Transport mechanism for the generated server.",
    ),
    click.option(
        "--port",
        "-p",
        type=int,
        default=8080,
        show_default=True,
        help="Port for streamable-http transport.",
    ),
    click.option(
        "--host",
        type=str,
        default="127.0.0.1",
        show_default=True,
        help="Host for streamable-http transport.",
    ),
    click.option(
        "--mcp-endpoint",
        type=str,
        default="/mcp",
        show_default=True,
        help="HTTP endpoint path for MCP streamable-http transport.",
    ),
    click.option(
        "--strict/--no-strict",
        default=True,
        show_default=True,
        help="Strict mode fails generation on unsupported required constructs.",
    ),
    click.option(
        "--on-mapping-error",
        type=ERROR_MODE_CHOICE,
        help="How to handle operation mapping failures. Defaults to fail in strict mode and skip in non-strict mode.",
    ),
    click.option(
        "--on-schema-error",
        type=ERROR_MODE_CHOICE,
        help="How to handle schema conversion failures. Defaults to fail in strict mode and skip in non-strict mode.",
    ),
    click.option(
        "--runtime-validation",
        default="input",
        show_default=True,
        type=RUNTIME_VALIDATION_CHOICE,
        help="Runtime validation applied by the generated server.",
    ),
]


run_options = [
    click.option(
        "--openapi-json",
        "-o",
        required=True,
        help="Path or URL to OpenAPI specification JSON or YAML file.",
    ),
    click.option(
        "--output-dir",
        "-d",
        type=click.Path(file_okay=False, writable=True),
        help="Optional output directory to reuse instead of a temporary workspace.",
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
        default="streamable-http",
        show_default=True,
        type=click.Choice(["stdio", "streamable-http"], case_sensitive=False),
        help="Transport mechanism for the generated server.",
    ),
    click.option(
        "--port",
        "-p",
        type=int,
        default=8080,
        show_default=True,
        help="Port for streamable-http transport.",
    ),
    click.option(
        "--host",
        type=str,
        default="127.0.0.1",
        show_default=True,
        help="Host for streamable-http transport.",
    ),
    click.option(
        "--mcp-endpoint",
        type=str,
        default="/mcp",
        show_default=True,
        help="HTTP endpoint path for MCP streamable-http transport.",
    ),
    click.option(
        "--strict/--no-strict",
        default=True,
        show_default=True,
        help="Strict mode fails generation on unsupported required constructs.",
    ),
    click.option(
        "--on-mapping-error",
        type=ERROR_MODE_CHOICE,
        help="How to handle operation mapping failures. Defaults to fail in strict mode and skip in non-strict mode.",
    ),
    click.option(
        "--on-schema-error",
        type=ERROR_MODE_CHOICE,
        help="How to handle schema conversion failures. Defaults to fail in strict mode and skip in non-strict mode.",
    ),
    click.option(
        "--runtime-validation",
        default="input",
        show_default=True,
        type=RUNTIME_VALIDATION_CHOICE,
        help="Runtime validation applied by the generated server.",
    ),
    click.option(
        "--target-api-base-url",
        help="Override TARGET_API_BASE_URL for the generated runtime.",
    ),
    click.option(
        "--env-source",
        help="Environment variables as a JSON string or path to a JSON/.env file.",
    ),
]
