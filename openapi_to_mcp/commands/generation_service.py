"""Generate an MCP server project from one immutable request."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import TYPE_CHECKING, Any

import rich_click as click

from openapi_to_mcp.adapters.generator import Generator
from openapi_to_mcp.adapters.spec_loader import SpecLoader
from openapi_to_mcp.commands.generation_context import build_template_context
from openapi_to_mcp.common.exceptions import NoToolsMappedError
from openapi_to_mcp.common.tool_runtime import (
    build_public_tools,
    build_runtime_tool_registry,
    derive_auth_env_vars,
)
from openapi_to_mcp.mapping import Mapper
from openapi_to_mcp.mapping.tool_grouping import apply_tool_grouping
from openapi_to_mcp.policy import apply_policy

if TYPE_CHECKING:
    from openapi_to_mcp.commands.generation_models import GenerationRequest
    from openapi_to_mcp.policy.models import PolicyConfig

logger = logging.getLogger(__name__)


def _validate_transport(request: GenerationRequest) -> None:
    transport = request.settings.transport
    if transport.kind != "streamable-http":
        return
    if transport.port is None:
        raise click.UsageError(
            "Option '--port'/-p is required when transport is 'streamable-http'."
        )
    if not transport.endpoint.startswith("/"):
        raise click.UsageError("--mcp-endpoint must start with '/'.")


def _raise_if_no_tools(
    tools: list[dict[str, Any]], policy_config: PolicyConfig | None
) -> None:
    if tools:
        return
    if policy_config is not None:
        raise NoToolsMappedError(
            "No tools remain after applying the configured mcpgen policy.",
            is_error=True,
        )
    message = "No tools were mapped from the OpenAPI spec."
    logger.warning("%s Aborting generation.", message)
    raise NoToolsMappedError(message)


def _map_tools(
    spec: dict[str, Any], request: GenerationRequest
) -> tuple[Mapper, list[dict[str, Any]]]:
    behavior = request.settings.behavior
    mapper = Mapper(
        spec=spec,
        strict=behavior.strict,
        on_mapping_error=behavior.on_mapping_error,
        on_schema_error=behavior.on_schema_error,
    )
    tools = apply_policy(mapper.map_tools(), request.policy_config)
    tools = apply_tool_grouping(tools, behavior.tool_grouping)
    logger.info("Mapped %d tools.", len(tools))
    _raise_if_no_tools(tools, request.policy_config)
    return mapper, tools


def _generation_report(
    mapper: Mapper, request: GenerationRequest, mapped_tools: int
) -> dict[str, Any]:
    settings = request.settings
    policy = request.policy_config
    return {
        "strict_mode": settings.behavior.strict,
        "tool_grouping": settings.behavior.tool_grouping,
        "transport": settings.transport.kind,
        "policy_file": str(policy.source_path) if policy is not None else None,
        **mapper.get_report(),
        "mapped_tools": mapped_tools,
    }


def _write_report(request: GenerationRequest, report: dict[str, Any]) -> None:
    report_path = Path(request.output_dir) / "generation_report.json"
    with report_path.open("w", encoding="utf-8") as report_file:
        json.dump(report, report_file, indent=2, sort_keys=True)
        report_file.write("\n")


def _log_request(request: GenerationRequest) -> None:
    settings = request.settings
    logger.info(
        "Starting MCP server generation...",
        extra={
            "params": {
                "openapi_source": request.source,
                "output_dir": request.output_dir,
                "name": settings.identity.name,
                "version": settings.identity.version,
                "transport": settings.transport.kind,
                "tool_grouping": settings.behavior.tool_grouping,
                "host": settings.transport.host,
                "port": settings.transport.port,
                "mcp_endpoint": settings.transport.endpoint,
                "strict": settings.behavior.strict,
                "runtime_validation": settings.behavior.runtime_validation,
                "on_mapping_error": settings.behavior.on_mapping_error,
                "on_schema_error": settings.behavior.on_schema_error,
            }
        },
    )


def generate_project(request: GenerationRequest) -> None:
    """Generate project files and a diagnostic report for one request."""
    _log_request(request)
    logger.info("Loading OpenAPI spec from: %s", request.source)
    spec = SpecLoader(source=request.source).load_and_validate()
    logger.info("OpenAPI spec loaded and validated successfully.")
    _validate_transport(request)
    logger.info("Mapping OpenAPI paths to MCP tools...")
    mapper, tools = _map_tools(spec, request)
    runtime_tools = build_runtime_tool_registry(tools)
    context = build_template_context(
        spec,
        request.settings,
        build_public_tools(tools),
        runtime_tools,
        derive_auth_env_vars(runtime_tools),
    )
    logger.info("Generating files in: %s", request.output_dir)
    Generator(output_dir=request.output_dir, context=context).generate_files()
    _write_report(request, _generation_report(mapper, request, len(tools)))
    logger.info("File generation complete.")
