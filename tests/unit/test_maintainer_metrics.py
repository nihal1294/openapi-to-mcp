# ruff: noqa: ANN201, ARG005, FBT003, PT011, S105
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


def test_cache_ttl_and_stale_replacement(tmp_path):
    clock = datetime(2026, 11, 15, tzinfo=UTC)
    session = Mock()
    session.get.return_value = Mock(
        status_code=200,
        headers={"ETag": "opaque-token"},
        json=lambda: {"data": {"last_day": 0, "last_week": 2, "last_month": 3}},
    )
    source = metrics.Sources(tmp_path, session=session, clock=lambda: clock)
    url = "https://example.test/recent"
    body, provenance = source.get("recent", "p", url)
    assert not provenance["cache"]
    assert source.get("recent", "p", url)[0] == body
    assert session.get.call_count == 1
    path = next((tmp_path / "cache" / "v1").iterdir())
    assert "opaque-token" not in path.read_text()
    source.clock = lambda: clock + timedelta(hours=25)
    session.get.return_value = Mock(
        status_code=200,
        headers={},
        json=lambda: {"data": {"last_day": 7, "last_week": 8, "last_month": 9}},
    )
    body, provenance = source.get("recent", "p", url)
    assert body["data"]["last_day"] == 7
    assert not provenance["cache"]
    assert not session.get.call_args.kwargs.get("headers")
    assert json.loads(path.read_text())["body"] == body


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


def test_cli_sanitizes_provider_labels_before_reports_and_cache(tmp_path, monkeypatch):
    secret = "ghp_0123456789abcdefghijklmnopqrstuvwxyz"
    hostname_secret = "abcdefghijklmnop1234567890"

    def public_get(self, url, **kwargs):
        if url.endswith("/python_minor"):
            body = {
                "data": [
                    {"category": secret, "date": "2026-11-01", "downloads": 2},
                    {"category": "3.14", "date": "2026-11-01", "downloads": 1},
                ]
            }
        elif url.endswith("/system"):
            body = {
                "data": [
                    {"category": "Linux", "date": "2026-11-01", "downloads": 3},
                    {"category": secret, "date": "2026-11-01", "downloads": 2},
                ]
            }
        else:
            raise requests.ConnectionError
        return Mock(status_code=200, headers={}, json=lambda: body)

    monkeypatch.setattr(metrics.requests.Session, "get", public_get)
    monkeypatch.setattr(
        metrics.subprocess,
        "run",
        lambda *a, **k: Mock(
            returncode=0,
            stdout=json.dumps(
                [
                    {
                        "referrer": f"https://user:{secret}@example.com/path?token={secret}",
                        "count": 4,
                        "uniques": 2,
                    },
                    {
                        "referrer": f"https://{hostname_secret}.example.com/path",
                        "count": 5,
                        "uniques": 3,
                    },
                ]
            ),
        ),
    )
    monkeypatch.delenv("GITHUB_ACTIONS", raising=False)
    assert (
        metrics.main(
            ["--output-dir", str(tmp_path), "--include-private-github-traffic"]
        )
        == 1
    )
    for path in tmp_path.rglob("*"):
        if path.is_file():
            assert secret not in path.read_text()
            assert hostname_secret not in path.read_text()
            assert "user:" not in path.read_text()
    report = json.loads((tmp_path / "maintainer-metrics.json").read_text())
    assert (
        report["sections"]["python_minor"]["data"]["downloads_by_category"]["3.14"] == 1
    )
    assert report["sections"]["system"]["data"]["downloads_by_category"]["Linux"] == 3
    assert (
        report["sections"]["referrers"]["data"]["referrers"][0]["referrer"] == "other"
    )


@pytest.mark.parametrize(
    ("endpoint", "body"),
    [
        ("/recent", {}),
        ("/pypi/sample/json", {"releases": {"1": [{"upload_time_iso_8601": 42}]}}),
    ],
)
def test_cli_malformed_schema_writes_partial_reports(
    tmp_path, monkeypatch, endpoint, body
):
    def get(self, url, **kwargs):
        if url.endswith(endpoint):
            return Mock(status_code=200, headers={}, json=lambda: body)
        raise requests.ConnectionError("private error")

    monkeypatch.setattr(metrics.requests.Session, "get", get)
    assert (
        metrics.main(
            [
                "--package",
                "sample",
                "--repo",
                "owner/repo",
                "--output-dir",
                str(tmp_path),
            ]
        )
        == 1
    )
    for name in ("maintainer-metrics.json", "maintainer-metrics.md"):
        content = (tmp_path / name).read_text()
        assert "unavailable" in content
        assert "private error" not in content
    report = json.loads((tmp_path / "maintainer-metrics.json").read_text())
    assert report["completeness"] == "partial"


def test_old_cached_provider_labels_are_reduced_before_reuse(tmp_path):
    secret = "ghp_0123456789abcdefghijklmnopqrstuvwxyz"
    session = Mock()
    session.get.return_value = Mock(
        status_code=200,
        headers={},
        json=lambda: {
            "data": [{"category": "3.14", "date": "2026-11-01", "downloads": 1}]
        },
    )
    source = metrics.Sources(tmp_path, session=session)
    url = "https://example.test/python_minor"
    source.get("python_minor", "sample", url)
    path = next((tmp_path / "cache" / "v1").iterdir())
    envelope = json.loads(path.read_text())
    envelope["body"]["data"][0]["category"] = secret
    path.write_text(json.dumps(envelope))
    body, provenance = source.get("python_minor", "sample", url)
    assert provenance["cache"] is True
    assert body["data"][0]["category"] is None
    assert secret not in path.read_text()
    assert session.get.call_count == 1


def test_referrer_host_and_legacy_envelope_privacy(tmp_path, monkeypatch):
    token = "abcdefghijklmnop1234567890"
    url = "https://api.github.com/repos/owner/repo/traffic/popular/referrers"
    run = Mock(
        return_value=Mock(
            returncode=0,
            stdout=json.dumps(
                [
                    {
                        "referrer": f"https://{token}.example.com/path",
                        "count": 4,
                        "uniques": 2,
                    },
                    {
                        "referrer": f"https://{token}.github.com/path",
                        "count": 3,
                        "uniques": 2,
                    },
                ]
            ),
        )
    )
    monkeypatch.setattr(metrics.subprocess, "run", run)
    source = metrics.Sources(tmp_path, private=True)
    body, _ = source.get("referrers", "owner/repo", url, gh=True)
    assert body == [
        {"referrer": "other", "count": 4, "uniques": 2},
        {"referrer": "github.com", "count": 3, "uniques": 2},
    ]
    path = next((tmp_path / "cache" / "v1").iterdir())
    entry = json.loads(path.read_text())
    entry["etag"] = token
    entry["last_modified"] = token
    entry["headers"] = {"Authorization": token}
    path.write_text(json.dumps(entry))
    body, provenance = source.get("referrers", "owner/repo", url, gh=True)
    assert provenance["cache"]
    assert run.call_count == 1
    assert token not in path.read_text()
    assert set(json.loads(path.read_text())) == {
        "version",
        "url",
        "identifier",
        "fetched_at",
        "status",
        "body",
    }
    assert body[0]["uniques"] == body[1]["uniques"] == 2
    report = {
        "observed_at": "time",
        "package": "sample",
        "repository": "owner/repo",
        "completeness": "complete",
        "sections": {
            "referrers": {
                "data": metrics.normalize("referrers", body)[0],
                "window": None,
                "methodology": "",
                "source": {"url": url},
            }
        },
    }
    assert token not in metrics.render(report)
    assert token not in json.dumps(report)
