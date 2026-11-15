from __future__ import annotations

import json
import re
from copy import deepcopy
from typing import TYPE_CHECKING

import pytest
import yaml

from openapi_to_mcp.cli import cli
from openapi_to_mcp.common.exceptions import GenerationError, PolicyConfigError
from openapi_to_mcp.mapping.tool_metadata import (
    apply_description_mode,
    validate_tool_names,
)
from openapi_to_mcp.policy.applier import apply_policy
from openapi_to_mcp.policy.parser import parse_policy_config

if TYPE_CHECKING:
    from pathlib import Path

    from click.testing import CliRunner


def _spec(path: Path, name: str = "bad name", tag: str = "Pets") -> Path:
    path.write_text(
        json.dumps(
            {
                "openapi": "3.0.0",
                "info": {"title": "Test", "version": "1"},
                "paths": {
                    "/private": {
                        "get": {
                            "operationId": name,
                            "summary": "Untrusted summary",
                            "tags": [tag],
                            "responses": {"200": {"description": "OK"}},
                        }
                    }
                },
            }
        )
    )
    return path


def _invoke(runner: CliRunner, source: Path, output: Path, *args: str):
    return runner.invoke(cli, ["generate", "-o", str(source), "-d", str(output), *args])


def _tools(path: Path):
    source = (path / "src/runtime/generated.ts").read_text()
    return json.loads(
        re.search(
            r"export const tools = (\[.*?\]) as Tool\[\];", source, re.DOTALL
        ).group(1)
    )


def test_method_description_override_and_final_name_repair(
    runner: CliRunner, tmp_path: Path
) -> None:
    spec = _spec(tmp_path / "spec.json")
    policy = tmp_path / "policy.yaml"
    policy.write_text(
        yaml.safe_dump(
            {
                "generate": {
                    "tool_descriptions": "method",
                    "tool_name_policy": "validate",
                },
                "tools": {
                    "rename": {"operations": {"GET /private": "safe"}},
                    "descriptions": {"names": {"safe": "Explicit text"}},
                },
            }
        )
    )
    output = tmp_path / "out"
    result = _invoke(runner, spec, output, "--config", str(policy))
    assert result.exit_code == 0, result.output
    assert _tools(output)[0]["description"] == "Explicit text"
    assert _tools(output)[0]["name"] == "safe"
    report = json.loads((output / "generation_report.json").read_text())
    assert report["tool_descriptions"] == "method"
    assert report["tool_name_policy"] == "validate"


def test_method_and_name_validation(runner: CliRunner, tmp_path: Path) -> None:
    spec = _spec(tmp_path / "spec.json")
    failed = tmp_path / "failed"
    result = _invoke(runner, spec, failed, "--tool-name-policy", "validate")
    assert result.exit_code != 0
    assert "bad name" in result.output
    assert "GET /private" in result.output
    assert not failed.exists()
    output = tmp_path / "out"
    result = _invoke(runner, spec, output, "--tool-descriptions", "method")
    assert result.exit_code == 0, result.output
    assert _tools(output)[0]["description"] == "Perform an HTTP GET request."
    assert "bad name" in result.output
    assert json.loads((output / "generation_report.json").read_text())[
        "tool_name_warnings"
    ]


@pytest.mark.parametrize(
    "value",
    [
        None,
        [],
        {"unknown": {}},
        {"operations": None},
        {"names": {"x": ""}},
        {"names": {"x": 2}},
    ],
)
def test_descriptions_namespace_rejects_invalid(value: object, tmp_path: Path) -> None:
    with pytest.raises(PolicyConfigError):
        parse_policy_config(
            {"tools": {"descriptions": value}}, tmp_path / "policy.yaml"
        )


def test_cli_overrides_policy_and_preserves_default_description(
    runner: CliRunner, tmp_path: Path
) -> None:
    spec = _spec(tmp_path / "spec.json", "valid")
    policy = tmp_path / "policy.yaml"
    policy.write_text(
        yaml.safe_dump(
            {
                "generate": {
                    "tool_descriptions": "method",
                    "tool_name_policy": "validate",
                }
            }
        )
    )
    output = tmp_path / "out"
    result = _invoke(
        runner,
        spec,
        output,
        "--config",
        str(policy),
        "--tool-descriptions",
        "spec",
        "--tool-name-policy",
        "preserve",
    )
    assert result.exit_code == 0, result.output
    assert _tools(output)[0]["description"] == "Untrusted summary."
    report = json.loads((output / "generation_report.json").read_text())
    assert (report["tool_descriptions"], report["tool_name_policy"]) == (
        "spec",
        "preserve",
    )


def test_grouped_name_is_validated_after_grouping(
    runner: CliRunner, tmp_path: Path
) -> None:
    spec = _spec(tmp_path / "spec.json", "a" * 128)
    output = tmp_path / "out"
    result = _invoke(
        runner,
        spec,
        output,
        "--tool-grouping",
        "tag-prefix",
        "--tool-name-policy",
        "validate",
    )
    assert result.exit_code != 0
    assert "pets_" in result.output
    assert not output.exists()


def test_excluded_invalid_name_does_not_fail(runner: CliRunner, tmp_path: Path) -> None:
    spec = _spec(tmp_path / "spec.json", "valid")
    data = json.loads(spec.read_text())
    data["paths"]["/excluded"] = {
        "get": {"operationId": "bad name", "responses": {"200": {"description": "OK"}}}
    }
    spec.write_text(json.dumps(data))
    policy = tmp_path / "policy.yaml"
    policy.write_text(
        yaml.safe_dump({"tools": {"exclude": {"operations": ["GET /excluded"]}}})
    )
    result = _invoke(
        runner,
        spec,
        tmp_path / "out",
        "--config",
        str(policy),
        "--tool-name-policy",
        "validate",
    )
    assert result.exit_code == 0, result.output


@pytest.mark.parametrize(
    ("name", "valid"),
    [
        ("a" * 127, True),
        ("a" * 128, True),
        ("a" * 129, False),
        ("", False),
        ("ümlaut", False),
        ("bad\nname", False),
        ("valid_.-09", True),
    ],
)
def test_name_boundaries_and_escaped_diagnostics(name: str, valid: bool) -> None:  # noqa: FBT001

    tools = [{"name": name, "_original_method": "get", "_original_path": "/a\nb"}]
    warnings = validate_tool_names(tools, "preserve")
    assert bool(warnings) is not valid
    if not valid:
        with pytest.raises(GenerationError) as error:
            validate_tool_names(tools, "validate")
        assert json.dumps(name) in str(error.value)
        assert json.dumps("GET /a\nb") in str(error.value)


def test_description_mode_is_pure_and_override_precedence(tmp_path: Path) -> None:
    tools = [
        {
            "name": "original",
            "description": "Original",
            "_original_method": "get",
            "_original_path": "/private",
            "inputSchema": {"description": "Schema"},
        }
    ]
    original = deepcopy(tools)
    policy = parse_policy_config(
        {
            "tools": {
                "rename": {"names": {"original": "renamed"}},
                "descriptions": {
                    "operations": {"GET /private": "operation"},
                    "names": {
                        "original": "original override",
                        "renamed": "renamed override",
                    },
                },
            }
        },
        tmp_path / "policy.yaml",
    )
    result = apply_policy(apply_description_mode(tools, "method"), policy)
    assert result[0]["description"] == "operation"
    assert result[0]["inputSchema"]["description"] == "Schema"
    assert tools == original
    policy = parse_policy_config(
        {
            "tools": {
                "rename": {"names": {"original": "renamed"}},
                "descriptions": {
                    "names": {
                        "original": "original override",
                        "renamed": "renamed override",
                    }
                },
            }
        },
        tmp_path / "policy.yaml",
    )
    assert (
        apply_policy(apply_description_mode(tools, "method"), policy)[0]["description"]
        == "original override"
    )


def test_run_options_use_policy_and_cli_precedence(
    runner: CliRunner, tmp_path: Path, mocker
) -> None:
    spec = _spec(tmp_path / "spec.json", "valid")
    policy = tmp_path / "policy.yaml"
    policy.write_text(
        yaml.safe_dump(
            {"generate": {"tool_descriptions": "spec", "tool_name_policy": "validate"}}
        )
    )
    mocker.patch("openapi_to_mcp.commands.run.ensure_runtime_tools")
    mocker.patch("openapi_to_mcp.commands.run._execute_runtime")
    output = tmp_path / "out"
    result = runner.invoke(
        cli,
        [
            "run",
            "-o",
            str(spec),
            "-d",
            str(output),
            "--config",
            str(policy),
            "--tool-descriptions",
            "method",
            "--target-api-base-url",
            "https://example.com",
        ],
    )
    assert result.exit_code == 0, result.output
    assert _tools(output)[0]["description"] == "Perform an HTTP GET request."
    assert (
        json.loads((output / "generation_report.json").read_text())["tool_name_policy"]
        == "validate"
    )
