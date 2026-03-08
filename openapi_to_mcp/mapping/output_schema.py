"""Helpers for extracting MCP tool output schemas from OpenAPI responses."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from openapi_to_mcp.common.exceptions import SchemaError
from openapi_to_mcp.schema.converter import openapi_schema_to_json_schema

if TYPE_CHECKING:
    from collections.abc import Callable

_PREFERRED_RESPONSE_CODES = ("200", "201", "202", "203", "206", "207", "208", "226")
_HTTP_STATUS_CODE_LENGTH = 3
logger = logging.getLogger(__name__)


def extract_output_schema(
    operation: dict[str, Any],
    spec: dict[str, Any],
    resolve_ref: Callable[[str], dict[str, Any]],
) -> dict[str, Any] | None:
    """Extract an object-shaped response schema suitable for MCP outputSchema."""
    response = _select_success_response(operation.get("responses"), resolve_ref)
    if not response:
        return None
    schema = _extract_response_schema(response)
    if not schema:
        return None
    try:
        json_schema = openapi_schema_to_json_schema(schema, spec, raise_on_error=True)
    except SchemaError:
        logger.warning(
            "Skipping outputSchema because response schema conversion failed."
        )
        return None
    if not _supports_structured_output(json_schema):
        return None
    return json_schema


def _select_success_response(
    responses_maybe: object,
    resolve_ref: Callable[[str], dict[str, Any]],
) -> dict[str, Any] | None:
    """Select the best available successful response object."""
    if not isinstance(responses_maybe, dict):
        return None
    for status_code in _candidate_response_codes(responses_maybe):
        response = responses_maybe.get(status_code)
        if not isinstance(response, dict):
            continue
        if "$ref" in response and isinstance(response["$ref"], str):
            resolved = resolve_ref(response["$ref"])
            if isinstance(resolved, dict):
                return resolved
            continue
        return response
    return None


def _candidate_response_codes(responses: dict[str, Any]) -> list[str]:
    """Return response codes in preferred selection order."""
    preferred = [code for code in _PREFERRED_RESPONSE_CODES if code in responses]
    remaining = sorted(
        code
        for code in responses
        if isinstance(code, str)
        and code.isdigit()
        and len(code) == _HTTP_STATUS_CODE_LENGTH
        and code.startswith("2")
        and code not in preferred
    )
    wildcard = [code for code in ("2XX", "2xx") if code in responses]
    return preferred + remaining + wildcard


def _extract_response_schema(response: dict[str, Any]) -> dict[str, Any] | None:
    """Extract a JSON response schema from OpenAPI 3 or Swagger 2 responses."""
    content = response.get("content")
    if isinstance(content, dict):
        schema = _extract_openapi_content_schema(content)
        if schema:
            return schema
    schema = response.get("schema")
    return schema if isinstance(schema, dict) else None


def _extract_openapi_content_schema(
    content: dict[str, Any],
) -> dict[str, Any] | None:
    """Prefer JSON-like media types from a response content map."""
    for media_type in _preferred_media_types(content):
        media = content.get(media_type)
        if not isinstance(media, dict):
            continue
        schema = media.get("schema")
        if isinstance(schema, dict):
            return schema
    return None


def _preferred_media_types(content: dict[str, Any]) -> list[str]:
    """Return media types ordered by JSON usefulness."""
    exact = [key for key in ("application/json",) if key in content]
    json_like = sorted(
        key
        for key in content
        if isinstance(key, str) and key not in exact and "json" in key
    )
    return exact + json_like


def _supports_structured_output(schema: dict[str, Any]) -> bool:
    """Return whether the converted schema is suitable for structuredContent."""
    schema_type = schema.get("type")
    if schema_type == "object":
        return True
    if schema_type in {"array", "string", "number", "integer", "boolean"}:
        return False
    return any(key in schema for key in ("properties", "allOf"))
