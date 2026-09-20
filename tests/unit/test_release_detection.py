from __future__ import annotations

import runpy
import subprocess
from pathlib import Path

import pytest

SCRIPT = Path(__file__).parents[2] / "scripts" / "detect_release.py"


def _run_detector(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    previous_version: str | None,
    tag_ref: str,
    before_sha: str = "old-sha",
) -> Path:
    (tmp_path / "pyproject.toml").write_text(
        '[project]\nversion = "0.9.0"\n', encoding="utf-8"
    )
    output_path = tmp_path / "github-output"

    def fake_check_output(command: list[str], *, text: bool) -> str:
        del text
        if command[1] == "show":
            if previous_version is None:
                raise subprocess.CalledProcessError(128, command)
            return f'[project]\nversion = "{previous_version}"\n'
        return tag_ref

    monkeypatch.setattr(subprocess, "check_output", fake_check_output)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("BEFORE_SHA", before_sha)
    monkeypatch.setenv("GITHUB_OUTPUT", str(output_path))
    runpy.run_path(str(SCRIPT), run_name="__main__")
    return output_path


def test_changed_version_without_tag_requests_release(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    output = _run_detector(monkeypatch, tmp_path, "0.8.0", "")
    contents = output.read_text(encoding="utf-8")
    assert "should_release=true" in contents
    assert "version=0.9.0" in contents
    assert "tag_name=v0.9.0" in contents


def test_unchanged_version_with_existing_tag_skips_release(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    output = _run_detector(monkeypatch, tmp_path, "0.9.0", "tag-sha")
    contents = output.read_text(encoding="utf-8")
    assert "should_release=false" in contents


def test_missing_tag_does_not_republish_unchanged_version(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    output = _run_detector(monkeypatch, tmp_path, "0.9.0", "")
    contents = output.read_text(encoding="utf-8")
    assert "should_release=false" in contents


@pytest.mark.parametrize("before_sha", ["", "0" * 40])
def test_missing_previous_commit_does_not_request_release(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, before_sha: str
) -> None:
    output = _run_detector(monkeypatch, tmp_path, "0.8.0", "", before_sha)
    assert "should_release=false" in output.read_text(encoding="utf-8")


def test_unreadable_previous_version_stops_before_output(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    with pytest.raises(subprocess.CalledProcessError):
        _run_detector(monkeypatch, tmp_path, None, "")
    assert not (tmp_path / "github-output").exists()


def test_changed_version_with_existing_tag_stops_before_output(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    with pytest.raises(SystemExit, match="already has a release tag"):
        _run_detector(monkeypatch, tmp_path, "0.8.0", "tag-sha")
    assert not (tmp_path / "github-output").exists()
