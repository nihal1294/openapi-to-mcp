"""Extract and render reviewed, single-line migration guidance."""

from __future__ import annotations

import hashlib
import re

MAX_NOTE_BYTES = 4096
MAX_RENDERED_BYTES = 65536
_NOTE = re.compile(
    r"^[ \t]*migration(?:[ \t]+notes?)?[ \t]*:[ \t]*(.*)$", re.IGNORECASE
)
_FENCE = re.compile(r"^[ \t]*(`{3,}|~{3,})(.*)$")
_REPOSITORY = re.compile(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+\Z")
_SHA = re.compile(r"[0-9a-f]{40}\Z")
_VERSION = re.compile(r"(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\Z")


def extract_migration_note(message: str) -> str | None:  # noqa: C901
    """Return the unique eligible note, rejecting ambiguous or unsafe text."""
    notes: set[str] = set()
    fence: tuple[str, int] | None = None
    lines = message.split("\n")
    for index, raw in enumerate(lines):
        line = raw.removesuffix("\r") if index < len(lines) - 1 else raw
        match = _FENCE.match(line)
        if fence:
            if (
                match
                and match.group(1)[0] == fence[0]
                and len(match.group(1)) >= fence[1]
                and not match.group(2).strip()
            ):
                fence = None
            continue
        if match:
            fence = (match.group(1)[0], len(match.group(1)))
            continue
        note = _NOTE.match(line)
        if not note:
            continue
        value = note.group(1).strip(" \t")
        if not value:
            raise ValueError("The migration notes must not be blank.")
        if any(
            (c < " " and c != "\t") or "\x7f" <= c <= "\x9f" or c in "\u2028\u2029"
            for c in value
        ):
            raise ValueError("Migration notes contain prohibited control characters.")
        try:
            size = len(value.encode("utf-8", errors="strict"))
        except UnicodeEncodeError as error:
            raise ValueError("Migration notes must be valid UTF-8.") from error
        if size > MAX_NOTE_BYTES:
            raise ValueError("Migration notes exceed 4096 UTF-8 bytes.")
        notes.add(value)
    if len(notes) > 1:
        raise ValueError("Conflicting migration notes in one source.")
    return next(iter(notes), None)


def build_release_notes(repository: str, version: str, history: dict) -> dict:
    """Render ordered guidance from the selected effective release history."""
    if not _REPOSITORY.fullmatch(repository) or not _VERSION.fullmatch(version):
        raise ValueError("Invalid repository or release version for migration notes.")
    entries = []
    lines = []
    for change in history["changes"]:
        sha, pr = change["sha"], change["pr"]
        if (
            not isinstance(sha, str)
            or not _SHA.fullmatch(sha)
            or (pr is not None and (type(pr) is not int or pr <= 0))
        ):
            raise ValueError("Invalid commit or PR identifier for migration notes.")
        note = extract_migration_note(change["message"])
        if note is None:
            continue
        entries.append({"sha": sha, "pr": pr, "text": note})
        link = (
            f"[#{pr}](https://github.com/{repository}/pull/{pr})"
            if pr is not None
            else f"[{sha[:7]}](https://github.com/{repository}/commit/{sha})"
        )
        lines.append(f"- {link}: {note}")
    markdown = (
        f"## Migration guidance for v{version}\n\n" + "\n".join(lines) + "\n"
        if lines
        else ""
    )
    content = markdown.encode("utf-8", errors="strict")
    if len(content) > MAX_RENDERED_BYTES:
        raise ValueError("Rendered migration guidance exceeds 65536 UTF-8 bytes.")
    return {
        "schema": 1,
        "version": version,
        "entries": entries,
        "markdown": markdown,
        "sha256": hashlib.sha256(content).hexdigest(),
    }
