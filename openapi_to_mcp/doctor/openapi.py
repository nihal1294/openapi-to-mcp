"""OpenAPI compatibility diagnostics for doctor."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from openapi_to_mcp.common.openapi_compatibility import openapi_operation_findings

if TYPE_CHECKING:
    from openapi_to_mcp.common.operations import OperationRef
    from openapi_to_mcp.doctor.models import DoctorReport


def report_openapi_compatibility(
    report: DoctorReport,
    spec: dict[str, Any],
    operations: list[OperationRef],
) -> None:
    """Add one diagnostic for each unsupported OpenAPI construct."""
    seen = set()
    for operation_ref in operations:
        for finding in openapi_operation_findings(spec, operation_ref):
            if finding in seen:
                continue
            seen.add(finding)
            report.add_error(
                "unsupported_openapi_construct",
                f"OpenAPI `{finding.field}` cannot be faithfully generated.",
                finding.location,
                finding.guidance,
            )
