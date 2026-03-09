"""Spec-readiness diagnostics used by the `doctor` command."""

from __future__ import annotations

from typing import Any

from openapi_to_mcp.doctor.models import DoctorReport
from openapi_to_mcp.doctor.security import (
    check_security_scheme,
    referenced_scheme_names,
    security_schemes,
)
from openapi_to_mcp.mapping.utils import generate_tool_name

_HTTP_METHODS = {"get", "post", "put", "delete", "patch", "options", "head", "trace"}
_MAX_UNION_DEPTH = 20


class DoctorAnalyzer:
    """Analyze an OpenAPI document for MCP-generation readiness."""

    def __init__(self, spec: dict[str, Any]) -> None:
        """Initialize the analyzer with a loaded OpenAPI document."""
        self.spec = spec

    def analyze(self, source: str) -> DoctorReport:
        """Return a diagnostics report for the current spec."""
        report = DoctorReport(source=source)
        self._check_base_url(report)
        operations = list(self._iter_operations())
        if not operations:
            report.add_error(
                "no_http_operations",
                "No HTTP operations were found under `paths`.",
                "paths",
                "Add at least one HTTP operation before generating an MCP server.",
            )
            return report
        self._check_missing_operation_ids(report, operations)
        self._check_generated_name_collisions(report, operations)
        self._check_security(report, operations)
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

    def _iter_operations(self) -> list[tuple[str, str, dict[str, Any]]]:
        paths = self.spec.get("paths", {})
        if not isinstance(paths, dict):
            return []
        operations = []
        for path, path_item in paths.items():
            if not isinstance(path_item, dict):
                continue
            for method, operation in path_item.items():
                if method.lower() not in _HTTP_METHODS or not isinstance(
                    operation, dict
                ):
                    continue
                operations.append((method, path, operation))
        return operations

    def _check_missing_operation_ids(
        self,
        report: DoctorReport,
        operations: list[tuple[str, str, dict[str, Any]]],
    ) -> None:
        for method, path, operation in operations:
            operation_id = operation.get("operationId")
            if isinstance(operation_id, str) and operation_id.strip():
                continue
            report.add_warning(
                "missing_operation_id",
                f"{method.upper()} {path} has no explicit operationId.",
                f"paths.{path}.{method}",
                "Add a stable operationId to avoid generated fallback names.",
            )

    def _check_generated_name_collisions(
        self,
        report: DoctorReport,
        operations: list[tuple[str, str, dict[str, Any]]],
    ) -> None:
        seen: dict[str, str] = {}
        for method, path, operation in operations:
            candidate_name = operation.get("operationId") or generate_tool_name(
                method, path
            )
            if not isinstance(candidate_name, str):
                continue
            location = f"paths.{path}.{method}"
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
        operations: list[tuple[str, str, dict[str, Any]]],
    ) -> None:
        schemes = security_schemes(self.spec)
        self._check_security_requirements(
            report,
            source=self.spec.get("security", []),
            schemes=schemes,
            location="security",
        )
        for method, path, operation in operations:
            security = operation.get("security")
            if security is None:
                continue
            self._check_security_requirements(
                report,
                source=security,
                schemes=schemes,
                location=f"paths.{path}.{method}.security",
            )

    def _check_security_requirements(
        self,
        report: DoctorReport,
        *,
        source: object,
        schemes: dict[str, Any],
        location: str,
    ) -> None:
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
        operations: list[tuple[str, str, dict[str, Any]]],
    ) -> None:
        for method, path, operation in operations:
            location = f"paths.{path}.{method}"
            if self._operation_uses_union_schema(operation):
                report.add_warning(
                    "risky_union_schema",
                    f"{method.upper()} {path} uses `oneOf` or `anyOf` in request or response schemas.",
                    location,
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
