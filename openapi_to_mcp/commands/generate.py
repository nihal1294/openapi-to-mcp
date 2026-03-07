from __future__ import annotations

import json
import logging
import sys
from pathlib import Path
from typing import Any

import rich_click as click

from openapi_to_mcp.adapters.generator import Generator
from openapi_to_mcp.adapters.spec_loader import SpecLoader
from openapi_to_mcp.commands.options import add_options, generate_options
from openapi_to_mcp.common.exceptions import (
    GenerationError,
    MappingError,
    SpecLoaderError,
)
from openapi_to_mcp.common.terminal import print_success_panel
from openapi_to_mcp.mapping import Mapper

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
    else:
        logger.warning(
            "No 'servers' array found or it's empty in the spec. Using placeholder for .env."
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
    mcp_tools: list[dict[str, Any]],
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
        "tools": mcp_tools,
        "auth_env_vars": auth_env_vars,
        "api_base_url_comment": api_base_url,
        "server_description": spec_info.get("description", ""),
    }


def _derive_auth_env_vars(mcp_tools: list[dict[str, Any]]) -> list[str]:
    """Collect auth-related env variable names required by mapped tools."""
    env_vars: set[str] = set()
    for tool in mcp_tools:
        security_schemes = tool.get("_original_security_schemes", {})
        if not isinstance(security_schemes, dict):
            continue
        for scheme_name, scheme_def in security_schemes.items():
            if not isinstance(scheme_name, str) or not isinstance(scheme_def, dict):
                continue
            normalized = "".join(
                c if c.isalnum() else "_" for c in scheme_name.upper()
            ).strip("_")
            normalized = "_".join(part for part in normalized.split("_") if part)
            if not normalized:
                continue
            scheme_type = str(scheme_def.get("type", "")).lower()
            http_scheme = str(scheme_def.get("scheme", "")).lower()
            if scheme_type == "apikey":
                env_vars.add(f"AUTH_{normalized}_API_KEY")
            elif (scheme_type == "http" and http_scheme == "bearer") or scheme_type in {
                "oauth2",
                "openidconnect",
            }:
                env_vars.add(f"AUTH_{normalized}_TOKEN")
    return sorted(env_vars)


def _build_generation_report(
    mapper: Mapper, *, strict: bool, transport: str
) -> dict[str, Any]:
    """Build generation diagnostics report."""
    mapper_report = mapper.get_report()
    return {
        "strict_mode": strict,
        "transport": transport,
        "mapped_tools": mapper_report.get("mapped_tools", 0),
        "skipped_operations": mapper_report.get("skipped_operations", []),
        "warnings": mapper_report.get("warnings", []),
    }


def _write_generation_report(output_dir: str, report: dict[str, Any]) -> None:
    """Write generation report JSON to output directory."""
    report_path = Path(output_dir) / "generation_report.json"
    with report_path.open("w", encoding="utf-8") as report_file:
        json.dump(report, report_file, indent=2, sort_keys=True)
        report_file.write("\n")


def generate_project(  # noqa: PLR0913
    openapi_json: str,
    output_dir: str,
    mcp_server_name: str | None,
    mcp_server_version: str | None,
    transport: str,
    host: str,
    port: int | None,
    mcp_endpoint: str,
    *,
    strict: bool,
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
                "host": host,
                "port": port,
                "mcp_endpoint": mcp_endpoint,
                "strict": strict,
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
    mapper = Mapper(spec=spec, strict=strict)
    mcp_tools = mapper.map_tools()
    logger.info("Mapped %d tools.", len(mcp_tools))

    if not mcp_tools:
        logger.warning(
            "No tools were mapped from the OpenAPI spec. Aborting generation.",
        )
        sys.exit(0)

    auth_env_vars = _derive_auth_env_vars(mcp_tools)
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
        mcp_tools=mcp_tools,
        auth_env_vars=auth_env_vars,
    )

    logger.info("Generating files in: %s", output_dir)
    generator = Generator(output_dir=output_dir, context=template_context)
    generator.generate_files()
    generation_report = _build_generation_report(
        mapper=mapper,
        strict=strict,
        transport=transport,
    )
    _write_generation_report(output_dir=output_dir, report=generation_report)
    logger.info("File generation complete.")


@click.command()
@add_options(generate_options)
def generate(  # noqa: PLR0913
    openapi_json: str,
    output_dir: str,
    mcp_server_name: str | None,
    mcp_server_version: str | None,
    transport: str,
    host: str,
    port: int | None,
    mcp_endpoint: str,
    *,
    strict: bool,
) -> None:
    """Generates a Node.js/TypeScript MCP server from an OpenAPI specification."""
    try:
        generate_project(
            openapi_json=openapi_json,
            output_dir=output_dir,
            mcp_server_name=mcp_server_name,
            mcp_server_version=mcp_server_version,
            transport=transport,
            host=host,
            port=port,
            mcp_endpoint=mcp_endpoint,
            strict=strict,
        )
        logger.info("MCP server generation successful.")
        print_success_panel(
            "MCP Server Generation Successful",
            [
                f"Files generated in: {output_dir}",
                "Check the generated README for build and runtime instructions.",
            ],
        )
    except SpecLoaderError, MappingError, GenerationError:
        logger.exception("Generation failed")
        sys.exit(1)
    except Exception as e:
        logger.critical("An unexpected critical error occurred: %s", e, exc_info=True)
        sys.exit(1)
