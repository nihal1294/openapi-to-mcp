"""Release-note visibility does not make documentation release the product."""

from __future__ import annotations

import pytest

from scripts import release_automation as automation


@pytest.mark.parametrize(
    ("message", "ready"),
    [
        ("docs: add a container deployment guide", False),
        ("fix: preserve schema constraints", True),
    ],
)
def test_preflight_requires_product_release_intent(
    monkeypatch, message: str, *, ready: bool
) -> None:
    repository = "example/project"
    head = "a" * 40
    monkeypatch.setattr(automation, "pages", lambda *_args: [])
    monkeypatch.setattr(automation, "resolve", lambda *_args: head)
    monkeypatch.setattr(automation, "project_version", lambda *_args: "0.9.2")
    monkeypatch.setattr(automation, "api", lambda *_args: {"object": {"sha": head}})
    monkeypatch.setattr(
        automation,
        "release_range",
        lambda *_args: {"impact": automation.parse_intent(message)["impact"]},
    )
    outputs = []
    monkeypatch.setattr(automation, "output", lambda **values: outputs.append(values))

    automation.preflight(repository)

    assert outputs == [{"ready": ready}]
