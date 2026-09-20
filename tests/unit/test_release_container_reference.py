"""Container examples do not change the installed Python package."""

from __future__ import annotations

import pytest

from scripts import release_policy_changes


def test_container_reference_is_repository_only(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        release_policy_changes,
        "_changed_paths",
        lambda *_: {"examples/container/Dockerfile": "A"},
    )
    assert release_policy_changes.analyze_changes("base", "head")["minimum"] == "none"


def test_other_example_paths_still_require_review(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        release_policy_changes,
        "_changed_paths",
        lambda *_: {"examples/new-runtime/server.js": "A"},
    )
    with pytest.raises(ValueError, match="Unclassified path"):
        release_policy_changes.analyze_changes("base", "head")
