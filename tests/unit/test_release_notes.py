"""Reviewed migration guidance is deterministic and safe to publish."""

import hashlib
import os
import subprocess
import textwrap
from copy import deepcopy
from pathlib import Path

import pytest

from scripts import release_automation as automation
from scripts import release_metadata
from scripts.release_notes import build_release_notes, extract_migration_note
from scripts.release_notes_cli import verify
from tests.unit.test_release_metadata import BASE, MERGE, REPO, evidence, release_pr


def test_migration_guidance_is_rendered_from_selected_history() -> None:

    history = {
        "changes": [
            {
                "sha": "a" * 40,
                "pr": 42,
                "message": "fix: change\n\nMigration: See [guide](https://example.com).",
            }
        ]
    }
    result = build_release_notes("owner/repo", "0.15.0", history)
    markdown = "## Migration guidance for v0.15.0\n\n- [#42](https://github.com/owner/repo/pull/42): See [guide](https://example.com).\n"
    assert result == {
        "schema": 1,
        "version": "0.15.0",
        "entries": [
            {"sha": "a" * 40, "pr": 42, "text": "See [guide](https://example.com)."}
        ],
        "markdown": markdown,
        "sha256": hashlib.sha256(markdown.encode()).hexdigest(),
    }


def test_effective_and_body_notes_must_agree() -> None:
    with pytest.raises(ValueError, match=r"[Cc]onflict"):
        automation.intent_message(
            "fix: change\n\nMigration: first", "Migration: second"
        )


def test_workflow_passes_authorized_artifact_by_id_and_verifies_twice() -> None:

    workflow = Path(".github/workflows/release.yml").read_text()
    assert (
        "artifact-ids: ${{ needs.detect-version-bump.outputs.notes_artifact_id }}"
        in workflow
    )
    assert workflow.count("scripts/release_notes_cli.py verify") == 2
    assert '--notes-file "$RUNNER_TEMP/release-notes/release-notes.md"' in workflow


@pytest.mark.parametrize(
    "message",
    [
        "Migration: ",
        "Migration: bad\rcontrol",
        "Migration: bad\r",
        "Migration: bad\x01",
        "Migration: bad\x7f",
        "Migration: bad\u0080",
        "Migration: bad\u009b",
        "Migration: bad\u009f",
        "Migration: bad\u0085next",
        "Migration: bad\u2028next",
        "Migration: bad\u2029next",
        "Migration: \ud800",
        "Migration: " + "é" * 2049,
        "Migration: one\nMigration note: two",
    ],
)
def test_invalid_guidance_is_rejected(message) -> None:

    with pytest.raises(ValueError, match=r"[Mm]igration notes"):
        extract_migration_note(message)


def test_fences_quotes_duplicates_crlf_and_unicode() -> None:

    text = "> Migration: ignored\r\n````text\r\nMigration: ignored\r\n```\r\nMigration: ignored\r\n````\r\n~~~\r\nMigration: ignored\r\n~~~\r\nMigration Notes:  café `a`\t[b](url) \r\nMigration: café `a`\t[b](url)"
    assert extract_migration_note(text) == "café `a`\t[b](url)"
    assert extract_migration_note("```\nMigration: ignored") is None


def test_breaking_fenced_guidance_is_not_accepted() -> None:
    with pytest.raises(ValueError, match="migration notes"):
        automation.parse_intent("feat!: breaking\n\n```\nMigration: fake\n```")


def test_empty_and_direct_commit_and_size_limit() -> None:

    assert (
        build_release_notes("owner/repo", "0.15.0", {"changes": []})["markdown"] == ""
    )
    change = {"sha": "b" * 40, "pr": None, "message": "fix: x\nMigration: text"}
    assert (
        "[bbbbbbb](https://github.com/owner/repo/commit/"
        in build_release_notes("owner/repo", "0.15.0", {"changes": [change]})[
            "markdown"
        ]
    )
    with pytest.raises(ValueError, match="65536"):
        build_release_notes("owner/repo", "0.15.0", {"changes": [change] * 1000})


def test_digest_verification_handles_empty_tampered_and_missing(tmp_path) -> None:

    path = tmp_path / "notes"
    path.write_bytes(b"")
    verify(path, hashlib.sha256(b"").hexdigest())
    path.write_bytes(b"tampered")
    with pytest.raises(ValueError, match="does not match"):
        verify(path, hashlib.sha256(b"").hexdigest())
    path.unlink()
    with pytest.raises(FileNotFoundError):
        verify(path, hashlib.sha256(b"").hexdigest())


def test_authorization_writes_only_reviewed_bytes_and_rejects_tampering(
    monkeypatch, tmp_path
) -> None:

    pr = release_pr()
    history = {
        "impact": "patch",
        "changes": [
            {
                "sha": "e" * 40,
                "pr": 2,
                "message": "fix: update\nMigration: use `new`.",
                "impact": "patch",
            }
        ],
    }
    proof = evidence(pr)
    proof["history"] = history
    proof["release_notes"] = build_release_notes(REPO, "0.9.2", history)
    monkeypatch.setattr(
        automation, "resolve", lambda ref: "d" * 40 if ref.startswith("v") else ref
    )
    monkeypatch.setattr(
        automation,
        "api",
        lambda path: (
            [{"merge_commit_sha": MERGE, "merged_at": "now", "number": 7}]
            if "/commits/" in path
            else deepcopy(pr)
        ),
    )
    monkeypatch.setattr(
        automation,
        "git",
        lambda *args: f"{MERGE} {BASE}" if args[0] == "rev-list" else "tree",
    )
    monkeypatch.setattr(automation.subprocess, "run", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(automation, "validate_release_files", lambda *_args: "0.9.2")
    monkeypatch.setattr(automation, "read_evidence", lambda *_args: proof)
    monkeypatch.setattr(automation, "project_version", lambda _ref: "0.9.1")
    monkeypatch.setattr(automation, "release_range", lambda *_args: history)
    monkeypatch.setattr(automation, "contracts", lambda *_args: {"minimum": "patch"})
    path = tmp_path / "notes"
    automation.authorize(REPO, MERGE, path)
    assert path.read_bytes() == proof["release_notes"]["markdown"].encode()
    for field, value in [
        ("sha256", "0" * 64),
        ("markdown", "tampered"),
        ("entries", []),
        ("version", "1.0.0"),
        ("schema", 2),
        ("schema", True),
    ]:
        original = deepcopy(proof["release_notes"])
        proof["release_notes"][field] = value
        path.write_bytes(b"keep")
        with pytest.raises(ValueError, match="rerun CI"):
            automation.authorize(REPO, MERGE, path)
        assert path.read_bytes() == b"keep"
        proof["release_notes"] = original
    proof.pop("release_notes")
    with pytest.raises(ValueError, match="rerun CI"):
        automation.authorize(REPO, MERGE, path)
    assert path.read_bytes() == b"keep"


@pytest.mark.parametrize(
    ("content", "exists"),
    [(b"guidance $() `x`\n", False), (b"", False), (b"guidance", True)],
)
def test_release_command_uses_reviewed_file_and_preserves_existing_release(
    tmp_path, content, exists
) -> None:

    workflow = Path(".github/workflows/release.yml").read_text()
    section = workflow.split("      - name: Create GitHub Release", 1)[1].split(
        "\n  finalize-release:", 1
    )[0]
    shell = textwrap.dedent(section.split("        run: |\n", 1)[1])
    bindir = tmp_path / "bin"
    bindir.mkdir()
    gh = bindir / "gh"
    gh.write_text(
        '#!/bin/bash\nif [[ "$2" == view ]]; then exit "$EXISTS"; fi\nprintf "%s\\n" "$@" > "$ARGS_FILE"\n'
    )
    gh.chmod(0o755)
    notes = tmp_path / "release-notes"
    notes.mkdir()
    (notes / "release-notes.md").write_bytes(content)
    dist = tmp_path / "dist"
    dist.mkdir()
    (dist / "x.whl").touch()
    args_file = tmp_path / "args"
    env = {
        **os.environ,
        "PATH": f"{bindir}:" + os.environ["PATH"],
        "RUNNER_TEMP": str(tmp_path),
        "TAG_NAME": "v1.2.3",
        "GITHUB_SHA": "a" * 40,
        "EXISTS": "0" if exists else "1",
        "ARGS_FILE": str(args_file),
    }
    subprocess.run(["bash", "-e", "-c", shell], cwd=tmp_path, env=env, check=True)  # noqa: S603, S607
    if exists:
        assert not args_file.exists()
    else:
        argv = args_file.read_text().splitlines()
        assert "--generate-notes" in argv
        assert ("--notes-file" in argv) == bool(content)
        if content:
            assert argv[argv.index("--notes-file") + 1] == str(
                notes / "release-notes.md"
            )
            assert (notes / "release-notes.md").read_bytes() == content


def test_workflow_verifies_notes_with_python_314_before_publication() -> None:
    workflow = Path(".github/workflows/release.yml").read_text()
    build = workflow.split("  build-release:", 1)[1].split("  pypi-publish:", 1)[0]
    github = workflow.split("  github-release:", 1)[1].split("  finalize-release:", 1)[
        0
    ]
    for job in (build, github):
        setup = job.index("- name: Set up Python 3.14")
        action = job.index(
            "uses: actions/setup-python@6d4fd22b20465ccc0f7354476588e8df7c9ca0e0", setup
        )
        version = job.index('python-version: "3.14"', action)
        verify = job.index("scripts/release_notes_cli.py verify")
        assert setup < action < version < verify
    assert build.index("scripts/release_notes_cli.py verify") < build.index(
        "- name: Build distribution artifacts"
    )
    assert github.index("scripts/release_notes_cli.py verify") < github.index(
        "- name: Create GitHub Release"
    )


@pytest.mark.parametrize("separator", ["\u0085", "\u2028", "\u2029"])
def test_release_range_rejects_trailing_unicode_separators_from_git(
    monkeypatch, separator
) -> None:
    sha = "a" * 40
    message = f"fix: change\n\nMigration: use new{separator}\n"

    def check_output(command, *, text=False):
        result = f"{sha}\n" if command[1] == "rev-list" else message
        return result if text else result.encode("utf-8")

    monkeypatch.setattr(release_metadata.subprocess, "check_output", check_output)
    monkeypatch.setattr(automation, "api", lambda *_args: [])
    monkeypatch.setattr(automation, "resolve", lambda ref: ref)
    monkeypatch.setattr(
        automation, "analyze_changes", lambda *_args: {"minimum": "patch"}
    )
    with pytest.raises(ValueError, match="control"):
        automation.release_range("owner/repo", "base", "head")


@pytest.mark.parametrize("newline", ["\n", "\r\n"])
def test_release_range_preserves_allowed_commit_note_text(monkeypatch, newline) -> None:
    sha = "a" * 40
    message = f"fix: change{newline}{newline}Migration: café\tnew{newline}"

    def check_output(command, *, text=False):
        result = f"{sha}\n" if command[1] == "rev-list" else message
        return result if text else result.encode("utf-8")

    monkeypatch.setattr(release_metadata.subprocess, "check_output", check_output)
    monkeypatch.setattr(automation, "api", lambda *_args: [])
    monkeypatch.setattr(automation, "resolve", lambda ref: ref)
    monkeypatch.setattr(
        automation, "analyze_changes", lambda *_args: {"minimum": "patch"}
    )
    history = automation.release_range("owner/repo", "base", "head")
    assert (
        build_release_notes("owner/repo", "0.15.0", history)["entries"][0]["text"]
        == "café\tnew"
    )


@pytest.mark.parametrize("separator", ["\u0085", "\u2028", "\u2029"])
def test_override_does_not_trim_invalid_trailing_note(separator) -> None:
    body = f"```\nBEGIN_COMMIT_OVERRIDE\nfix: change\nMigration: use new{separator}\nEND_COMMIT_OVERRIDE\n```"
    with pytest.raises(ValueError, match="control"):
        automation.intent_message("fix: original", body)
