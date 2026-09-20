"""Swagger 2 compatibility diagnostics for doctor."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from openapi_to_mcp.common.spec_compatibility import swagger_operation_findings

if TYPE_CHECKING:
    from openapi_to_mcp.doctor.models import DoctorReport


def report_swagger_compatibility(
    report: DoctorReport,
    spec: dict[str, Any],
    operations: list[tuple[str, str, dict[str, Any]]],
) -> None:
    """Add one diagnostic for each unique unsupported Swagger 2 construct."""
    paths = spec.get("paths", {})
    if not isinstance(paths, dict):
        return
    seen = set()
    for method, path, operation in operations:
        path_item = paths.get(path)
        if not isinstance(path_item, dict):
            continue
        for finding in swagger_operation_findings(
            spec, method, path, path_item, operation
        ):
            if finding in seen:
                continue
            seen.add(finding)
            report.add_error(
                "unsupported_swagger_construct",
                f"Swagger 2 `{finding.field}` cannot be faithfully generated.",
                finding.location,
                "Convert this operation to OpenAPI 3 before generating an MCP server.",
            )
