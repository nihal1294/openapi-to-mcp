"""Repository automation contracts for dependency migration CI."""

from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[2]
WORKFLOWS = ROOT / ".github" / "workflows"
EXPECTED_PR_GATE_STEPS = {
    "docs": [
        {"name": "Check out repository", "uses": "actions/checkout@v7"},
        {
            "name": "Set up Python 3.14",
            "uses": "actions/setup-python@v7",
            "with": {"python-version": "3.14"},
        },
        {
            "name": "Set up uv",
            "uses": "astral-sh/setup-uv@v10.0.1",
            "with": {"enable-cache": "true"},
        },
        {"name": "Sync dependencies", "run": "uv sync --dev --frozen"},
        {
            "name": "Build docs strictly",
            "run": "NO_MKDOCS_2_WARNING=1 uv run mkdocs build --strict",
        },
    ],
    "package": [
        {"name": "Check out repository", "uses": "actions/checkout@v7"},
        {
            "name": "Set up Python 3.14",
            "uses": "actions/setup-python@v7",
            "with": {"python-version": "3.14"},
        },
        {"name": "Set up uv", "uses": "astral-sh/setup-uv@v10.0.1"},
        {"name": "Build distribution artifacts", "run": "uv build"},
        {
            "name": "Check distribution metadata",
            "run": "uvx --from twine==7.0.0 twine check dist/*",
        },
        {
            "name": "Check installed wheel CLI",
            "run": "uvx --from dist/*.whl openapi-to-mcp --help",
        },
    ],
}


def _workflow_files() -> list[Path]:
    return sorted((*WORKFLOWS.glob("*.yml"), *WORKFLOWS.glob("*.yaml")))


def _load_workflow(name: str) -> dict[str, Any]:
    content = (WORKFLOWS / name).read_text(encoding="utf-8")
    workflow = yaml.load(content, Loader=yaml.BaseLoader)  # noqa: S506
    assert "on" in workflow
    return workflow


def test_all_setup_uv_actions_use_v10_0_1() -> None:
    """Require every workflow to use the approved setup-uv release."""
    references = [
        line.split("astral-sh/setup-uv@", maxsplit=1)[1].strip()
        for workflow in _workflow_files()
        for line in workflow.read_text(encoding="utf-8").splitlines()
        if "uses: astral-sh/setup-uv@" in line
    ]

    assert references
    assert set(references) == {"v10.0.1"}


def test_generated_server_ci_uses_supported_node_versions() -> None:
    """Exercise generated servers on every supported Node.js major."""
    workflow = _load_workflow("ci.yml")
    matrix = workflow["jobs"]["e2e-generated-server"]["strategy"]["matrix"]

    assert matrix["node-version"] == ["22", "24"]


def test_cli_e2e_uses_minimum_supported_node_version() -> None:
    """Keep CLI end-to-end coverage at the minimum supported Node.js major."""
    workflow = _load_workflow("ci.yml")
    steps = workflow["jobs"]["e2e-cli-matrix"]["steps"]
    setup_node = next(
        step for step in steps if step.get("uses") == "actions/setup-node@v7"
    )

    assert setup_node["with"]["node-version"] == "22"


def test_pull_request_ci_builds_docs_strictly() -> None:
    """Block pull requests when the documentation build emits warnings."""
    workflow = _load_workflow("ci.yml")
    steps = workflow["jobs"]["docs"]["steps"]
    commands = [step.get("run") for step in steps]

    assert "pull_request" in workflow["on"]
    assert "NO_MKDOCS_2_WARNING=1 uv run mkdocs build --strict" in commands


def test_pull_request_ci_validates_built_package() -> None:
    """Build and exercise distribution artifacts before a pull request merges."""
    workflow = _load_workflow("ci.yml")
    steps = workflow["jobs"]["package"]["steps"]
    commands = [step.get("run") for step in steps]

    assert "pull_request" in workflow["on"]
    assert "uv build" in commands
    assert "uvx --from twine==7.0.0 twine check dist/*" in commands
    assert "uvx --from dist/*.whl openapi-to-mcp --help" in commands


def test_pull_request_jobs_have_read_only_repository_access() -> None:
    """Keep pull-request gates free of release credentials and write access."""
    workflow = _load_workflow("ci.yml")
    assert workflow["permissions"] == {"contents": "read"}

    for job_name, expected_steps in EXPECTED_PR_GATE_STEPS.items():
        job = workflow["jobs"][job_name]
        assert set(job) == {"name", "needs", "runs-on", "timeout-minutes", "steps"}
        assert job["steps"] == expected_steps

        commands_and_actions = "\n".join(
            step.get("uses", "") + step.get("run", "") for step in job["steps"]
        ).casefold()
        forbidden = (
            "secrets.",
            "github.token",
            "credential",
            "password",
            "publish",
            "deploy",
            "release",
            "upload",
        )
        assert not any(term in commands_and_actions for term in forbidden)


def test_dependabot_separates_uv_dependency_groups() -> None:
    """Keep runtime, tooling, docs, build, and MCP major updates isolated."""
    config = yaml.safe_load(
        (ROOT / ".github" / "dependabot.yml").read_text(encoding="utf-8")
    )
    uv_update = next(
        update for update in config["updates"] if update["package-ecosystem"] == "uv"
    )

    expected_groups = {
        "mcp-major": {"patterns": ["mcp"], "update-types": ["major"]},
        "python-runtime": {
            "patterns": [
                "click",
                "jinja2",
                "mcp",
                "openapi-spec-validator",
                "pyyaml",
                "requests",
                "rich",
                "rich-click",
                "structlog",
            ],
            "update-types": ["minor", "patch"],
        },
        "python-development": {
            "patterns": ["pre-commit", "pytest", "pytest-*", "ruff"]
        },
        "documentation": {"patterns": ["mkdocs", "mkdocs-material"]},
        "build-system": {"patterns": ["hatchling"]},
    }
    assert list(uv_update["groups"].items()) == list(expected_groups.items())

    actions_update = next(
        update
        for update in config["updates"]
        if update["package-ecosystem"] == "github-actions"
    )
    expected_action_groups = {
        "github-actions": {"patterns": ["*"]},
    }
    assert list(actions_update["groups"].items()) == list(
        expected_action_groups.items()
    )


def test_cli_integration_modules_stay_within_file_limit() -> None:
    """Keep CLI integration modules within the repository navigation limit."""
    modules = (ROOT / "tests" / "integration").glob("test_cli*.py")
    line_counts = {
        module.name: len(module.read_text(encoding="utf-8").splitlines())
        for module in modules
    }

    assert {name: count for name, count in line_counts.items() if count > 200} == {}
