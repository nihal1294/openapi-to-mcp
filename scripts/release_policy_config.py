"""Public Python package metadata checks for release policy."""

from __future__ import annotations

import re
import tomllib
from typing import Any


def project_impacts(before_content: str, after_content: str) -> list[tuple[str, str]]:
    """Return impacts for public project metadata changes."""
    before = _project(before_content)
    after = _project(after_content)
    impacts: list[tuple[str, str]] = []
    if before.get("name") != after.get("name"):
        impacts.append(("breaking", "distribution name changed"))
    if _raised_floor(before.get("requires-python"), after.get("requires-python")):
        impacts.append(("breaking", "Python floor increased"))
    impacts.extend(_script_impacts(before, after))
    if _string_set(before.get("dependencies")) != _string_set(
        after.get("dependencies")
    ):
        impacts.append(("patch", "runtime dependencies changed"))
    return impacts


def _project(content: str) -> dict[str, Any]:
    payload = tomllib.loads(content) if content else {}
    project = payload.get("project")
    return project if isinstance(project, dict) else {}


def _script_impacts(
    before_project: dict[str, Any], after_project: dict[str, Any]
) -> list[tuple[str, str]]:
    before = _mapping(before_project.get("scripts"))
    after = _mapping(after_project.get("scripts"))
    impacts = [
        ("breaking", f"CLI script removed: {name}")
        for name in sorted(set(before) - set(after))
    ]
    impacts.extend(
        ("minor", f"CLI script added: {name}")
        for name in sorted(set(after) - set(before))
    )
    impacts.extend(
        ("breaking", f"CLI script changed: {name}")
        for name in sorted(set(before) & set(after))
        if before[name] != after[name]
    )
    return impacts


def _mapping(value: object) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _string_set(value: object) -> set[str]:
    return (
        set(value)
        if isinstance(value, list) and all(isinstance(item, str) for item in value)
        else set()
    )


def _raised_floor(before: object, after: object) -> bool:
    matcher = re.compile(r">=\s*(\d+(?:\.\d+)*)")
    old = matcher.search(str(before))
    new = matcher.search(str(after))
    return (
        old is not None
        and new is not None
        and tuple(map(int, new.group(1).split(".")))
        > tuple(map(int, old.group(1).split(".")))
    )
