"""Validate the immutable inputs to an automated release."""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
import tomllib
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from pathlib import Path

RELEASE_BRANCH = "release-please--branches--master--components--openapi-to-mcp-cli"
RELEASE_FILES = {
    "pyproject.toml",
    "uv.lock",
    "CHANGELOG.md",
    ".release-please-manifest.json",
}
DISTRIBUTION_COUNT = 2
SHA_PATTERN = re.compile(r"[0-9a-f]{40}\Z")


def git(*args: str) -> str:
    return subprocess.check_output(["git", *args], text=True).strip()  # noqa: S603, S607


def resolve(ref: str) -> str:
    return git("rev-parse", "--verify", "--end-of-options", f"{ref}^{{commit}}")


def read_at(ref: str, path: str) -> str:
    return git("show", f"{resolve(ref)}:{path}")


def project_version(ref: str) -> str:
    return tomllib.loads(read_at(ref, "pyproject.toml"))["project"]["version"]


def metadata_digest(pr: dict[str, Any]) -> str:
    metadata = {key: pr.get(key) for key in ("number", "title", "body")}
    return hashlib.sha256(json.dumps(metadata, sort_keys=True).encode()).hexdigest()


def validate_release_pr(
    pr: dict[str, Any], repository: str, *, merge_sha: str | None = None
) -> None:
    """Require the expected same-repository bot PR, and a human merge if merged."""
    if (
        pr["user"]["login"] != "github-actions[bot]"
        or pr["user"]["type"] != "Bot"
        or pr["head"]["ref"] != RELEASE_BRANCH
        or not pr["head"]["repo"]
        or pr["head"]["repo"]["full_name"] != repository
        or pr["base"]["repo"]["full_name"] != repository
        or pr["base"]["ref"] != "master"
    ):
        raise ValueError("Release must originate from the expected automation PR.")
    if merge_sha is not None and (
        not pr["merged"]
        or pr["merge_commit_sha"] != merge_sha
        or not pr.get("merged_by")
        or pr["merged_by"]["type"] != "User"
    ):
        raise ValueError("Publishing requires a human-merged release PR at this SHA.")


def validate_evidence(
    evidence: dict[str, Any],
    pr: dict[str, Any],
    repository: str,
    parent: str,
    version: str,
) -> None:
    expected = {
        "schema": 1,
        "repository": repository,
        "pr_number": pr["number"],
        "head_sha": pr["head"]["sha"],
        "base_sha": parent,
        "version": version,
        "tag": f"v{version}",
        "metadata_digest": metadata_digest(pr),
        "complete": True,
    }
    for key, value in expected.items():
        if evidence.get(key) != value:
            raise ValueError(f"Release evidence does not match {key}; rerun CI.")
    if not SHA_PATTERN.fullmatch(str(evidence.get("baseline_sha", ""))):
        raise ValueError("Release evidence has no valid published baseline.")


def validate_release_files(base: str, head: str) -> str:
    """Allow only synchronized version edits and release notes."""
    base, head = resolve(base), resolve(head)
    changed = set(git("diff", "--name-only", base, head).splitlines())
    if changed != RELEASE_FILES:
        raise ValueError(f"Release PR must change exactly {sorted(RELEASE_FILES)}.")
    before = tomllib.loads(read_at(base, "pyproject.toml"))
    after = tomllib.loads(read_at(head, "pyproject.toml"))
    previous = before["project"].pop("version")
    version = after["project"].pop("version")
    if (
        before != after
        or version == previous
        or not re.fullmatch(r"\d+\.\d+\.\d+", version)
    ):
        raise ValueError("Release pyproject must contain only a new stable version.")
    if json.loads(read_at(head, ".release-please-manifest.json")) != {".": version}:
        raise ValueError("Release Please manifest must match the package version.")
    old_lock = tomllib.loads(read_at(base, "uv.lock"))
    new_lock = tomllib.loads(read_at(head, "uv.lock"))
    for lock, expected in ((old_lock, previous), (new_lock, version)):
        roots = [p for p in lock["package"] if p["name"] == "openapi-to-mcp-cli"]
        if len(roots) != 1 or roots[0].get("source") != {"editable": "."}:
            raise ValueError("Expected one editable root package in uv.lock.")
        if roots[0].pop("version") != expected:
            raise ValueError("uv.lock root version is not synchronized.")
    if old_lock != new_lock:
        raise ValueError("A release PR must not change dependency resolution.")
    changelog = read_at(head, "CHANGELOG.md")
    heading = next(
        (line for line in changelog.splitlines() if line.startswith("## ")), ""
    )
    if not re.search(rf"(?<!\d){re.escape(version)}(?![\d.])", heading):
        raise ValueError("The first changelog entry must describe the new version.")
    return version


def artifact_hashes(directory: Path) -> dict[str, str]:
    paths = sorted(directory.iterdir())
    if (
        len(paths) != DISTRIBUTION_COUNT
        or not any(p.name.endswith(".whl") for p in paths)
        or not any(p.name.endswith(".tar.gz") for p in paths)
    ):
        raise ValueError("Expected exactly one wheel and one source distribution.")
    return {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
