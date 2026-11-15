"""Spec-readiness diagnostics used by the `doctor` command."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from openapi_to_mcp.common.openapi_compatibility import openapi_operation_findings
from openapi_to_mcp.common.operations import OperationRef, iter_operations
from openapi_to_mcp.common.spec_compatibility import swagger_operation_findings
from openapi_to_mcp.doctor.models import DoctorReport
from openapi_to_mcp.doctor.openapi import report_openapi_compatibility
from openapi_to_mcp.doctor.security import (
    check_security_header_conflicts,
    check_security_scheme,
    referenced_scheme_names,
    security_schemes,
)
from openapi_to_mcp.doctor.swagger import report_swagger_compatibility
from openapi_to_mcp.mapping.security import (
    operation_security,
    operation_security_schemes,
)
from openapi_to_mcp.mapping.utils import generate_tool_name, next_available_tool_name
from openapi_to_mcp.policy.openapi import is_openapi_operation_selected
from openapi_to_mcp.policy.swagger import preview_swagger_findings

if TYPE_CHECKING:
    from openapi_to_mcp.policy.models import PolicyConfig

_MAX_UNION_DEPTH = 20


class DoctorAnalyzer:
    """Analyze an OpenAPI document for MCP-generation readiness."""

    def __init__(
        self, spec: dict[str, Any], policy_config: PolicyConfig | None = None
    ) -> None:
        """Initialize the analyzer with a loaded OpenAPI document."""
        self.spec = spec
        self.policy_config = policy_config

    def analyze(self, source: str) -> DoctorReport:
        """Return a diagnostics report for the current spec."""
        report = DoctorReport(source=source)
        self._check_base_url(report)
        discovered_operations = list(self._iter_operations())
        if not discovered_operations:
            report.add_error(
                "no_http_operations",
                "No HTTP operations were found under `paths`.",
                "paths",
                "Add at least one HTTP operation before generating an MCP server.",
            )
            return report
        operations = self._selected_operations(discovered_operations)
        if not operations:
            report.add_error(
                "no_selected_operations",
                "No HTTP operations remain after applying the configured policy.",
                "paths",
                "Adjust the policy include or exclude selectors to retain at least one HTTP operation.",
            )
            return report
        self._check_missing_operation_ids(report, operations)
        self._check_generated_name_collisions(report, operations)
        self._check_security(report, operations)
        report_swagger_compatibility(
            report,
            self.spec,
            [(item.method, item.path, item.operation) for item in operations],
        )
        report_openapi_compatibility(report, self.spec, operations)
        self._check_schema_unions(report, operations)
        return report

    def _check_base_url(self, report: DoctorReport) -> None:
        servers = self.spec.get("servers")
        if isinstance(servers, list) and any(
            isinstance(item, dict) and isinstance(item.get("url"), str)
            for item in servers
        ):
            return
        host = self.spec.get("host")
        if isinstance(host, str) and host:
            return
        # `basePath` without a host is still not enough for this tool to derive
        # a runnable absolute TARGET_API_BASE_URL, so it remains a warning.
        report.add_warning(
            "missing_base_url",
            "No default base URL was found in `servers[0].url` or Swagger 2 host fields.",
            "servers",
            "`run` will require `--target-api-base-url` or an env override.",
        )

    def _iter_operations(self) -> list[OperationRef]:
        return iter_operations(self.spec)

    def _selected_operations(
        self, operations: list[OperationRef]
    ) -> list[OperationRef]:
        """Return inventory entries retained by the configured policy selectors."""
        original_names = self._allocated_operation_names(operations)
        return [
            operation_ref
            for operation_ref, original_name in zip(
                operations, original_names, strict=True
            )
            if is_openapi_operation_selected(
                operation_ref, self.policy_config, original_name=original_name
            )
        ]

    def _allocated_operation_names(
        self, operations: list[OperationRef]
    ) -> list[str | None]:
        """Return deterministic mapper-equivalent names for policy selection."""
        used_names: set[str] = set()
        name_counts: dict[str, int] = {}
        original_names: list[str | None] = []
        for operation_ref in operations:
            candidate_name = operation_ref.operation.get(
                "operationId"
            ) or generate_tool_name(operation_ref.method, operation_ref.path)
            if not isinstance(candidate_name, str):
                original_names.append(None)
                continue
            if openapi_operation_findings(self.spec, operation_ref):
                # OpenAPI compatibility is checked before name allocation.
                original_names.append(candidate_name)
                continue
            allocated_name = next_available_tool_name(
                candidate_name, used_names, name_counts
            )
            original_names.append(allocated_name)
            findings = swagger_operation_findings(
                self.spec,
                operation_ref.method,
                operation_ref.path,
                operation_ref.path_item,
                operation_ref.operation,
            )
            requirements = operation_security(self.spec, operation_ref.operation)
            tool = {
                "name": allocated_name,
                "_original_method": operation_ref.method,
                "_original_path": operation_ref.path,
                "_original_security": requirements,
                "_original_security_schemes": operation_security_schemes(
                    self.spec, requirements
                ),
            }
            if preview_swagger_findings(findings, tool, self.policy_config):
                # Selected operations with effective findings fail before registration.
                continue
            used_names.add(allocated_name)
            if allocated_name == candidate_name:
                name_counts[candidate_name] = max(name_counts.get(candidate_name, 0), 1)
            else:
                name_counts[candidate_name] = int(
                    allocated_name.removeprefix(f"{candidate_name}_")
                )
        return original_names

    def _check_missing_operation_ids(
        self,
        report: DoctorReport,
        operations: list[OperationRef],
    ) -> None:
        for operation_ref in operations:
            operation_id = operation_ref.operation.get("operationId")
            if isinstance(operation_id, str) and operation_id.strip():
                continue
            report.add_warning(
                "missing_operation_id",
                f"{operation_ref.method} {operation_ref.path} has no explicit operationId.",
                operation_ref.location,
                "Add a stable operationId to avoid generated fallback names.",
            )

    def _check_generated_name_collisions(
        self,
        report: DoctorReport,
        operations: list[OperationRef],
    ) -> None:
        seen: dict[str, str] = {}
        for operation_ref in operations:
            candidate_name = operation_ref.operation.get(
                "operationId"
            ) or generate_tool_name(operation_ref.method, operation_ref.path)
            if not isinstance(candidate_name, str):
                continue
            location = operation_ref.location
            first_location = seen.get(candidate_name)
            if first_location is None:
                seen[candidate_name] = location
                continue
            report.add_error(
                "tool_name_collision",
                f"Generated tool name `{candidate_name}` collides with another operation.",
                location,
                f"Rename one operationId or adjust the path shape. First seen at `{first_location}`.",
            )

    def _check_security(
        self,
        report: DoctorReport,
        operations: list[OperationRef],
    ) -> None:
        schemes = security_schemes(self.spec)
        if any("security" not in item.operation for item in operations):
            self._check_security_requirements(
                report,
                source=self.spec.get("security", []),
                schemes=schemes,
                location="security",
            )
        for operation_ref in operations:
            security = operation_ref.operation.get("security")
            if security is None:
                continue
            self._check_security_requirements(
                report,
                source=security,
                schemes=schemes,
                location=f"{operation_ref.location}.security",
            )

    def _check_security_requirements(
        self,
        report: DoctorReport,
        *,
        source: object,
        schemes: dict[str, Any],
        location: str,
    ) -> None:
        check_security_header_conflicts(
            report,
            source=source,
            schemes=schemes,
            location=location,
        )
        for scheme_name in referenced_scheme_names(source):
            check_security_scheme(
                report,
                name=scheme_name,
                scheme=schemes.get(scheme_name),
                location=location,
            )

    def _check_schema_unions(
        self,
        report: DoctorReport,
        operations: list[OperationRef],
    ) -> None:
        for operation_ref in operations:
            if self._operation_uses_union_schema(operation_ref.operation):
                report.add_warning(
                    "risky_union_schema",
                    f"{operation_ref.method} {operation_ref.path} uses `oneOf` or `anyOf` in request or response schemas.",
                    operation_ref.location,
                    "Generation can proceed, but review the generated input/output contract carefully.",
                )

    def _operation_uses_union_schema(self, operation: dict[str, Any]) -> bool:
        request_body = operation.get("requestBody")
        if isinstance(request_body, dict) and self._contains_union(request_body):
            return True
        responses = operation.get("responses")
        return isinstance(responses, dict) and self._contains_union(responses)

    def _contains_union(self, value: object, *, depth: int = 0) -> bool:
        if depth >= _MAX_UNION_DEPTH:
            return False
        if isinstance(value, dict):
            if "oneOf" in value or "anyOf" in value:
                return True
            return any(
                self._contains_union(item, depth=depth + 1) for item in value.values()
            )
        if isinstance(value, list):
            return any(self._contains_union(item, depth=depth + 1) for item in value)
        return False
