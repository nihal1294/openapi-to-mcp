"""CLI adapter for MCP project generation."""

from __future__ import annotations

import logging
import sys
from typing import Unpack

import rich_click as click

from openapi_to_mcp.commands.generation_models import (
    GenerateClickOptions,
    GenerationRequest,
    compose_generation_request,
    generation_cli_values,
)
from openapi_to_mcp.commands.generation_service import generate_project
from openapi_to_mcp.commands.options import add_options, generate_options
from openapi_to_mcp.commands.policy_support import load_policy_and_settings
from openapi_to_mcp.common.exceptions import (
    GenerationError,
    MappingError,
    NoToolsMappedError,
    PolicyConfigError,
    SchemaError,
    SpecLoaderError,
)
from openapi_to_mcp.common.terminal import print_success_panel

logger = logging.getLogger(__name__)


def _generation_request(options: GenerateClickOptions) -> GenerationRequest:
    policy, values = load_policy_and_settings(
        generation_cli_values(options), options["config"]
    )
    return compose_generation_request(
        options["openapi_json"], options["output_dir"], values, policy
    )


def _print_success(output_dir: str) -> None:
    print_success_panel(
        "MCP Server Generation Successful",
        [
            f"Files generated in: {output_dir}",
            "Check the generated README for build and runtime instructions.",
        ],
    )


@click.command()
@add_options(generate_options)
def generate(**options: Unpack[GenerateClickOptions]) -> None:
    """Generate a Node.js/TypeScript MCP server from an OpenAPI specification."""
    try:
        generate_project(request=_generation_request(options))
        logger.info("MCP server generation successful.")
        _print_success(options["output_dir"])
    except NoToolsMappedError as error:
        if error.is_error:
            raise click.ClickException(str(error)) from error
        click.echo(str(error))
    except click.ClickException:
        raise
    except (
        SpecLoaderError,
        MappingError,
        GenerationError,
        PolicyConfigError,
        SchemaError,
    ) as error:
        raise click.ClickException(str(error)) from error
    except Exception as error:
        logger.critical(
            "An unexpected critical error occurred: %s", error, exc_info=True
        )
        sys.exit(1)
