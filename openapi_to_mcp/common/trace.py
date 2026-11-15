"""Associate mapped tools with their original operation trace rows."""

from typing import Any


def trace_row(
    trace: list[dict[str, Any]] | None, tool: dict[str, Any]
) -> dict[str, Any] | None:
    """Return the row identified at mapping time, if tracing is enabled."""
    if trace is None:
        return None
    return trace[tool["_trace_index"]]
