"""Validation helpers for `mcpgen.yaml` policy parsing."""

from __future__ import annotations

from typing import Any

from openapi_to_mcp.common.exceptions import PolicyConfigError


def mapping_value(value: object, field_name: str) -> dict[str, Any]:
    """Return a mapping value or raise a policy validation error."""
    if value is None:
        return {}
    if isinstance(value, dict):
        return value
    raise PolicyConfigError(f"`{field_name}` must be a mapping.")


def optional_string(value: object, field_name: str) -> str | None:
    """Validate an optional non-empty string field."""
    if value is None:
        return None
    if isinstance(value, str) and value:
        return value
    raise PolicyConfigError(f"`{field_name}` must be a non-empty string.")


def optional_choice(value: object, field_name: str, allowed: set[str]) -> str | None:
    """Validate an optional string constrained to an allowed set."""
    text = optional_string(value, field_name)
    if text is None:
        return None
    if text in allowed:
        return text
    allowed_text = ", ".join(sorted(allowed))
    raise PolicyConfigError(f"`{field_name}` must be one of: {allowed_text}.")


def optional_bool(value: object, field_name: str) -> bool | None:
    """Validate an optional boolean field."""
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    raise PolicyConfigError(f"`{field_name}` must be a boolean.")


def optional_int(value: object, field_name: str, *, minimum: int) -> int | None:
    """Validate an optional integer field with a lower bound."""
    if value is None:
        return None
    if isinstance(value, int) and not isinstance(value, bool) and value >= minimum:
        return value
    raise PolicyConfigError(f"`{field_name}` must be an integer >= {minimum}.")


def string_list(value: object, field_name: str) -> list[str]:
    """Validate a list of non-empty strings."""
    if value is None:
        return []
    is_valid = isinstance(value, list) and all(
        isinstance(item, str) and item for item in value
    )
    if is_valid:
        return value
    raise PolicyConfigError(f"`{field_name}` must be a list of non-empty strings.")


def parse_string_mapping(value: object, field_name: str) -> dict[str, str]:
    """Validate a mapping of non-empty strings to non-empty strings."""
    mapping = mapping_value(value, field_name)
    parsed: dict[str, str] = {}
    for key, item in mapping.items():
        if not isinstance(key, str) or not key:
            raise PolicyConfigError(
                f"`{field_name}` must map non-empty strings to non-empty strings."
            )
        if not isinstance(item, str) or not item:
            raise PolicyConfigError(
                f"`{field_name}` must map non-empty strings to non-empty strings."
            )
        parsed[key] = item
    return parsed


def optional_security_list(
    value: object, field_name: str
) -> list[dict[str, Any]] | None:
    """Validate an optional security requirement list."""
    if value is None:
        return None
    if isinstance(value, list) and all(isinstance(item, dict) for item in value):
        return value
    raise PolicyConfigError(f"`{field_name}` must be a list of mappings.")


def optional_scheme_mapping(
    value: object, field_name: str
) -> dict[str, dict[str, Any]] | None:
    """Validate an optional security scheme mapping."""
    if value is None:
        return None
    mapping = mapping_value(value, field_name)
    parsed: dict[str, dict[str, Any]] = {}
    for key, item in mapping.items():
        if not isinstance(key, str) or not key or not isinstance(item, dict):
            raise PolicyConfigError(
                f"`{field_name}` must map scheme names to mappings."
            )
        parsed[key] = item
    return parsed
