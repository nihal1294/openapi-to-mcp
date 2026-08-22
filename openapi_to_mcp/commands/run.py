"""CLI adapter for generating and running an MCP server."""

from __future__ import annotations

from typing import TYPE_CHECKING, Unpack

import rich_click as click

from openapi_to_mcp.commands.generate import generate_project
from openapi_to_mcp.commands.generation_models import (
    GenerationRequest,
    RunClickOptions,
    compose_generation_request,
    generation_cli_values,
)
from openapi_to_mcp.commands.options import add_options, run_options
from openapi_to_mcp.commands.policy_support import load_policy_and_settings
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
    PolicyConfigError,
    SchemaError,
    SpecLoaderError,
)
from openapi_to_mcp.common.terminal import print_section, print_success_panel

if TYPE_CHECKING:
    from pathlib import Path


def _generation_request(
    options: RunClickOptions, output_path: Path
) -> GenerationRequest:
    policy, values = load_policy_and_settings(
        generation_cli_values(options), options["config"]
    )
    return compose_generation_request(
        options["openapi_json"], str(output_path), values, policy
    )


def _prepare_runtime(options: RunClickOptions, output_path: Path) -> dict[str, str]:
    return prepare_runtime_env(
        output_path,
        options["target_api_base_url"],
        options["env_source"],
        build_runtime_override_env(options),
    )


def _execute_runtime(output_path: Path, runtime_env: dict[str, str]) -> None:
    print_section("Installing generated server dependencies")
    run_subprocess(["npm", "install"], cwd=output_path, env=runtime_env)
    print_section("Building generated server")
    run_subprocess(["npm", "run", "build"], cwd=output_path, env=runtime_env)
    print_success_panel(
        "Starting generated MCP server",
        [f"Working directory: {output_path}", "Press Ctrl+C to stop the server."],
    )
    run_subprocess(["node", "build/index.js"], cwd=output_path, env=runtime_env)


def _run(options: RunClickOptions) -> None:
    ensure_runtime_tools()
    output_path, temp_dir = prepare_output_dir(options["output_dir"])
    try:
        print_section(f"Generating MCP server in {output_path}")
        generate_project(request=_generation_request(options, output_path))
        _execute_runtime(output_path, _prepare_runtime(options, output_path))
    finally:
        if temp_dir is not None:
            temp_dir.cleanup()


@click.command(name="run")
@add_options(run_options)
def run_server(**options: Unpack[RunClickOptions]) -> None:
    """Generate, build, and run an MCP server directly from an OpenAPI spec."""
    try:
        _run(options)
    except click.ClickException:
        raise
    except KeyboardInterrupt:
        raise click.Abort from None
    except (
        GenerationError,
        MappingError,
        NoToolsMappedError,
        PolicyConfigError,
        SchemaError,
        SpecLoaderError,
        ValueError,
    ) as error:
        raise click.ClickException(str(error)) from error
