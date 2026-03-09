"""Structured diagnostic models for the `doctor` command."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

Severity = Literal["warning", "error"]


@dataclass(frozen=True)
class DoctorIssue:
    """One actionable diagnostic emitted by the `doctor` command."""

    code: str
    severity: Severity
    message: str
    location: str
    hint: str

    def to_dict(self) -> dict[str, str]:
        """Return a JSON-serializable issue payload."""
        return {
            "code": self.code,
            "severity": self.severity,
            "message": self.message,
            "location": self.location,
            "hint": self.hint,
        }


@dataclass
class DoctorReport:
    """Aggregate diagnostics for one OpenAPI source."""

    source: str
    issues: list[DoctorIssue] = field(default_factory=list)

    def add(self, issue: DoctorIssue) -> None:
        """Append a diagnostic issue to the report."""
        self.issues.append(issue)

    def add_error(self, code: str, message: str, location: str, hint: str) -> None:
        """Append an error diagnostic."""
        self.add(DoctorIssue(code, "error", message, location, hint))

    def add_warning(self, code: str, message: str, location: str, hint: str) -> None:
        """Append a warning diagnostic."""
        self.add(DoctorIssue(code, "warning", message, location, hint))

    def error_count(self) -> int:
        """Return the number of error diagnostics."""
        return sum(1 for issue in self.issues if issue.severity == "error")

    def warning_count(self) -> int:
        """Return the number of warning diagnostics."""
        return sum(1 for issue in self.issues if issue.severity == "warning")

    def exit_code(self) -> int:
        """Return the command exit code for this report."""
        if self.error_count() > 0:
            return 3
        if self.warning_count() > 0:
            return 2
        return 0

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable report."""
        return {
            "source": self.source,
            "errors": self.error_count(),
            "warnings": self.warning_count(),
            "exit_code": self.exit_code(),
            "issues": [issue.to_dict() for issue in self.issues],
        }
