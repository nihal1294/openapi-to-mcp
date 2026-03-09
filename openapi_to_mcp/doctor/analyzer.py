"""Spec-readiness diagnostics used by the `doctor` command."""

from __future__ import annotations

from typing import Any

from openapi_to_mcp.doctor.models import DoctorReport
from openapi_to_mcp.mapping.utils import generate_tool_name

_HTTP_METHODS = {"get", "post", "put", "delete", "patch", "options", "head", "trace"}
_SUPPORTED_SECURITY_TYPES = {"apiKey", "oauth2", "openIdConnect"}


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
        operations: list[tuple[str, str, dict[str, Any]]] = []
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
        schemes = self._security_schemes()
        for method, path, operation in operations:
            for scheme_name in self._referenced_security_scheme_names(operation):
                scheme = schemes.get(scheme_name)
                location = f"paths.{path}.{method}.security"
                if not isinstance(scheme, dict):
                    report.add_error(
                        "undefined_security_scheme",
                        f"Security requirement references undefined scheme `{scheme_name}`.",
                        location,
                        "Define the scheme under `components.securitySchemes`.",
                    )
                    continue
                self._check_security_scheme(report, scheme_name, scheme, location)

    def _security_schemes(self) -> dict[str, Any]:
        components = self.spec.get("components", {})
        if not isinstance(components, dict):
            return {}
        schemes = components.get("securitySchemes", {})
        return schemes if isinstance(schemes, dict) else {}

    def _referenced_security_scheme_names(self, operation: dict[str, Any]) -> list[str]:
        source = operation.get("security", self.spec.get("security", []))
        if not isinstance(source, list):
            return []
        names: list[str] = []
        for requirement in source:
            if not isinstance(requirement, dict):
                continue
            names.extend(name for name in requirement if isinstance(name, str))
        return names

    def _check_security_scheme(
        self, report: DoctorReport, name: str, scheme: dict[str, Any], location: str
    ) -> None:
        scheme_type = scheme.get("type")
        if scheme_type in _SUPPORTED_SECURITY_TYPES:
            return
        if scheme_type == "http":
            http_scheme = scheme.get("scheme")
            if isinstance(http_scheme, str) and http_scheme.lower() == "bearer":
                return
            report.add_error(
                "unsupported_http_auth",
                f"Security scheme `{name}` uses unsupported HTTP scheme `{http_scheme}`.",
                location,
                "Use bearer, apiKey, oauth2, or openIdConnect for generated runtime auth.",
            )
            return
        report.add_error(
            "unsupported_security_scheme",
            f"Security scheme `{name}` uses unsupported type `{scheme_type}`.",
            location,
            "Use bearer, apiKey, oauth2, or openIdConnect for generated runtime auth.",
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

    def _contains_union(self, value: object) -> bool:
        if isinstance(value, dict):
            if "oneOf" in value or "anyOf" in value:
                return True
            return any(self._contains_union(item) for item in value.values())
        if isinstance(value, list):
            return any(self._contains_union(item) for item in value)
        return False
