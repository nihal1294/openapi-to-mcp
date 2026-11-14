"""OpenAPI compatibility diagnostics for doctor."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from openapi_to_mcp.common.openapi_compatibility import openapi_operation_findings
from openapi_to_mcp.policy.openapi import is_openapi_operation_selected

if TYPE_CHECKING:
    from openapi_to_mcp.common.operations import OperationRef
    from openapi_to_mcp.doctor.models import DoctorReport
    from openapi_to_mcp.policy.models import PolicyConfig


def report_openapi_compatibility(
    report: DoctorReport,
    spec: dict[str, Any],
    operations: list[OperationRef],
    policy: PolicyConfig | None,
) -> None:
    """Add one diagnostic for each selected unsupported OpenAPI construct."""
    seen = set()
    for operation_ref in operations:
        if not is_openapi_operation_selected(operation_ref, policy):
            continue
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
