"""Shared inventory of operations declared by an OpenAPI document."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

_FIXED_OPERATION_FIELDS = frozenset(
    {"get", "post", "put", "delete", "patch", "options", "head", "trace"}
)


@dataclass(frozen=True)
class OperationRef:
    """One declared operation together with its source and containing path item."""

    method: str
    path: str
    path_item: dict[str, Any]
    operation: dict[str, Any]
    location: str
    origin: Literal["fixed", "additional"]


def iter_operations(spec: dict[str, Any]) -> list[OperationRef]:
    """Return fixed and OpenAPI 3.2 operation declarations in source order."""
    paths = spec.get("paths", {})
    if not isinstance(paths, dict):
        return []

    operations: list[OperationRef] = []
    supports_openapi_32_operations = _uses_openapi_32_operations(spec)
    for path, path_item in paths.items():
        if not isinstance(path, str) or not isinstance(path_item, dict):
            continue
        operations.extend(
            _path_operations(
                path,
                path_item,
                supports_openapi_32_operations=supports_openapi_32_operations,
            )
        )
    return operations


def _path_operations(
    path: str, path_item: dict[str, Any], *, supports_openapi_32_operations: bool
) -> list[OperationRef]:
    path_location = f"paths.{path}"
    operations: list[OperationRef] = []
    for field, value in path_item.items():
        if _is_fixed_operation(
            field, supports_openapi_32_operations=supports_openapi_32_operations
        ):
            if isinstance(value, dict):
                operations.append(
                    OperationRef(
                        method=field.upper(),
                        path=path,
                        path_item=path_item,
                        operation=value,
                        location=f"{path_location}.{field}",
                        origin="fixed",
                    )
                )
            continue
        if field == "additionalOperations" and supports_openapi_32_operations:
            operations.extend(_additional_operations(path, path_item, value))
    return operations


def _is_fixed_operation(field: str, *, supports_openapi_32_operations: bool) -> bool:
    return field in _FIXED_OPERATION_FIELDS or (
        supports_openapi_32_operations and field == "query"
    )


def _additional_operations(
    path: str, path_item: dict[str, Any], value: object
) -> list[OperationRef]:
    if not isinstance(value, dict):
        return []
    operations: list[OperationRef] = []
    for method, operation in value.items():
        if not isinstance(method, str) or not isinstance(operation, dict):
            continue
        operations.append(
            OperationRef(
                method=method,
                path=path,
                path_item=path_item,
                operation=operation,
                location=f"paths.{path}.additionalOperations.{method}",
                origin="additional",
            )
        )
    return operations


def _uses_openapi_32_operations(spec: dict[str, Any]) -> bool:
    version = spec.get("openapi")
    return isinstance(version, str) and version.startswith("3.2")
