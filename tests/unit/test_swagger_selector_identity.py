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
