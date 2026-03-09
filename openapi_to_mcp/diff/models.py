"""Structured models for MCP surface diffs."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

Impact = Literal["breaking", "non_breaking"]
FailMode = Literal["breaking", "none"]


@dataclass(frozen=True)
class DiffChange:
    """One meaningful MCP-surface change between two specs."""

    code: str
    impact: Impact
    message: str
    location: str
    hint: str
    details: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable change payload."""
        return {
            "code": self.code,
            "impact": self.impact,
            "message": self.message,
            "location": self.location,
            "hint": self.hint,
            "details": self.details,
        }


@dataclass
class DiffReport:
    """Aggregate MCP-surface changes between two OpenAPI sources."""

    before_source: str
    after_source: str
    changes: list[DiffChange] = field(default_factory=list)

    def add(self, change: DiffChange) -> None:
        """Append a diff change to the report."""
        self.changes.append(change)

    def breaking_count(self) -> int:
        """Return the number of breaking changes."""
        return sum(1 for change in self.changes if change.impact == "breaking")

    def non_breaking_count(self) -> int:
        """Return the number of non-breaking changes."""
        return sum(1 for change in self.changes if change.impact == "non_breaking")

    def exit_code(self, fail_on: FailMode) -> int:
        """Return the command exit code for the requested fail policy."""
        if fail_on == "breaking" and self.breaking_count() > 0:
            return 2
        return 0

    def to_dict(self, fail_on: FailMode) -> dict[str, Any]:
        """Return a JSON-serializable diff report."""
        return {
            "before_source": self.before_source,
            "after_source": self.after_source,
            "breaking": self.breaking_count(),
            "non_breaking": self.non_breaking_count(),
            "exit_code": self.exit_code(fail_on),
            "changes": [change.to_dict() for change in self.changes],
        }
