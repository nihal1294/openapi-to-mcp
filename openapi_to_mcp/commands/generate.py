from __future__ import annotations

import json
import logging
import sys
from pathlib import Path
from typing import TYPE_CHECKING, Any

import rich_click as click

from openapi_to_mcp.adapters.generator import Generator
from openapi_to_mcp.adapters.spec_loader import SpecLoader
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
from openapi_to_mcp.common.performance_presets import performance_preset_context
from openapi_to_mcp.common.terminal import print_success_panel
from openapi_to_mcp.common.tool_runtime import (
    build_public_tools,
    build_runtime_tool_registry,
    derive_auth_env_vars,
)
from openapi_to_mcp.mapping import Mapper
from openapi_to_mcp.mapping.tool_grouping import apply_tool_grouping
from openapi_to_mcp.policy import apply_policy

if TYPE_CHECKING:
    from openapi_to_mcp.common.error_policy import ErrorMode
    from openapi_to_mcp.policy.models import PolicyConfig

logger = logging.getLogger(__name__)


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
    host = spec.get("host")
    if isinstance(host, str) and host:
        base_path = spec.get("basePath", "")
        schemes = spec.get("schemes", [])
        scheme = schemes[0] if isinstance(schemes, list) and schemes else "https"
        if not isinstance(base_path, str):
            base_path = ""
        if isinstance(scheme, str) and scheme:
            url = f"{scheme}://{host}{base_path}"
            logger.info("Using base URL from Swagger 2 host/basePath: %s", url)
            return url
    logger.warning(
        "No 'servers' array found and no Swagger 2 host/basePath detected. Using placeholder for .env."
    )
    return default_url


def _prepare_template_context(  # noqa: PLR0913
    spec: dict[str, Any],
    mcp_server_name: str | None,
    mcp_server_version: str | None,
    transport: str,
    host: str,
    port: int | None,
    mcp_endpoint: str,
    *,
    strict: bool,
    runtime_validation: str,
    public_tools: list[dict[str, Any]],
    runtime_tools: dict[str, dict[str, Any]],
    auth_env_vars: list[str],
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
        "host": host,
        "port": port,
        "mcp_endpoint": mcp_endpoint,
        "strict": strict,
        "runtime_validation": runtime_validation,
        "tools": public_tools,
        "runtime_tools": runtime_tools,
        "auth_env_vars": auth_env_vars,
        "api_base_url_comment": api_base_url,
        "performance_presets": performance_preset_context(),
        "server_description": spec_info.get("description", ""),
    }


def _build_generation_report(
    mapper: Mapper,
    *,
    mapped_tools: int,
    strict: bool,
    generation_settings: dict[str, str],
    policy: PolicyConfig | None,
) -> dict[str, Any]:
    """Build generation diagnostics report."""
    mapper_report = mapper.get_report()
    return {
        "strict_mode": strict,
        "tool_grouping": generation_settings["tool_grouping"],
        "transport": generation_settings["transport"],
        "policy_file": str(policy.source_path) if policy is not None else None,
        **mapper_report,
        "mapped_tools": mapped_tools,
    }


def _write_generation_report(output_dir: str, report: dict[str, Any]) -> None:
    """Write generation report JSON to output directory."""
    report_path = Path(output_dir) / "generation_report.json"
    with report_path.open("w", encoding="utf-8") as report_file:
        json.dump(report, report_file, indent=2, sort_keys=True)
        report_file.write("\n")


def _raise_if_no_tools_mapped(
    mcp_tools: list[dict[str, Any]], *, policy_config: PolicyConfig | None
) -> None:
    """Abort generation when the spec does not map to any MCP tools."""
    if mcp_tools:
        return
    if policy_config is not None:
        err_msg = "No tools remain after applying the configured mcpgen policy."
        raise NoToolsMappedError(err_msg, is_error=True)
    err_msg = "No tools were mapped from the OpenAPI spec."
    logger.warning("%s Aborting generation.", err_msg)
    raise NoToolsMappedError(err_msg)


def generate_project(  # noqa: PLR0913
    openapi_json: str,
    output_dir: str,
    mcp_server_name: str | None,
    mcp_server_version: str | None,
    tool_grouping: str,
    transport: str,
    host: str,
    port: int | None,
    mcp_endpoint: str,
    *,
    strict: bool,
    runtime_validation: str,
    on_mapping_error: ErrorMode | None = None,
    on_schema_error: ErrorMode | None = None,
    policy_config: PolicyConfig | None = None,
) -> None:
    logger.info(
        "Starting MCP server generation...",
        extra={
            "params": {
                "openapi_source": openapi_json,
                "output_dir": output_dir,
                "name": mcp_server_name,
                "version": mcp_server_version,
                "transport": transport,
                "tool_grouping": tool_grouping,
                "host": host,
                "port": port,
                "mcp_endpoint": mcp_endpoint,
                "strict": strict,
                "runtime_validation": runtime_validation,
                "on_mapping_error": on_mapping_error,
                "on_schema_error": on_schema_error,
            },
        },
    )

    logger.info("Loading OpenAPI spec from: %s", openapi_json)
    loader = SpecLoader(source=openapi_json)
    spec = loader.load_and_validate()
    logger.info("OpenAPI spec loaded and validated successfully.")

    if transport == "streamable-http":
        if port is None:
            raise click.UsageError(
                "Option '--port'/-p is required when transport is 'streamable-http'."
            )
        if not mcp_endpoint.startswith("/"):
            raise click.UsageError("--mcp-endpoint must start with '/'.")

    logger.info("Mapping OpenAPI paths to MCP tools...")
    mapper = Mapper(
        spec=spec,
        strict=strict,
        on_mapping_error=on_mapping_error,
        on_schema_error=on_schema_error,
    )
    mcp_tools = mapper.map_tools()
    mcp_tools = apply_policy(mcp_tools, policy_config)
    mcp_tools = apply_tool_grouping(mcp_tools, tool_grouping)
    logger.info("Mapped %d tools.", len(mcp_tools))
    _raise_if_no_tools_mapped(mcp_tools, policy_config=policy_config)
    public_tools = build_public_tools(mcp_tools)
    runtime_tools = build_runtime_tool_registry(mcp_tools)

    auth_env_vars = derive_auth_env_vars(runtime_tools)
    logger.debug("Preparing template context.")
    template_context = _prepare_template_context(
        spec=spec,
        mcp_server_name=mcp_server_name,
        mcp_server_version=mcp_server_version,
        transport=transport,
        host=host,
        port=port,
        mcp_endpoint=mcp_endpoint,
        strict=strict,
        runtime_validation=runtime_validation,
        public_tools=public_tools,
        runtime_tools=runtime_tools,
        auth_env_vars=auth_env_vars,
    )

    logger.info("Generating files in: %s", output_dir)
    generator = Generator(output_dir=output_dir, context=template_context)
    generator.generate_files()
    generation_report = _build_generation_report(
        mapper=mapper,
        mapped_tools=len(mcp_tools),
        strict=strict,
        generation_settings={
            "tool_grouping": tool_grouping,
            "transport": transport,
        },
        policy=policy_config,
    )
    _write_generation_report(output_dir=output_dir, report=generation_report)
    logger.info("File generation complete.")


@click.command()
@add_options(generate_options)
def generate(  # noqa: PLR0913
    openapi_json: str,
    config: str | None,
    output_dir: str,
    mcp_server_name: str | None,
    mcp_server_version: str | None,
    tool_grouping: str,
    transport: str,
    host: str,
    port: int | None,
    mcp_endpoint: str,
    *,
    strict: bool,
    runtime_validation: str,
    on_mapping_error: str | None,
    on_schema_error: str | None,
) -> None:
    """Generates a Node.js/TypeScript MCP server from an OpenAPI specification."""
    try:
        policy_config, resolved_settings = load_policy_and_settings(
            {
                "mcp_server_name": mcp_server_name,
                "mcp_server_version": mcp_server_version,
                "tool_grouping": tool_grouping,
                "transport": transport,
                "host": host,
                "port": port,
                "mcp_endpoint": mcp_endpoint,
                "strict": strict,
                "runtime_validation": runtime_validation,
                "on_mapping_error": on_mapping_error,
                "on_schema_error": on_schema_error,
            },
            config,
        )
        generate_project(
            openapi_json=openapi_json,
            output_dir=output_dir,
            mcp_server_name=resolved_settings["mcp_server_name"],
            mcp_server_version=resolved_settings["mcp_server_version"],
            tool_grouping=resolved_settings["tool_grouping"],
            transport=resolved_settings["transport"],
            host=resolved_settings["host"],
            port=resolved_settings["port"],
            mcp_endpoint=resolved_settings["mcp_endpoint"],
            strict=resolved_settings["strict"],
            runtime_validation=resolved_settings["runtime_validation"],
            on_mapping_error=resolved_settings["on_mapping_error"],
            on_schema_error=resolved_settings["on_schema_error"],
            policy_config=policy_config,
        )
        logger.info("MCP server generation successful.")
        print_success_panel(
            "MCP Server Generation Successful",
            [
                f"Files generated in: {output_dir}",
                "Check the generated README for build and runtime instructions.",
            ],
        )
    except NoToolsMappedError as exc:
        if exc.is_error:
            raise click.ClickException(str(exc)) from exc
        click.echo(str(exc))
        return
    except click.ClickException:
        raise
    except (
        SpecLoaderError,
        MappingError,
        GenerationError,
        PolicyConfigError,
        SchemaError,
    ) as exc:
        raise click.ClickException(str(exc)) from exc
    except Exception as e:
        logger.critical("An unexpected critical error occurred: %s", e, exc_info=True)
        sys.exit(1)
