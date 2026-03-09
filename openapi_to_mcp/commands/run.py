from __future__ import annotations

from typing import TYPE_CHECKING

import rich_click as click

from openapi_to_mcp.commands.generate import generate_project
from openapi_to_mcp.commands.options import add_options, run_options
from openapi_to_mcp.commands.run_support import (
    ensure_runtime_tools,
    prepare_output_dir,
    prepare_runtime_env,
    run_subprocess,
)
from openapi_to_mcp.commands.runtime_overrides import build_runtime_override_env
from openapi_to_mcp.common.exceptions import (
    GenerationError,
    MappingError,
    NoToolsMappedError,
    SchemaError,
    SpecLoaderError,
)
from openapi_to_mcp.common.terminal import print_section, print_success_panel

if TYPE_CHECKING:
    import tempfile


@click.command(name="run")
@add_options(run_options)
def run_server(  # noqa: PLR0913
    openapi_json: str,
    output_dir: str | None,
    mcp_server_name: str | None,
    mcp_server_version: str | None,
    transport: str,
    host: str,
    port: int | None,
    mcp_endpoint: str,
    *,
    strict: bool,
    runtime_validation: str,
    on_mapping_error: str | None,
    on_schema_error: str | None,
    target_api_base_url: str | None,
    env_source: str | None,
    origin_allowlist: str | None,
    host_allowlist: str | None,
    max_concurrency: int | None,
    per_tool_max_concurrency: int | None,
    max_queue_size: int | None,
    queue_timeout_ms: int | None,
    tool_timeout_ms: int | None,
) -> None:
    """Generate, build, and run an MCP server directly from an OpenAPI spec."""
    temp_dir: tempfile.TemporaryDirectory[str] | None = None

    try:
        ensure_runtime_tools()
        output_path, temp_dir = prepare_output_dir(output_dir)
        print_section(f"Generating MCP server in {output_path}")
        generate_project(
            openapi_json=openapi_json,
            output_dir=str(output_path),
            mcp_server_name=mcp_server_name,
            mcp_server_version=mcp_server_version,
            transport=transport,
            host=host,
            port=port,
            mcp_endpoint=mcp_endpoint,
            strict=strict,
            runtime_validation=runtime_validation,
            on_mapping_error=on_mapping_error,
            on_schema_error=on_schema_error,
        )
        runtime_env = prepare_runtime_env(
            output_path,
            target_api_base_url,
            env_source,
            build_runtime_override_env(
                {
                    "origin_allowlist": origin_allowlist,
                    "host_allowlist": host_allowlist,
                    "max_concurrency": max_concurrency,
                    "per_tool_max_concurrency": per_tool_max_concurrency,
                    "max_queue_size": max_queue_size,
                    "queue_timeout_ms": queue_timeout_ms,
                    "tool_timeout_ms": tool_timeout_ms,
                }
            ),
        )
        print_section("Installing generated server dependencies")
        run_subprocess(["npm", "install"], cwd=output_path, env=runtime_env)
        print_section("Building generated server")
        run_subprocess(["npm", "run", "build"], cwd=output_path, env=runtime_env)
        print_success_panel(
            "Starting generated MCP server",
            [
                f"Working directory: {output_path}",
                "Press Ctrl+C to stop the server.",
            ],
        )
        run_subprocess(["node", "build/index.js"], cwd=output_path, env=runtime_env)
    except click.ClickException:
        raise
    except KeyboardInterrupt:
        raise click.Abort from None
    except (
        GenerationError,
        MappingError,
        NoToolsMappedError,
        SchemaError,
        SpecLoaderError,
        ValueError,
    ) as exc:
        raise click.ClickException(str(exc)) from exc
    finally:
        if temp_dir is not None:
            temp_dir.cleanup()
