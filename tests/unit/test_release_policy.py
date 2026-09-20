from __future__ import annotations

import pytest

from scripts import release_policy, release_policy_changes
from scripts.release_policy_config import project_impacts


def test_parse_intent_classifies_conventional_messages() -> None:
    assert (
        release_policy.parse_intent("fix: preserve result metadata")["impact"]
        == "patch"
    )
    assert release_policy.parse_intent("feat: add a policy check")["impact"] == "minor"
    assert release_policy.parse_intent("docs: clarify installation")["impact"] == "none"


def test_parse_intent_requires_migration_notes_for_breaking_change() -> None:
    with pytest.raises(ValueError, match="migration notes"):
        release_policy.parse_intent("feat!: replace the generated runtime")

    result = release_policy.parse_intent(
        "feat!: replace the generated runtime\n\nMigration: regenerate projects."
    )

    assert result["impact"] == "breaking"


def test_parse_intent_uses_complete_commit_override() -> None:
    result = release_policy.parse_intent(
        "chore: stale title\n\nBEGIN_COMMIT_OVERRIDE\nfix: repair output\n\n"
        "feat: add an option\nEND_COMMIT_OVERRIDE"
    )

    assert result["impact"] == "minor"
    assert result["reasons"] == ["fix commit", "feat commit"]


def test_parse_intent_classifies_embedded_squash_messages() -> None:
    result = release_policy.parse_intent(
        "fix: restore metadata\n\nfeat: add a transport\n\nMigration: no action needed."
    )

    assert result["impact"] == "minor"
    assert result["reasons"] == ["fix commit", "feat commit"]


@pytest.mark.parametrize(
    "message",
    [
        "fix: repair\n\nRelease-As: 9.9.9",
        "BEGIN_COMMIT_OVERRIDE\nfix: repair",
        "END_COMMIT_OVERRIDE\nfix: repair",
        "update dependencies",
    ],
)
def test_parse_intent_rejects_forced_or_malformed_messages(message: str) -> None:
    with pytest.raises(ValueError, match=r"Release-As|Malformed|conventional"):
        release_policy.parse_intent(message)


def test_parse_intent_rejects_non_native_revert_type() -> None:
    with pytest.raises(ValueError, match="Unsupported"):
        release_policy.parse_intent("revert: undo an unpublished feature")


def test_validate_intent_rejects_a_declared_impact_below_evidence() -> None:
    with pytest.raises(ValueError, match="below evidence"):
        release_policy.validate_intent("fix: rename command", "breaking")

    validated = release_policy.validate_intent(
        "feat!: replace runtime\n\nMigration: regenerate.", "minor"
    )

    assert validated["impact"] == "breaking"
    assert validated["minimum"] == "minor"


@pytest.mark.parametrize(
    ("previous", "current", "impact"),
    [
        ("0.9.1", "0.9.2", "patch"),
        ("0.9.1", "0.10.0", "minor"),
        ("0.9.1", "0.10.0", "breaking"),
        ("1.2.3", "1.2.4", "patch"),
        ("1.2.3", "1.3.0", "minor"),
        ("1.2.3", "2.0.0", "breaking"),
    ],
)
def test_validate_version_accepts_policy_bumps(
    previous: str, current: str, impact: str
) -> None:
    release_policy.validate_version(previous, current, impact)


def test_validate_version_requires_explicit_promotion_to_one() -> None:
    with pytest.raises(ValueError, match="breaking"):
        release_policy.validate_version("0.9.1", "1.0.0", "breaking")

    release_policy.validate_version("0.9.1", "1.0.0", "breaking", promotion=True)


def test_analyze_changes_treats_runtime_lock_transitive_as_patch(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    base_pyproject = _pyproject('dependencies = ["requests==1"]')
    head_pyproject = _pyproject('dependencies = ["requests==1"]')
    base_lock = _lock("1.0", "1.0")
    head_lock = _lock("1.0", "2.0")
    _stub_git(
        monkeypatch,
        "M\tuv.lock\n",
        {
            "base:pyproject.toml": base_pyproject,
            "head:pyproject.toml": head_pyproject,
            "base:uv.lock": base_lock,
            "head:uv.lock": head_lock,
        },
    )

    result = release_policy.analyze_changes("base", "head")

    assert result["minimum"] == "patch"
    assert "runtime lock dependency changed: urllib3" in result["reasons"]


def test_analyze_changes_treats_dev_lock_only_as_none(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pyproject = _pyproject('dependencies = ["requests==1"]')
    base_lock = _lock("1.0", "1.0", ruff_version="1.0")
    head_lock = _lock("1.0", "1.0", ruff_version="2.0")
    _stub_git(
        monkeypatch,
        "M\tuv.lock\n",
        {
            "base:pyproject.toml": pyproject,
            "head:pyproject.toml": pyproject,
            "base:uv.lock": base_lock,
            "head:uv.lock": head_lock,
        },
    )

    assert release_policy.analyze_changes("base", "head")["minimum"] == "none"


def test_analyze_changes_detects_removed_cli_command_and_runtime_floor(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _stub_git(
        monkeypatch,
        "M\topenapi_to_mcp/cli.py\nM\topenapi_to_mcp/templates/package.json.j2\n",
        {
            "base:openapi_to_mcp/cli.py": "cli.add_command(generate)\ncli.add_command(diff)\n",
            "head:openapi_to_mcp/cli.py": "cli.add_command(generate)\n",
            "base:openapi_to_mcp/templates/package.json.j2": '"node": ">=22"\n',
            "head:openapi_to_mcp/templates/package.json.j2": '"node": ">=24"\n',
        },
    )

    result = release_policy.analyze_changes("base", "head")

    assert result["minimum"] == "breaking"
    assert "CLI command removed: diff" in result["reasons"]
    assert "generated Node floor increased: 22 to 24" in result["reasons"]


def test_analyze_changes_never_treats_public_code_as_no_release(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _stub_git(
        monkeypatch,
        "M\topenapi_to_mcp/cli.py\nM\topenapi_to_mcp/templates/package.json.j2\n",
        {
            "base:openapi_to_mcp/cli.py": "cli.add_command(generate)\n",
            "head:openapi_to_mcp/cli.py": "cli.add_command(generate)\n# bug fix\n",
            "base:openapi_to_mcp/templates/package.json.j2": '"node": ">=22"\n',
            "head:openapi_to_mcp/templates/package.json.j2": '"node": ">=22"\n"axios": "^2"\n',
        },
    )

    result = release_policy.analyze_changes("base", "head")

    assert result["minimum"] == "patch"
    assert "CLI implementation changed" in result["reasons"]
    assert "generated runtime package changed" in result["reasons"]


def test_analyze_changes_detects_removed_custom_tool_abi(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    path = "openapi_to_mcp/templates/src/runtime/generated.ts.j2"
    _stub_git(
        monkeypatch,
        f"M\t{path}\n",
        {
            f"base:{path}": "export interface CustomToolDefinition {}\n",
            f"head:{path}": "export interface ToolRuntimeMetadata {}\n",
        },
    )

    result = release_policy.analyze_changes("base", "head")

    assert result["minimum"] == "breaking"
    assert "custom-tool ABI removed: CustomToolDefinition" in result["reasons"]


def _stub_git(
    monkeypatch: pytest.MonkeyPatch, diff_output: str, files: dict[str, str]
) -> None:
    def fake_git_output(arguments: list[str]) -> str:
        if arguments[:2] == ["diff", "--name-status"]:
            return diff_output
        key = arguments[-1]
        if key in files:
            return files[key]
        raise AssertionError(f"Unexpected git request: {arguments}")

    monkeypatch.setattr(release_policy_changes, "_git_output", fake_git_output)


def _pyproject(dependencies: str) -> str:
    return (
        "[project]\n"
        'name = "openapi-to-mcp-cli"\n'
        'version = "0.9.1"\n'
        'requires-python = ">=3.14"\n'
        f"{dependencies}\n"
    )


def _lock(
    requests_version: str, urllib3_version: str, *, ruff_version: str = "1.0"
) -> str:
    return "\n".join(
        [
            "version = 1",
            "",
            "[[package]]",
            'name = "openapi-to-mcp-cli"',
            'version = "0.9.1"',
            'dependencies = [{ name = "requests" }]',
            "",
            "[package.dev-dependencies]",
            'dev = [{ name = "ruff" }]',
            "",
            "[[package]]",
            'name = "requests"',
            f'version = "{requests_version}"',
            'dependencies = [{ name = "urllib3" }]',
            "",
            "[[package]]",
            'name = "urllib3"',
            f'version = "{urllib3_version}"',
            "",
            "[[package]]",
            'name = "ruff"',
            f'version = "{ruff_version}"',
            "",
        ]
    )


def test_python_minor_floor_increase_is_breaking() -> None:
    result = project_impacts(
        '[project]\nrequires-python=">=3.14"', '[project]\nrequires-python=">=3.15"'
    )
    assert ("breaking", "Python floor increased") in result


def test_release_configuration_does_not_change_product_impact(monkeypatch) -> None:
    _stub_git(
        monkeypatch,
        "A\trelease-please-config.json\nA\t.release-please-manifest.json\n",
        {},
    )
    assert release_policy.analyze_changes("base", "head")["minimum"] == "none"


def test_migration_notes_cover_the_reviewed_squash_change() -> None:
    message = "feat!: update public configuration\n\nfix: preserve runtime behavior\n\nMigration: rename the configuration key."
    assert release_policy.parse_intent(message)["impact"] == "breaking"


def test_empty_migration_notes_are_not_release_evidence() -> None:
    with pytest.raises(ValueError, match="migration notes"):
        release_policy.parse_intent("feat!: change configuration\n\nMigration:  \n")
