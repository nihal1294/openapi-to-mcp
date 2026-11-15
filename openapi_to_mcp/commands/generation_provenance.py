"""Build the deliberately limited, opt-in generation provenance record."""

from __future__ import annotations

import hashlib
import json
import math
from importlib import metadata
from typing import Any

from openapi_to_mcp.commands.generation_models import (
    GenerationBehavior,
    GenerationSettings,
    ServerIdentity,
    TransportSettings,
)
from openapi_to_mcp.common.error_policy import resolve_error_mode
from openapi_to_mcp.common.exceptions import GenerationError
from openapi_to_mcp.policy.models import (
    ExecutionOverride,
    PolicyConfig,
    SelectorSet,
    ToolAnnotationOverride,
)

_ANNOTATIONS = ("read_only", "destructive", "idempotent", "open_world")
_EXECUTION = (
    "max_concurrency",
    "timeout_ms",
    "max_response_bytes",
    "cache_ttl_ms",
    "rate_limit_per_minute",
    "retry_max_retries",
    "retry_budget_per_minute",
    "circuit_breaker_failure_threshold",
    "circuit_breaker_cooldown_ms",
)
_CAPTURED = ["include", "exclude", "rename", "annotations", "execution"]
_SHA256_HEX_LENGTH = 64
_EXCLUDED = [
    "auth",
    "descriptions",
    "generation_defaults",
    "source_path",
    "unknown_fields",
]


def _invalid() -> GenerationError:
    return GenerationError("Invalid values for generation provenance projection.")


def _validate_json(value: object) -> None:
    if value is None or type(value) in (str, bool, int):
        return
    if type(value) is float and math.isfinite(value):
        return
    if type(value) is list:
        for item in value:
            _validate_json(item)
        return
    if type(value) is dict:
        for key, item in value.items():
            if type(key) is not str:
                raise _invalid()
            _validate_json(item)
        return
    raise _invalid()


def _digest(value: object) -> str:
    _validate_json(value)
    try:
        data = json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        )
        return hashlib.sha256(data.encode("utf-8")).hexdigest()
    except (TypeError, ValueError, UnicodeError) as error:
        raise _invalid() from error


def _selector(value: SelectorSet) -> dict[str, list[str]]:
    if not isinstance(value, SelectorSet):
        raise _invalid()
    result = {}
    for key in ("operations", "names"):
        entries = getattr(value, key)
        if not isinstance(entries, frozenset) or any(
            type(item) is not str for item in entries
        ):
            raise _invalid()
        result[key] = sorted(entries)
    return result


def _mapping(value: object, kind: str) -> dict[str, Any]:
    if not isinstance(value, dict) or any(type(key) is not str for key in value):
        raise _invalid()
    result = {}
    for key, item in value.items():
        if kind == "rename":
            if type(item) is not str:
                raise _invalid()
            result[key] = item
            continue
        cls, fields, expected = (
            (ToolAnnotationOverride, _ANNOTATIONS, bool)
            if kind == "annotations"
            else (ExecutionOverride, _EXECUTION, int)
        )
        if not isinstance(item, cls):
            raise _invalid()
        projected = {field: getattr(item, field) for field in fields}
        if any(v is not None and type(v) is not expected for v in projected.values()):
            raise _invalid()
        result[key] = projected
    return result


def _policy(policy: PolicyConfig | None) -> tuple[dict[str, Any], dict[str, bool]]:
    if policy is not None and not isinstance(policy, PolicyConfig):
        raise _invalid()
    present = policy is not None
    empty = SelectorSet()
    projection: dict[str, Any] = {"present": present}
    presence = {"present": present}
    for name in ("include", "exclude"):
        projection[name] = _selector(getattr(policy, name) if present else empty)
        presence[name] = bool(
            projection[name]["operations"] or projection[name]["names"]
        )
    for name, prefix in (
        ("rename", "rename"),
        ("annotations", "annotation"),
        ("execution", "execution"),
    ):
        projection[name] = {
            side: _mapping(getattr(policy, f"{prefix}_{side}") if present else {}, name)
            for side in ("operations", "names")
        }
        presence[name] = bool(
            projection[name]["operations"] or projection[name]["names"]
        )
    for name, prefix in (("auth", "auth"), ("descriptions", "description")):
        presence[name] = bool(
            present
            and (
                getattr(policy, f"{prefix}_operations")
                or getattr(policy, f"{prefix}_names")
            )
        )
    return projection, presence


def validate_settings_containers(settings: GenerationSettings) -> None:
    """Reject malformed request containers before logging or projection."""
    if not isinstance(settings, GenerationSettings) or not (
        isinstance(settings.identity, ServerIdentity)
        and isinstance(settings.transport, TransportSettings)
        and isinstance(settings.behavior, GenerationBehavior)
    ):
        raise _invalid()


def _options(settings: GenerationSettings) -> dict[str, Any]:
    validate_settings_containers(settings)
    behavior = settings.behavior
    options = {
        "tool_grouping": behavior.tool_grouping,
        "tool_descriptions": behavior.tool_descriptions,
        "tool_name_policy": behavior.tool_name_policy,
        "telemetry": behavior.telemetry,
        "transport": settings.transport.kind,
        "strict": behavior.strict,
        "runtime_validation": behavior.runtime_validation,
        "on_mapping_error": behavior.on_mapping_error,
        "on_schema_error": behavior.on_schema_error,
    }
    choices = {
        "tool_grouping": {"none", "tag-prefix"},
        "tool_descriptions": {"spec", "method"},
        "tool_name_policy": {"preserve", "validate"},
        "telemetry": {"off", "opentelemetry"},
        "transport": {"stdio", "streamable-http"},
        "runtime_validation": {"none", "input"},
    }
    if type(options["strict"]) is not bool:
        raise _invalid()
    for key, allowed in choices.items():
        if type(options[key]) is not str or options[key] not in allowed:
            raise _invalid()
    for key in ("on_mapping_error", "on_schema_error"):
        value = options[key]
        if value is not None and (
            type(value) is not str or value not in {"fail", "skip"}
        ):
            raise _invalid()
        options[key] = resolve_error_mode(value, strict=behavior.strict)
    return options


def build_provenance(
    *,
    source_kind: str,
    spec_digest: str,
    settings: GenerationSettings,
    policy: PolicyConfig | None,
) -> dict[str, Any]:
    """Build a v1 record without exposing source or policy projection values."""
    if (
        type(source_kind) is not str
        or source_kind not in {"file", "url"}
        or type(spec_digest) is not str
        or len(spec_digest) != _SHA256_HEX_LENGTH
        or any(c not in "0123456789abcdef" for c in spec_digest)
    ):
        raise _invalid()
    options = _options(settings)
    projection, presence = _policy(policy)
    try:
        version = metadata.version("openapi-to-mcp-cli")
    except metadata.PackageNotFoundError:
        version = None
    return {
        "schema_version": 1,
        "generator": {"distribution": "openapi-to-mcp-cli", "version": version},
        "spec": {
            "source_kind": source_kind,
            "digest": {
                "algorithm": "sha256",
                "scope": "loaded-top-level-text-utf8",
                "value": spec_digest,
            },
        },
        "resolved_options": options,
        "config_projection_digest": {
            "algorithm": "sha256",
            "scope": "resolved-options-v1",
            "value": _digest(options),
        },
        "policy_projection": presence,
        "policy_digest": {
            "algorithm": "sha256",
            "scope": "non-auth-policy-projection-v1",
            "value": _digest(projection),
            "captured": _CAPTURED,
            "excluded": _EXCLUDED,
        },
    }
