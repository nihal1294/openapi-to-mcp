from copy import deepcopy

import pytest

from scripts import release_metadata as metadata
from scripts.release_metadata import (
    metadata_digest,
    validate_evidence,
    validate_release_pr,
)

REPO = "example/project"
HEAD = "a" * 40
BASE = "b" * 40
MERGE = "c" * 40


def release_pr() -> dict:
    return {
        "number": 7,
        "title": "chore(master): release 0.9.2",
        "body": "Release notes",
        "user": {"login": "github-actions[bot]", "type": "Bot"},
        "head": {
            "sha": HEAD,
            "ref": "release-please--branches--master--components--openapi-to-mcp-cli",
            "repo": {"full_name": REPO},
        },
        "base": {"ref": "master", "sha": BASE, "repo": {"full_name": REPO}},
        "merged": True,
        "merge_commit_sha": MERGE,
        "merged_by": {"login": "maintainer", "type": "User"},
    }


def evidence(pr) -> dict:
    return {
        "schema": 1,
        "repository": REPO,
        "pr_number": 7,
        "head_sha": HEAD,
        "base_sha": BASE,
        "version": "0.9.2",
        "tag": "v0.9.2",
        "metadata_digest": metadata_digest(pr),
        "complete": True,
        "baseline_sha": "d" * 40,
    }


def test_human_merged_expected_bot_pr_is_accepted() -> None:
    validate_release_pr(release_pr(), REPO, merge_sha=MERGE)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("user", {"login": "a-human", "type": "User"}),
        ("merged_by", {"login": "automation[bot]", "type": "Bot"}),
        ("merge_commit_sha", "e" * 40),
        ("merged", False),
    ],
)
def test_release_identity_cannot_be_replaced_by_labels(field, value) -> None:
    pr = release_pr()
    pr[field] = value
    with pytest.raises(ValueError, match=r"Release|Publishing"):
        validate_release_pr(pr, REPO, merge_sha=MERGE)


def test_fork_with_matching_release_branch_is_rejected() -> None:
    pr = release_pr()
    pr["head"]["repo"]["full_name"] = "other/project"
    with pytest.raises(ValueError, match=r"Release|Publishing"):
        validate_release_pr(pr, REPO, merge_sha=MERGE)


def test_evidence_is_bound_to_head_base_and_reviewed_metadata() -> None:
    pr = release_pr()
    proof = evidence(pr)
    validate_evidence(proof, pr, REPO, BASE, "0.9.2")
    for key in ("head_sha", "base_sha", "metadata_digest", "version", "repository"):
        changed = deepcopy(proof)
        changed[key] = "wrong"
        with pytest.raises(ValueError, match=r"Release|Publishing"):
            validate_evidence(changed, pr, REPO, BASE, "0.9.2")


def test_changed_release_body_requires_fresh_evidence() -> None:
    pr = release_pr()
    proof = evidence(pr)
    pr["body"] += "\nRelease-As: 1.0.0"
    with pytest.raises(ValueError, match=r"Release|Publishing"):
        validate_evidence(proof, pr, REPO, BASE, "0.9.2")


def test_incomplete_evidence_cannot_authorize_release() -> None:
    pr = release_pr()
    proof = evidence(pr)
    proof["complete"] = False
    with pytest.raises(ValueError, match=r"Release|Publishing"):
        validate_evidence(proof, pr, REPO, BASE, "0.9.2")


def test_release_diff_changes_only_versions_and_notes(monkeypatch) -> None:
    def content(ref, path):
        version = "0.9.1" if ref == "base" else "0.9.2"
        return {
            "pyproject.toml": f'[project]\nname="openapi-to-mcp-cli"\nversion="{version}"\n',
            "uv.lock": f'[[package]]\nname="openapi-to-mcp-cli"\nversion="{version}"\nsource={{editable="."}}\n',
            ".release-please-manifest.json": '{".":"0.9.2"}',
            "CHANGELOG.md": "# Changelog\n\n## [0.9.2](https://example.com)\n\nFixes.",
        }[path]

    monkeypatch.setattr(metadata, "resolve", lambda value: value)
    monkeypatch.setattr(
        metadata, "git", lambda *_args: "\n".join(metadata.RELEASE_FILES)
    )
    monkeypatch.setattr(metadata, "read_at", content)
    assert metadata.validate_release_files("base", "head") == "0.9.2"
    monkeypatch.setattr(
        metadata,
        "read_at",
        lambda ref, path: (
            content(ref, path)
            + (
                '\n[[package]]\nname="unexpected"\nversion="1.0"\n'
                if ref == "head" and path == "uv.lock"
                else ""
            )
        ),
    )
    with pytest.raises(ValueError, match="dependency resolution"):
        metadata.validate_release_files("base", "head")


def test_release_cannot_include_product_or_workflow_edits(monkeypatch) -> None:
    monkeypatch.setattr(metadata, "resolve", lambda value: value)
    monkeypatch.setattr(
        metadata,
        "git",
        lambda *_args: "\n".join(
            metadata.RELEASE_FILES | {".github/workflows/release.yml"}
        ),
    )
    with pytest.raises(ValueError, match="change exactly"):
        metadata.validate_release_files("base", "head")
