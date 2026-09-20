"""Determine whether uv lockfile changes reach runtime dependencies."""

from __future__ import annotations

import json
import tomllib
from typing import Any

_ROOT_PACKAGE = "openapi-to-mcp-cli"


def runtime_lock_changes(before_content: str, after_content: str) -> set[str]:
    """Return changed runtime-reachable package names, excluding the root project."""
    before = tomllib.loads(before_content) if before_content else {}
    after = tomllib.loads(after_content) if after_content else {}
    runtime = _runtime_packages(before) | _runtime_packages(after)
    return runtime & (_changed_packages(before, after) - {_ROOT_PACKAGE})


def _runtime_packages(lock: dict[str, Any]) -> set[str]:
    packages = _packages(lock)
    root = packages.get(_ROOT_PACKAGE, {})
    pending = [
        entry["name"] for entry in root.get("dependencies", []) if "name" in entry
    ]
    reachable: set[str] = set()
    while pending:
        name = pending.pop()
        if name in reachable:
            continue
        reachable.add(name)
        pending.extend(
            entry["name"]
            for entry in packages.get(name, {}).get("dependencies", [])
            if "name" in entry
        )
    return reachable


def _changed_packages(before: dict[str, Any], after: dict[str, Any]) -> set[str]:
    old = _packages(before)
    new = _packages(after)
    return {
        name
        for name in set(old) | set(new)
        if json.dumps(old.get(name), sort_keys=True)
        != json.dumps(new.get(name), sort_keys=True)
    }


def _packages(lock: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        package["name"]: package
        for package in lock.get("package", [])
        if isinstance(package, dict) and isinstance(package.get("name"), str)
    }
