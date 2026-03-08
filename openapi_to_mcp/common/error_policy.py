"""Shared error-policy helpers."""

from typing import Literal

ErrorMode = Literal["fail", "skip"]


def resolve_error_mode(mode: ErrorMode | None, *, strict: bool) -> ErrorMode:
    """Resolve an explicit error mode or derive it from strictness."""
    if mode is not None:
        return mode
    return "fail" if strict else "skip"
