"""Artifact-safety and contributor-contract regression tests."""

import shlex
import tomllib
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[2]
EXPECTED_SDIST_EXCLUDES = [
    "/AGENTS.md",
    "/docs/plans/**",
    "/.superpowers/**",
]
EXPECTED_REQUIRED_CHECKS = (
    "e2e-generated-server (node-22)",
    "e2e-generated-server (node-24)",
    "docs",
    "package",
)
FORBIDDEN_NODE_20_REFERENCES = ("node 20", "node-20", "node.js 20")


def _load_pyproject() -> dict[str, Any]:
    return tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))


def _assert_contributor_contract(path: Path) -> None:
    content = path.read_text(encoding="utf-8")
    folded_content = content.casefold()

    assert "Node.js 22+" in content
    assert not any(
        reference in folded_content for reference in FORBIDDEN_NODE_20_REFERENCES
    )
    for check in EXPECTED_REQUIRED_CHECKS:
        assert f"- `{check}`" in content


def test_sdist_excludes_local_only_artifacts() -> None:
    """Keep instructions, plans, and SDD reports out of source archives."""
    config = _load_pyproject()
    sdist = config["tool"]["hatch"]["build"]["targets"]["sdist"]

    assert sdist["exclude"] == EXPECTED_SDIST_EXCLUDES


def test_mkdocs_excludes_local_plan_directory() -> None:
    """Prevent top-level plan files from entering built documentation."""
    config = yaml.safe_load((ROOT / "mkdocs.yml").read_text(encoding="utf-8"))

    assert config["exclude_docs"].splitlines() == ["/plans/"]


def test_coverage_xml_stays_outside_distribution_directory() -> None:
    """Write test coverage separately from publishable distributions."""
    options = shlex.split(_load_pyproject()["tool"]["pytest"]["ini_options"]["addopts"])
    xml_reports = [
        option for option in options if option.startswith("--cov-report=xml:")
    ]

    assert xml_reports == ["--cov-report=xml:coverage.xml"]
    assert all("dist/" not in option for option in xml_reports)


def test_contributing_documents_supported_node_and_checks() -> None:
    """Keep the root contributor guide aligned with required CI checks."""
    _assert_contributor_contract(ROOT / "CONTRIBUTING.md")


def test_local_workflows_document_supported_node_and_checks() -> None:
    """Keep local workflow guidance aligned with required CI checks."""
    _assert_contributor_contract(ROOT / "docs" / "guides" / "local-workflows.md")
