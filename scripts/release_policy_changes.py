"""Repository change analysis for the release-policy guard."""

from __future__ import annotations

import re
import subprocess

try:
    from scripts.release_policy_config import project_impacts
    from scripts.release_policy_lock import runtime_lock_changes
except ModuleNotFoundError:
    from release_policy_config import project_impacts
    from release_policy_lock import runtime_lock_changes

_NODE_FLOOR = re.compile(r'"node"\s*:\s*">=(\d+)"')
_CLI_COMMAND = re.compile(r"cli\.add_command\((\w+)\)")
_MIN_STATUS_COLUMNS = 2
_CUSTOM_TOOL_API = {
    "openapi_to_mcp/templates/src/custom/tools.ts.j2": ("getCustomTools",),
    "openapi_to_mcp/templates/src/runtime/generated.ts.j2": ("CustomToolDefinition",),
}


def analyze_changes(base: str, head: str) -> dict[str, object]:
    """Return the minimum product impact implied by the changed repository files."""
    changes = _changed_paths(base, head)
    impacts: list[str] = []
    reasons: list[str] = []
    _analyze_pyproject(base, head, changes, impacts, reasons)
    _analyze_lock(base, head, changes, impacts, reasons)
    _analyze_cli(base, head, changes, impacts, reasons)
    _analyze_node_floor(base, head, changes, impacts, reasons)
    _analyze_custom_tool_api(base, head, changes, impacts, reasons)
    _analyze_remaining(changes, impacts, reasons)
    return {"minimum": _highest(impacts or ["none"]), "reasons": reasons}


def _highest(impacts: list[str]) -> str:
    order = {"none": 0, "patch": 1, "minor": 2, "breaking": 3}
    return max(impacts, key=order.__getitem__)


def _changed_paths(base: str, head: str) -> dict[str, str]:
    output = _git_output(["diff", "--name-status", base, head])
    changes: dict[str, str] = {}
    for line in output.splitlines():
        parts = line.split("\t")
        if len(parts) < _MIN_STATUS_COLUMNS:
            continue
        status = parts[0][0]
        paths = parts[1:] if status in {"R", "C"} else [parts[1]]
        for path in paths:
            changes[path] = status
    return changes


def _analyze_pyproject(
    base: str,
    head: str,
    changes: dict[str, str],
    impacts: list[str],
    reasons: list[str],
) -> None:
    if "pyproject.toml" not in changes:
        return
    for impact, reason in project_impacts(
        _file_at(base, "pyproject.toml"), _file_at(head, "pyproject.toml")
    ):
        _add(impacts, reasons, impact, reason)


def _analyze_lock(
    base: str,
    head: str,
    changes: dict[str, str],
    impacts: list[str],
    reasons: list[str],
) -> None:
    if "uv.lock" not in changes:
        return
    for name in sorted(
        runtime_lock_changes(_file_at(base, "uv.lock"), _file_at(head, "uv.lock"))
    ):
        _add(impacts, reasons, "patch", f"runtime lock dependency changed: {name}")


def _analyze_cli(
    base: str,
    head: str,
    changes: dict[str, str],
    impacts: list[str],
    reasons: list[str],
) -> None:
    path = "openapi_to_mcp/cli.py"
    if path not in changes:
        return
    before = set(_CLI_COMMAND.findall(_file_at(base, path)))
    after = set(_CLI_COMMAND.findall(_file_at(head, path)))
    for name in sorted(before - after):
        _add(impacts, reasons, "breaking", f"CLI command removed: {name}")
    for name in sorted(after - before):
        _add(impacts, reasons, "minor", f"CLI command added: {name}")
    _add(impacts, reasons, "patch", "CLI implementation changed")


def _analyze_node_floor(
    base: str,
    head: str,
    changes: dict[str, str],
    impacts: list[str],
    reasons: list[str],
) -> None:
    path = "openapi_to_mcp/templates/package.json.j2"
    if path not in changes:
        return
    if changes[path] == "D":
        _add(impacts, reasons, "breaking", "generated runtime package removed")
        return
    before = _node_floor(_file_at(base, path))
    after = _node_floor(_file_at(head, path))
    if before is not None and after is not None and after > before:
        _add(
            impacts,
            reasons,
            "breaking",
            f"generated Node floor increased: {before} to {after}",
        )
    _add(impacts, reasons, "patch", "generated runtime package changed")


def _analyze_custom_tool_api(
    base: str,
    head: str,
    changes: dict[str, str],
    impacts: list[str],
    reasons: list[str],
) -> None:
    for path, symbols in _CUSTOM_TOOL_API.items():
        if path not in changes:
            continue
        before = _file_at(base, path)
        after = _file_at(head, path)
        for symbol in symbols:
            if symbol in before and symbol not in after:
                _add(impacts, reasons, "breaking", f"custom-tool ABI removed: {symbol}")


def _analyze_remaining(
    changes: dict[str, str], impacts: list[str], reasons: list[str]
) -> None:
    handled = {
        "pyproject.toml",
        "uv.lock",
        "openapi_to_mcp/cli.py",
        "openapi_to_mcp/templates/package.json.j2",
    }
    for path, status in changes.items():
        if path in handled or _repository_only(path):
            continue
        if path.startswith("openapi_to_mcp/"):
            impact = "breaking" if status == "D" else "patch"
            reason = (
                "public product file removed"
                if status == "D"
                else "public product code changed"
            )
            _add(impacts, reasons, impact, f"{reason}: {path}")
            continue
        _add(impacts, reasons, "patch", f"unclassified repository change: {path}")


def _file_at(ref: str, path: str) -> str:
    try:
        return _git_output(["show", f"{ref}:{path}"])
    except subprocess.CalledProcessError:
        return ""


def _git_output(arguments: list[str]) -> str:
    return subprocess.check_output(["git", *arguments], text=True)  # noqa: S603, S607


def _repository_only(path: str) -> bool:
    return path.startswith((".github/", "docs/", "tests/", "scripts/")) or path in {
        "CHANGELOG.md",
        "CONTRIBUTING.md",
        "README.md",
        "Justfile",
        "mkdocs.yml",
        "release-please-config.json",
        ".release-please-manifest.json",
        ".gitignore",
        ".pre-commit-config.yaml",
    }


def _node_floor(content: str) -> int | None:
    match = _NODE_FLOOR.search(content)
    return int(match.group(1)) if match else None


def _add(impacts: list[str], reasons: list[str], impact: str, reason: str) -> None:
    impacts.append(impact)
    reasons.append(reason)
