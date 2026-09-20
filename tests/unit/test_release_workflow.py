from pathlib import Path

import yaml

WORKFLOW = Path(__file__).parents[2] / ".github" / "workflows" / "release.yml"


def test_release_concurrency_preserves_pending_version_bumps() -> None:
    """A later push must not replace a waiting version-bump run."""
    workflow = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
    concurrency = workflow["concurrency"]

    assert concurrency.get("queue") == "max"
    assert concurrency.get("cancel-in-progress", False) is False
