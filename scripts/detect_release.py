"""Detect whether the current version needs a release."""

import os
import subprocess
import tomllib
from pathlib import Path


def main() -> None:
    """Write release decision outputs for the GitHub Actions job."""
    before_sha = os.environ.get("BEFORE_SHA", "")
    output_path = Path(os.environ["GITHUB_OUTPUT"])
    current = tomllib.loads(Path("pyproject.toml").read_text(encoding="utf-8"))[
        "project"
    ]["version"]
    tag_name = f"v{current}"

    version_changed = False
    zero_sha = "0" * 40
    if before_sha and before_sha != zero_sha:
        prior = subprocess.check_output(  # noqa: S603
            ["git", "show", f"{before_sha}:pyproject.toml"],  # noqa: S607
            text=True,
        )
        version_changed = tomllib.loads(prior)["project"]["version"] != current

    if version_changed:
        existing_tag_ref = subprocess.check_output(  # noqa: S603
            [  # noqa: S607
                "git",
                "ls-remote",
                "--tags",
                "origin",
                f"refs/tags/{tag_name}",
            ],
            text=True,
        ).strip()
        if existing_tag_ref:
            raise SystemExit(
                f"Version {current} already has a release tag; choose a new version."
            )

    with output_path.open("a", encoding="utf-8") as output:
        output.write(f"version={current}\n")
        output.write(f"tag_name={tag_name}\n")
        output.write(f"should_release={'true' if version_changed else 'false'}\n")


if __name__ == "__main__":
    main()
