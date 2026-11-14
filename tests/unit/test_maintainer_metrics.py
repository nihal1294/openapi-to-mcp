# ruff: noqa: ANN201, ARG005, FBT003, PT011
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import Mock

import pytest
import requests

from scripts import maintainer_metrics as metrics

FIXTURES = Path(__file__).parents[1] / "resources" / "maintainer_metrics"


def test_mirrors_and_partial_history():
    body = json.loads((FIXTURES / "overall.json").read_text())
    data, window = metrics.normalize("overall", body)
    assert data["downloads"] == 3
    assert data["history"] == "insufficient_history"
    assert window == {"start": "2026-11-01", "end": "2026-11-03"}


def test_zero_missing_and_unknown():
    data, _ = metrics.normalize("recent", {"data": {"last_day": 0, "last_week": 2}})
    assert data["last_day"] == {"state": "zero", "value": 0}
    assert data["last_month"]["state"] == "missing"
    data, _ = metrics.normalize(
        "system", {"data": [{"category": None, "date": "2026-11-01", "downloads": 2}]}
    )
    assert data["downloads_by_category"] == {"unknown": 2}


def test_upload_and_release_and_search():
    data, _ = metrics.normalize(
        "pypi",
        {
            "releases": {
                "x": [
                    {"upload_time_iso_8601": "2026-01-02T00:00:00Z"},
                    {},
                    {"upload_time_iso_8601": "2025-01-01T00:00:00Z"},
                ]
            }
        },
    )
    assert data["first_upload"] == "2025-01-01T00:00:00Z"
    assert metrics.normalize("pypi", {"releases": {}})[0]["state"] == "missing"
    assert metrics.normalize("release", None)[0]["published_release"] is None
    assert (
        metrics.normalize("issues", {"total_count": 0, "incomplete_results": False})[0][
            "state"
        ]
        == "zero"
    )
    with pytest.raises(ValueError):
        metrics.normalize("issues", {"total_count": 4, "incomplete_results": True})


def test_cache_and_conditional_refresh(tmp_path):
    clock = datetime(2026, 11, 15, tzinfo=UTC)
    session = Mock()
    session.get.return_value = Mock(
        status_code=200,
        headers={"ETag": "tag"},
        json=lambda: {"data": {"last_day": 0, "last_week": 2, "last_month": 3}},
    )
    source = metrics.Sources(tmp_path, session=session, clock=lambda: clock)
    url = "https://example.test/recent"
    body, provenance = source.get("recent", "p", url)
    assert not provenance["cache"]
    assert source.get("recent", "p", url)[0] == body
    assert session.get.call_count == 1
    source.clock = lambda: clock + timedelta(hours=25)
    session.get.return_value = Mock(status_code=304)
    assert source.get("recent", "p", url)[0] == body
    assert session.get.call_args.kwargs["headers"]["If-None-Match"] == "tag"


@pytest.mark.parametrize("status", [403, 404, 429, 500])
def test_http_failure_is_safe_and_unavailable(tmp_path, status):
    session = Mock()
    session.get.return_value = Mock(
        status_code=status, text="secret Authorization: token"
    )
    body, provenance = metrics.Sources(tmp_path, session=session).get(
        "recent", "p", "https://example.test"
    )
    assert body is None
    assert provenance["state"] == "unavailable"
    assert "secret" not in str(provenance)


def test_timeout_and_bad_schema(tmp_path):
    session = Mock()
    session.get.side_effect = requests.Timeout("secret")
    assert (
        metrics.Sources(tmp_path, session=session).get(
            "recent", "p", "https://example.test"
        )[1]["state"]
        == "unavailable"
    )
    session.get.side_effect = None
    session.get.return_value = Mock(
        status_code=200, headers={}, json=lambda: {"data": []}
    )
    assert (
        metrics.Sources(tmp_path, session=session).get(
            "recent", "p", "https://example.test"
        )[1]["state"]
        == "unavailable"
    )


def test_public_and_actions_guard(tmp_path, monkeypatch):
    run = Mock(side_effect=AssertionError("gh should not run"))
    monkeypatch.setattr(metrics.subprocess, "run", run)
    monkeypatch.setenv("GITHUB_ACTIONS", "true")
    with pytest.raises(SystemExit):
        metrics.main(
            ["--output-dir", str(tmp_path), "--include-private-github-traffic"]
        )
    assert not run.called


def test_private_file_permissions_and_sanitized_failure(tmp_path, monkeypatch):
    monkeypatch.setattr(
        metrics.subprocess,
        "run",
        lambda *a, **k: Mock(returncode=1, stderr="secret token"),
    )
    source = metrics.Sources(tmp_path, private=True)
    assert "secret" not in str(
        source.get("views", "a/b", "https://api.github.com/repos/a/b/traffic/views")
    )
    metrics.write_file(tmp_path / "report", "private", True)
    assert (tmp_path / "report").stat().st_mode & 0o777 == 0o600


def test_partial_report_for_unavailable_sources(tmp_path):
    session = Mock()
    session.get.side_effect = requests.ConnectionError("sensitive detail")
    report = metrics.build_report(
        "sample", "owner/repo", metrics.Sources(tmp_path, session=session)
    )
    assert report["completeness"] == "partial"
    assert report["sections"]["recent"]["data"]["state"] == "unavailable"
    assert "sensitive detail" not in metrics.render(report)


def test_private_success_cache_permissions_and_public_no_gh(tmp_path, monkeypatch):
    run = Mock(
        return_value=Mock(
            returncode=0, stdout=json.dumps({"count": 0, "uniques": 0, "views": []})
        )
    )
    monkeypatch.setattr(metrics.subprocess, "run", run)
    source = metrics.Sources(tmp_path, private=True)
    body, _ = source.get(
        "views",
        "owner/repo",
        "https://api.github.com/repos/owner/repo/traffic/views",
        gh=True,
    )
    assert body["count"] == 0
    assert next((tmp_path / "cache" / "v1").iterdir()).stat().st_mode & 0o777 == 0o600
    run.reset_mock()
    session = Mock()
    session.get.side_effect = requests.ConnectionError()
    report = metrics.build_report(
        "sample", "owner/repo", metrics.Sources(tmp_path, session=session)
    )
    assert "views" not in report["sections"]
    assert not run.called


def test_corrupt_cache_is_refetched(tmp_path):
    session = Mock()
    session.get.return_value = Mock(
        status_code=200,
        headers={},
        json=lambda: {"data": {"last_day": 1, "last_week": 1, "last_month": 1}},
    )
    source = metrics.Sources(tmp_path, session=session)
    source.get("recent", "p", "https://example.test")
    path = next((tmp_path / "cache" / "v1").iterdir())
    entry = json.loads(path.read_text())
    entry["body"] = {"data": []}
    path.write_text(json.dumps(entry))
    source.get("recent", "p", "https://example.test")
    assert session.get.call_count == 2
