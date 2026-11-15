"""Swagger policy selection agrees between source diagnostics and mapping."""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING

import pytest
from openapi_spec_validator import validate

from openapi_to_mcp.cli import cli
from openapi_to_mcp.common.operations import iter_operations
from openapi_to_mcp.doctor import DoctorAnalyzer
from openapi_to_mcp.mapping import Mapper
from openapi_to_mcp.policy import apply_policy
from openapi_to_mcp.policy.models import AuthOverride, PolicyConfig, SelectorSet

if TYPE_CHECKING:
    from click.testing import CliRunner


def _spec() -> dict:
    response = {"200": {"description": "OK"}}
    return {
        "swagger": "2.0",
        "host": "example.com",
        "info": {"title": "Selection", "version": "1.0.0"},
        "paths": {
            "/a-b": {
                "get": {
                    "parameters": [
                        {"name": "payload", "in": "body", "schema": {"type": "object"}}
                    ],
                    "responses": response,
                }
            },
            "/a_b": {"get": {"responses": response}},
            "/a.b": {"get": {"responses": response}},
        },
    }


@pytest.mark.parametrize(
    ("name", "expected", "diagnosed"),
    [("get_a_b", ["/a-b", "/a_b"], True), ("get_a_b_2", ["/a_b"], False)],
)
def test_swagger_selection_matches_mapper_and_cli(
    runner: CliRunner,
    tmp_path: Path,
    name: str,
    expected: list[str],
    *,
    diagnosed: bool,
) -> None:
    spec = _spec()
    validate(spec)
    policy = PolicyConfig(
        source_path=Path("mcpgen.yaml"), include=SelectorSet(names=frozenset({name}))
    )
    analyzer = DoctorAnalyzer(spec, policy)
    assert [
        op.path for op in analyzer._selected_operations(iter_operations(spec))
    ] == expected
    selected = apply_policy(
        Mapper(spec, strict=False, policy_config=policy).map_tools(), policy
    )
    assert [tool["_original_path"] for tool in selected] == [expected[-1]]
    source = tmp_path / "spec.json"
    source.write_text(json.dumps(spec), encoding="utf-8")
    config = tmp_path / "mcpgen.yaml"
    config.write_text(f"tools:\n  include:\n    names: [{name}]\n", encoding="utf-8")
    result = runner.invoke(
        cli, ["doctor", "-o", str(source), "--config", str(config), "--format", "json"]
    )
    issues = json.loads(result.output[result.output.index("{\n") :])["issues"]
    assert (
        any(
            issue["code"] == "unsupported_swagger_construct"
            and issue["location"].startswith("paths./a-b")
            for issue in issues
        )
    ) is diagnosed
    if diagnosed:
        assert result.exit_code == 3
    output = tmp_path / "generated"
    generated = runner.invoke(
        cli,
        [
            "generate",
            "-o",
            str(source),
            "--config",
            str(config),
            "--no-strict",
            "-d",
            str(output),
        ],
    )
    assert generated.exit_code == 0, generated.output
    runtime = (output / "src/runtime/generated.ts").read_text(encoding="utf-8")
    assert f'"path": "{expected[-1]}"' in runtime
    assert f'"name": "{name}"' in runtime


def test_auth_repaired_swagger_operation_still_reserves_name() -> None:
    spec = _spec()
    spec["paths"]["/a-b"]["get"].pop("parameters")
    spec["securityDefinitions"] = {
        "key": {"type": "apiKey", "name": "key", "in": "header"}
    }
    spec["paths"]["/a-b"]["get"]["security"] = [{"key": []}]
    policy = PolicyConfig(
        source_path=Path("policy"),
        include=SelectorSet(names=frozenset({"get_a_b", "get_a_b_2"})),
        auth_operations={"GET /a-b": AuthOverride(security=[])},
    )
    mapped = apply_policy(
        Mapper(spec, strict=False, policy_config=policy).map_tools(), policy
    )
    selected = DoctorAnalyzer(spec, policy)._selected_operations(iter_operations(spec))
    assert [tool["_original_path"] for tool in mapped] == ["/a-b", "/a_b"]
    assert [op.path for op in selected] == ["/a-b", "/a_b"]


@pytest.mark.parametrize(
    ("name", "include_first", "expected"),
    [
        ("get_a_b", True, "/a_b"),
        ("get_a_b_2", True, "/a.b"),
        ("get_a_b_2", False, "/a_b"),
    ],
)
def test_protocol_selection_matches_generation(
    runner: CliRunner, tmp_path: Path, name: str, *, include_first: bool, expected: str
) -> None:
    import yaml  # noqa: PLC0415

    spec = _spec()
    operation = spec["paths"]["/a-b"]["get"]
    operation.pop("parameters")
    operation["schemes"] = ["http"]
    validate(spec)
    payload = {
        "tools": {
            "include": {
                "names": [name],
                "operations": ["GET /a-b"] if include_first else [],
            }
        }
    }
    source = tmp_path / "spec.json"
    source.write_text(json.dumps(spec), encoding="utf-8")
    config = tmp_path / "policy.yaml"
    config.write_text(yaml.safe_dump(payload), encoding="utf-8")
    from openapi_to_mcp.policy.loader import load_policy_config  # noqa: PLC0415

    policy = load_policy_config(str(config))
    assert policy is not None
    selected = DoctorAnalyzer(spec, policy)._selected_operations(iter_operations(spec))
    assert [op.path for op in selected] == (
        ["/a-b", expected] if include_first else [expected]
    )
    mapped = apply_policy(
        Mapper(spec, strict=False, policy_config=policy).map_tools(), policy
    )
    assert [tool["_original_path"] for tool in mapped] == [expected]
    result = runner.invoke(
        cli, ["doctor", "-o", str(source), "--config", str(config), "--format", "json"]
    )
    assert ("unsupported_swagger_construct" in result.output) is include_first
    if include_first:
        assert result.exit_code == 3
    output = tmp_path / "generated"
    generated = runner.invoke(
        cli,
        [
            "generate",
            "-o",
            str(source),
            "--config",
            str(config),
            "--no-strict",
            "-d",
            str(output),
        ],
    )
    assert generated.exit_code == 0, generated.output
    assert f'"path": "{expected}"' in (output / "src/runtime/generated.ts").read_text(
        encoding="utf-8"
    )


@pytest.mark.parametrize(
    "repair", ["none", "renamed", "original_wins", "operation_wins"]
)
def test_security_override_name_preview(repair: str) -> None:
    spec = _spec()
    spec["paths"]["/a-b"]["get"].pop("parameters")
    spec["securityDefinitions"] = {
        "key": {"type": "apiKey", "name": "key", "in": "header"}
    }
    spec["paths"]["/a-b"]["get"]["security"] = [{"key": []}]
    policy = PolicyConfig(
        source_path=Path("policy"),
        include=SelectorSet(
            operations=frozenset({"GET /a-b"}), names=frozenset({"get_a_b_2"})
        ),
        rename_operations={"GET /a-b": "renamed"},
        auth_names=(
            {
                "renamed": AuthOverride(security=[]),
                "get_a_b": AuthOverride(security=[{"missing": []}]),
            }
            if repair == "original_wins"
            else {"renamed": AuthOverride(security=[])}
            if repair != "none"
            else {}
        ),
        auth_operations={"GET /a-b": AuthOverride(security=[{"missing": []}])}
        if repair == "operation_wins"
        else {},
    )
    expected = "/a_b" if repair == "renamed" else "/a.b"
    selected = DoctorAnalyzer(spec, policy)._selected_operations(iter_operations(spec))
    assert [op.path for op in selected] == ["/a-b", expected]
    mapped = apply_policy(
        Mapper(spec, strict=False, policy_config=policy).map_tools(), policy
    )
    assert [tool["_original_path"] for tool in mapped] == (
        ["/a-b", expected] if repair == "renamed" else [expected]
    )


def test_doctor_does_not_validate_unrelated_execution_override() -> None:
    from openapi_to_mcp.policy.models import ExecutionOverride  # noqa: PLC0415

    spec = _spec()
    spec["paths"]["/a-b"] = {
        "post": {"schemes": ["http"], "responses": {"200": {"description": "OK"}}}
    }
    policy = PolicyConfig(
        source_path=Path("policy"),
        execution_operations={"POST /a-b": ExecutionOverride(cache_ttl_ms=5)},
    )
    report = DoctorAnalyzer(spec, policy).analyze("inline")
    assert any(issue.code == "unsupported_swagger_construct" for issue in report.issues)
