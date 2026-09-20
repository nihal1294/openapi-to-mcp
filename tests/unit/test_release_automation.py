from __future__ import annotations

import io
import json
from copy import deepcopy

import pytest

from scripts import release_automation as automation
from tests.unit.test_release_metadata import MERGE, REPO, release_pr


def test_override_must_be_complete_and_unique() -> None:
    with pytest.raises(ValueError, match="complete"):
        automation.override_message(
            "fix: message", "BEGIN_COMMIT_OVERRIDE\nfix: changed"
        )
    assert (
        automation.override_message(
            "old", "BEGIN_COMMIT_OVERRIDE\nfix: corrected\nEND_COMMIT_OVERRIDE"
        )
        == "fix: corrected"
    )


def test_pending_release_stops_the_next_proposal(monkeypatch) -> None:
    monkeypatch.setattr(
        automation, "pages", lambda *_args: [{"number": 7, "pull_request": {}}]
    )
    monkeypatch.setattr(
        automation, "api", lambda *_args, **_kwargs: {"merged": True, "number": 7}
    )
    outputs = []
    monkeypatch.setattr(automation, "output", lambda **values: outputs.append(values))
    automation.preflight(REPO)
    assert outputs == [{"ready": False}]


def test_unclassified_legacy_product_change_is_not_silently_skipped(
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        automation,
        "git",
        lambda *_args: "a" * 40 if _args[0] == "rev-list" else "Update dependencies",
    )
    monkeypatch.setattr(automation, "api", lambda *_args, **_kwargs: [])
    monkeypatch.setattr(automation, "resolve", lambda value: value)
    monkeypatch.setattr(
        automation, "analyze_changes", lambda *_args: {"minimum": "patch"}
    )
    with pytest.raises(ValueError, match="Classify merged PR"):
        automation.release_range(REPO, "base", "head")


def test_legacy_non_releasing_maintenance_can_be_ignored(monkeypatch) -> None:
    monkeypatch.setattr(
        automation,
        "git",
        lambda *_args: "a" * 40 if _args[0] == "rev-list" else "Update docs",
    )
    monkeypatch.setattr(automation, "api", lambda *_args, **_kwargs: [])
    monkeypatch.setattr(automation, "resolve", lambda value: value)
    monkeypatch.setattr(
        automation, "analyze_changes", lambda *_args: {"minimum": "none"}
    )
    assert automation.release_range(REPO, "base", "head")["impact"] == "none"


def test_malformed_breaking_maintenance_is_not_ignored(monkeypatch) -> None:
    monkeypatch.setattr(
        automation,
        "git",
        lambda *_args: (
            "a" * 40 if _args[0] == "rev-list" else "feat!: changed defaults"
        ),
    )
    monkeypatch.setattr(automation, "api", lambda *_args, **_kwargs: [])
    monkeypatch.setattr(automation, "resolve", lambda value: value)
    monkeypatch.setattr(
        automation, "analyze_changes", lambda *_args: {"minimum": "none"}
    )
    with pytest.raises(ValueError, match="Classify merged PR"):
        automation.release_range(REPO, "base", "head")


def test_pypi_verification_requires_exact_original_distributions(monkeypatch) -> None:
    payload = {"urls": [{"filename": "project.whl", "digests": {"sha256": "abc"}}]}
    monkeypatch.setattr(
        automation.urllib.request,
        "urlopen",
        lambda *_args, **_kwargs: io.BytesIO(json.dumps(payload).encode()),
    )
    automation.verify_pypi("0.9.2", {"project.whl": "abc"})
    with pytest.raises(ValueError, match="original artifacts"):
        automation.verify_pypi("0.9.2", {"project.whl": "different"})


def _finalizer_api(pr, mutations, *, wrong_tag=False):
    def fake(path, *, method="GET", body=None):
        if method != "GET":
            mutations.append((path, method, body))
            return None
        if "/pulls/" in path:
            return deepcopy(pr)
        if "/git/ref/" in path:
            return {
                "object": {"type": "commit", "sha": "wrong" if wrong_tag else MERGE}
            }
        return {
            "draft": False,
            "prerelease": False,
            "assets": [{"name": "project.whl", "digest": "sha256:abc"}],
        }

    return fake


def test_finalizer_updates_labels_only_after_publication_verifies(
    monkeypatch, tmp_path
) -> None:
    pr = release_pr()
    pr["labels"] = [{"name": "autorelease: pending"}]
    mutations = []
    monkeypatch.setattr(automation, "api", _finalizer_api(pr, mutations))
    monkeypatch.setattr(
        automation, "artifact_hashes", lambda *_args: {"project.whl": "abc"}
    )
    monkeypatch.setattr(automation, "verify_pypi", lambda *_args: None)
    automation.finalize(REPO, 7, MERGE, "0.9.2", tmp_path)
    assert [entry[1] for entry in mutations] == ["POST", "DELETE"]
    assert mutations[0][2] == {"labels": ["autorelease: tagged"]}


def test_failed_publication_leaves_pending_intact(monkeypatch, tmp_path) -> None:
    pr = release_pr()
    pr["labels"] = [{"name": "autorelease: pending"}]
    mutations = []
    monkeypatch.setattr(
        automation, "api", _finalizer_api(pr, mutations, wrong_tag=True)
    )
    monkeypatch.setattr(
        automation, "artifact_hashes", lambda *_args: {"project.whl": "abc"}
    )
    monkeypatch.setattr(automation, "verify_pypi", lambda *_args: None)
    with pytest.raises(ValueError, match="authorized merge SHA"):
        automation.finalize(REPO, 7, MERGE, "0.9.2", tmp_path)
    assert mutations == []


def test_finalizer_retry_does_not_publish_or_delete_absent_pending(
    monkeypatch, tmp_path
) -> None:
    pr = release_pr()
    pr["labels"] = [{"name": "autorelease: tagged"}]
    mutations = []
    monkeypatch.setattr(automation, "api", _finalizer_api(pr, mutations))
    monkeypatch.setattr(
        automation, "artifact_hashes", lambda *_args: {"project.whl": "abc"}
    )
    monkeypatch.setattr(automation, "verify_pypi", lambda *_args: None)
    automation.finalize(REPO, 7, MERGE, "0.9.2", tmp_path)
    assert [entry[1] for entry in mutations] == ["POST"]


def test_expired_evidence_cannot_authorize_release(monkeypatch) -> None:
    pr = release_pr()

    def fake_pages(path, key):
        if key == "workflow_runs":
            return [
                {
                    "id": 1,
                    "conclusion": "success",
                    "head_sha": pr["head"]["sha"],
                    "path": ".github/workflows/ci.yml",
                }
            ]
        return [
            {
                "id": 2,
                "name": f"release-evidence-7-{pr['head']['sha']}",
                "expired": True,
            }
        ]

    monkeypatch.setattr(automation, "pages", fake_pages)
    with pytest.raises(ValueError, match="retained release evidence"):
        automation.read_evidence(REPO, pr)


def test_lifecycle_labels_are_initialized_idempotently(monkeypatch) -> None:
    created = []
    monkeypatch.setattr(
        automation, "pages", lambda *_args: [{"name": "autorelease: pending"}]
    )
    monkeypatch.setattr(
        automation, "api", lambda path, **kwargs: created.append((path, kwargs))
    )
    automation.prepare_labels(REPO)
    assert len(created) == 1
    assert created[0][1]["body"]["name"] == "autorelease: tagged"


def test_breaking_intent_can_use_reviewed_pr_migration_notes() -> None:
    message = automation.intent_message(
        "feat!: change configuration", "Migration: rename old to new."
    )
    assert automation.validate_intent(message, "breaking")["impact"] == "breaking"


def test_pr_prose_is_not_treated_as_squash_commits() -> None:
    message = automation.intent_message(
        "docs: describe configuration",
        "Example:\n```yaml\nname: a-server\nfeature: enabled\n```",
    )
    assert automation.parse_intent(message)["impact"] == "none"
