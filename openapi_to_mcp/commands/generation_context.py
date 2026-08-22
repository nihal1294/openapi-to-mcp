"""Build template context values for generated MCP servers."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from openapi_to_mcp.common.performance_presets import performance_preset_context

if TYPE_CHECKING:
    from openapi_to_mcp.commands.generation_models import GenerationSettings

logger = logging.getLogger(__name__)


def _server_name(provided: str | None, spec_info: dict[str, Any]) -> str:
    if provided:
        return provided
    title = spec_info.get("title")
    if title:
        logger.info("Using server name from OpenAPI spec info.title: %s", title)
        return str(title)
    default = "openapi-mcp-server"
    logger.warning(
        "Server name not provided and not found in spec title. Using default: %s",
        default,
    )
    return default


def _server_version(provided: str | None, spec_info: dict[str, Any]) -> str:
    if provided:
        return provided
    version = spec_info.get("version")
    if version:
        logger.info("Using server version from OpenAPI spec info.version: %s", version)
        return str(version)
    default = "1.0.0"
    logger.warning(
        "Server version not provided and not found in spec version. Using default: %s",
        default,
    )
    return default


def _swagger_base_url(spec: dict[str, Any]) -> str | None:
    host = spec.get("host")
    if not isinstance(host, str) or not host:
        return None
    base_path = spec.get("basePath", "")
    schemes = spec.get("schemes", [])
    scheme = schemes[0] if isinstance(schemes, list) and schemes else "https"
    if not isinstance(base_path, str):
        base_path = ""
    if not isinstance(scheme, str) or not scheme:
        return None
    url = f"{scheme}://{host}{base_path}"
    logger.info("Using base URL from Swagger 2 host/basePath: %s", url)
    return url


def _base_url(spec: dict[str, Any]) -> str:
    servers = spec.get("servers", [])
    if isinstance(servers, list) and servers:
        first_server = servers[0]
        if isinstance(first_server, dict) and isinstance(first_server.get("url"), str):
            url = first_server["url"]
            logger.info("Using base URL from spec servers[0].url: %s", url)
            return url
        logger.warning(
            "First server object in spec lacks a valid 'url' string. Using placeholder for .env."
        )
    swagger_url = _swagger_base_url(spec)
    if swagger_url is not None:
        return swagger_url
    logger.warning(
        "No 'servers' array found and no Swagger 2 host/basePath detected. Using placeholder for .env."
    )
    return "YOUR_API_BASE_URL_HERE"


def build_template_context(
    spec: dict[str, Any],
    settings: GenerationSettings,
    public_tools: list[dict[str, Any]],
    runtime_tools: dict[str, dict[str, Any]],
    auth_env_vars: list[str],
) -> dict[str, Any]:
    """Build the Jinja context consumed by the project generator."""
    spec_info = spec.get("info", {})
    identity = settings.identity
    transport = settings.transport
    behavior = settings.behavior
    return {
        "server_name": _server_name(identity.name, spec_info),
        "server_version": _server_version(identity.version, spec_info),
        "server_description": spec_info.get("description", ""),
        "transport": transport.kind,
        "host": transport.host,
        "port": transport.port,
        "mcp_endpoint": transport.endpoint,
        "strict": behavior.strict,
        "runtime_validation": behavior.runtime_validation,
        "tools": public_tools,
        "runtime_tools": runtime_tools,
        "auth_env_vars": auth_env_vars,
        "api_base_url_comment": _base_url(spec),
        "performance_presets": performance_preset_context(),
    }
