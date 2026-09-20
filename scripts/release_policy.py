"""Validate release intent without taking release actions."""

from __future__ import annotations

import re
from typing import Final

IMPACTS: Final = ("none", "patch", "minor", "breaking")
__all__ = ["analyze_changes", "parse_intent", "validate_intent", "validate_version"]
_IMPACT_ORDER: Final = {impact: index for index, impact in enumerate(IMPACTS)}
_CONVENTIONAL_HEADER: Final = re.compile(
    r"^(?P<kind>[a-z]+)(?:\([^)]+\))?(?P<breaking>!)?:\s+\S.*$",
    re.MULTILINE,
)
_RELEASE_AS: Final = re.compile(r"(?im)^\s*release-as\s*:")
_BREAKING_NOTE: Final = re.compile(r"(?im)^\s*breaking[ -]change\s*:")
_MIGRATION_NOTE: Final = re.compile(
    r"(?im)^[ \t]*migration(?:[ \t]+notes?)?[ \t]*:[ \t]*\S"
)
_VERSION: Final = re.compile(r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)$")


def parse_intent(message: str) -> dict[str, object]:
    """Return the highest conventional-commit impact in an effective message."""
    if _RELEASE_AS.search(message):
        raise ValueError("Release-As directives require reviewed release metadata.")
    messages = _effective_messages(message)
    impacts: list[str] = []
    reasons: list[str] = []
    for entry in messages:
        header = _first_header(entry)
        kind = header.group("kind")
        breaking = bool(header.group("breaking")) or bool(_BREAKING_NOTE.search(entry))
        if breaking and not _MIGRATION_NOTE.search("\n".join(messages)):
            raise ValueError("Breaking changes require migration notes.")
        impact = _impact_for_kind(kind, breaking)
        impacts.append(impact)
        reasons.append("breaking change" if breaking else f"{kind} commit")
    return {"impact": _highest(impacts), "reasons": reasons}


def validate_intent(message: str, minimum: str) -> dict[str, object]:
    """Ensure a declared conventional-commit impact meets evidence."""
    _validate_impact(minimum)
    intent = parse_intent(message)
    impact = str(intent["impact"])
    if _IMPACT_ORDER[impact] < _IMPACT_ORDER[minimum]:
        raise ValueError(
            f"Declared impact {impact!r} is below evidence minimum {minimum!r}."
        )
    return {**intent, "minimum": minimum}


def validate_version(
    previous: str,
    current: str,
    impact: str,
    promotion: bool = False,  # noqa: FBT001, FBT002
) -> None:
    """Validate Release Please's proposed version against product policy."""
    _validate_impact(impact)
    before = _parse_version(previous)
    after = _parse_version(current)
    if promotion:
        if before[0] != 0 or after != (1, 0, 0):
            raise ValueError("Promotion must move a pre-1.0 version to 1.0.0.")
        if impact not in {"minor", "breaking"}:
            raise ValueError("Promotion requires minor or breaking release intent.")
        return
    expected = _expected_version(before, impact)
    if after != expected:
        raise ValueError(
            f"Impact {impact!r} requires {'.'.join(map(str, expected))}, not {current}."
        )


def _effective_messages(message: str) -> list[str]:
    lines = message.splitlines()
    begin = [
        index
        for index, line in enumerate(lines)
        if line.strip() == "BEGIN_COMMIT_OVERRIDE"
    ]
    end = [
        index
        for index, line in enumerate(lines)
        if line.strip() == "END_COMMIT_OVERRIDE"
    ]
    if not begin and not end:
        return _split_messages(message)
    if len(begin) != 1 or len(end) != 1 or begin[0] >= end[0] - 1:
        raise ValueError("Malformed BEGIN_COMMIT_OVERRIDE block.")
    return _split_messages("\n".join(lines[begin[0] + 1 : end[0]]).strip())


def _split_messages(message: str) -> list[str]:
    headers = list(_CONVENTIONAL_HEADER.finditer(message))
    if not headers or headers[0].start() != 0:
        raise ValueError("Release intent must begin with a conventional commit header.")
    return [
        message[header.start() : headers[index + 1].start()].strip()
        if index + 1 < len(headers)
        else message[header.start() :].strip()
        for index, header in enumerate(headers)
    ]


def _first_header(message: str) -> re.Match[str]:
    match = _CONVENTIONAL_HEADER.match(message)
    if match is None:
        raise ValueError("Release intent must begin with a conventional commit header.")
    return match


def _impact_for_kind(kind: str, breaking: bool) -> str:  # noqa: FBT001
    if breaking:
        return "breaking"
    if kind in {"fix", "perf", "deps"}:
        return "patch"
    if kind in {"feat", "feature"}:
        return "minor"
    if kind in {"build", "chore", "ci", "docs", "refactor", "style", "test"}:
        return "none"
    raise ValueError(f"Unsupported conventional commit type: {kind!r}.")


def _highest(impacts: list[str]) -> str:
    return max(impacts, key=_IMPACT_ORDER.__getitem__)


def _expected_version(
    version: tuple[int, int, int], impact: str
) -> tuple[int, int, int]:
    major, minor, patch = version
    if impact == "none":
        return version
    if impact == "patch":
        return major, minor, patch + 1
    if impact == "minor" or (impact == "breaking" and major == 0):
        return major, minor + 1, 0
    return major + 1, 0, 0


def _parse_version(value: str) -> tuple[int, int, int]:
    match = _VERSION.fullmatch(value)
    if match is None:
        raise ValueError(f"Expected a stable semantic version, got {value!r}.")
    return tuple(int(component) for component in match.groups())


def _validate_impact(impact: str) -> None:
    if impact not in _IMPACT_ORDER:
        raise ValueError(f"Unknown release impact: {impact!r}.")


try:
    from scripts.release_policy_changes import analyze_changes
except ModuleNotFoundError:
    from release_policy_changes import analyze_changes
