"""Analyzer for meaningful MCP-surface diffs between two specs."""

from __future__ import annotations

from typing import Any, Literal

from openapi_to_mcp.diff.models import DiffChange, DiffReport
from openapi_to_mcp.diff.surface import ToolSurface, build_tool_surfaces, canonicalize

ContractCode = Literal[
    "input_schema_changed",
    "output_schema_changed",
    "auth_changed",
]


class DiffAnalyzer:
    """Compare two OpenAPI specs as generated MCP tool surfaces."""

    def __init__(self, before_spec: dict[str, Any], after_spec: dict[str, Any]) -> None:
        """Initialize the diff analyzer with two loaded OpenAPI documents."""
        self.before_spec = before_spec
        self.after_spec = after_spec

    def analyze(self, before_source: str, after_source: str) -> DiffReport:
        """Return a report of meaningful MCP-surface changes."""
        before_tools = build_tool_surfaces(self.before_spec)
        after_tools = build_tool_surfaces(self.after_spec)
        before_by_op = {tool.operation_key: tool for tool in before_tools.values()}
        after_by_op = {tool.operation_key: tool for tool in after_tools.values()}
        report = DiffReport(before_source=before_source, after_source=after_source)

        self._record_removed_tools(report, before_by_op, after_by_op)
        self._record_added_tools(report, before_by_op, after_by_op)
        self._record_changed_tools(report, before_by_op, after_by_op)
        return report

    def _record_removed_tools(
        self,
        report: DiffReport,
        before_by_op: dict[tuple[str, str], ToolSurface],
        after_by_op: dict[tuple[str, str], ToolSurface],
    ) -> None:
        for operation in sorted(before_by_op.keys() - after_by_op.keys()):
            removed = before_by_op[operation]
            report.add(
                DiffChange(
                    code="tool_removed",
                    impact="breaking",
                    message=f"Tool `{removed.name}` was removed.",
                    location=_format_operation(operation),
                    hint="Keep the old operation or add a compatibility alias if clients depend on it.",
                    details={"tool": removed.name},
                )
            )

    def _record_added_tools(
        self,
        report: DiffReport,
        before_by_op: dict[tuple[str, str], ToolSurface],
        after_by_op: dict[tuple[str, str], ToolSurface],
    ) -> None:
        for operation in sorted(after_by_op.keys() - before_by_op.keys()):
            added = after_by_op[operation]
            report.add(
                DiffChange(
                    code="tool_added",
                    impact="non_breaking",
                    message=f"Tool `{added.name}` was added.",
                    location=_format_operation(operation),
                    hint="Review whether downstream docs or allowlists should include the new tool.",
                    details={"tool": added.name},
                )
            )

    def _record_changed_tools(
        self,
        report: DiffReport,
        before_by_op: dict[tuple[str, str], ToolSurface],
        after_by_op: dict[tuple[str, str], ToolSurface],
    ) -> None:
        for operation in sorted(before_by_op.keys() & after_by_op.keys()):
            before = before_by_op[operation]
            after = after_by_op[operation]
            if before.name != after.name:
                report.add(
                    DiffChange(
                        code="tool_renamed",
                        impact="breaking",
                        message=f"Tool `{before.name}` was renamed to `{after.name}`.",
                        location=_format_operation(operation),
                        hint="Keep the old name or add migration guidance for clients.",
                        details={"before_tool": before.name, "after_tool": after.name},
                    )
                )
            self._record_contract_change(
                report, operation, "input_schema_changed", before, after
            )
            self._record_contract_change(
                report, operation, "output_schema_changed", before, after
            )
            self._record_contract_change(
                report, operation, "auth_changed", before, after
            )

    def _record_contract_change(
        self,
        report: DiffReport,
        operation: tuple[str, str],
        code: ContractCode,
        before: ToolSurface,
        after: ToolSurface,
    ) -> None:
        _, _, before_value = _contract_config(code, before)
        message, hint, after_value = _contract_config(code, after)
        if canonicalize(before_value) == canonicalize(after_value):
            return
        report.add(
            DiffChange(
                code=code,
                impact="breaking",
                message=message,
                location=_format_operation(operation),
                hint=hint,
            )
        )


def _auth_contract(surface: ToolSurface) -> dict[str, object]:
    return {
        "security": surface.security,
        "securitySchemes": surface.security_schemes,
    }


def _format_operation(operation: tuple[str, str]) -> str:
    method, path = operation
    return f"{method} {path}"


def _contract_config(
    code: ContractCode,
    surface: ToolSurface,
) -> tuple[str, str, object]:
    if code == "input_schema_changed":
        return (
            "The tool input schema changed.",
            "Review callers because argument compatibility changed.",
            surface.input_schema,
        )
    if code == "output_schema_changed":
        return (
            "The tool output schema changed.",
            "Review consumers because structured output compatibility changed.",
            surface.output_schema,
        )
    if code == "auth_changed":
        return (
            "The tool auth requirements changed.",
            "Review runtime credentials and access expectations for this tool.",
            _auth_contract(surface),
        )
    raise ValueError(f"Unsupported diff contract code: {code}")
