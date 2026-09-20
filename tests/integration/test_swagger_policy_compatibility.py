"""Swagger compatibility checks respect the effective generation policy."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

import pytest
import yaml

from openapi_to_mcp.cli import cli

if TYPE_CHECKING:
    from pathlib import Path

    from click.testing import CliRunner


@pytest.mark.parametrize("strict", [True, False])
@pytest.mark.parametrize(
    "policy",
    [
        {"auth": {"operations": {"GET /status": {"security": []}}}},
        {"auth": {"names": {"getStatus": {"security": []}}}},
        {
            "tools": {"rename": {"names": {"getStatus": "publicStatus"}}},
            "auth": {"names": {"publicStatus": {"security": []}}},
        },
    ],
)
def test_swagger_auth_policy_can_make_operation_public(
    runner: CliRunner, tmp_path: Path, policy: dict, *, strict: bool
) -> None:
    result = _generate(runner, tmp_path, policy, strict=strict)

    assert result.exit_code == 0, result.output
    report = json.loads((tmp_path / "output/generation_report.json").read_text())
    assert report["mapped_tools"] == 1
    assert report["skipped_operations"] == []
    runtime = (tmp_path / "output/src/runtime/generated.ts").read_text()
    assert '"security": []' in runtime


def test_swagger_auth_policy_can_supply_runtime_security(
    runner: CliRunner, tmp_path: Path
) -> None:
    policy = {
        "auth": {
            "operations": {
                "GET /status": {
                    "security": [{"Replacement": []}],
                    "security_schemes": {
                        "Replacement": {
                            "type": "apiKey",
                            "in": "header",
                            "name": "X-Key",
                        }
                    },
                }
            }
        }
    }

    result = _generate(runner, tmp_path, policy)

    assert result.exit_code == 0, result.output
    assert "AUTH_REPLACEMENT_API_KEY" in (tmp_path / "output/.env.example").read_text()


@pytest.mark.parametrize(
    "policy",
    [
        {"auth": {"operations": {"GET /other": {"security": []}}}},
        {"auth": {"operations": {"GET /status": {"security": [{"Missing": []}]}}}},
    ],
)
def test_swagger_unresolved_auth_still_fails(
    runner: CliRunner, tmp_path: Path, policy: dict
) -> None:
    result = _generate(runner, tmp_path, policy)

    assert result.exit_code != 0
    assert "unsupported Swagger 2" in result.output


def test_swagger_auth_policy_does_not_hide_unsupported_parameters(
    runner: CliRunner, tmp_path: Path
) -> None:
    spec = _spec()
    spec["paths"]["/status"]["get"]["parameters"] = [
        {"name": "limit", "in": "query", "type": "integer"}
    ]
    result = _generate(
        runner,
        tmp_path,
        {"auth": {"operations": {"GET /status": {"security": []}}}},
        spec=spec,
    )

    assert result.exit_code != 0
    assert "unsupported Swagger 2" in result.output


def _generate(runner, tmp_path, policy, *, strict=True, spec=None):
    spec_path = tmp_path / "swagger.json"
    policy_path = tmp_path / "mcpgen.yaml"
    spec_path.write_text(json.dumps(spec or _spec()))
    policy_path.write_text(yaml.safe_dump(policy))
    return runner.invoke(
        cli,
        [
            "generate",
            "--openapi-json",
            str(spec_path),
            "--config",
            str(policy_path),
            "--output-dir",
            str(tmp_path / "output"),
            "--strict" if strict else "--no-strict",
        ],
    )


def _spec() -> dict:
    return {
        "swagger": "2.0",
        "info": {"title": "Policy compatibility", "version": "1.0"},
        "host": "api.example.com",
        "securityDefinitions": {
            "Legacy": {"type": "apiKey", "in": "header", "name": "X-Key"}
        },
        "security": [{"Legacy": []}],
        "paths": {
            "/status": {
                "get": {
                    "operationId": "getStatus",
                    "responses": {"200": {"description": "OK"}},
                }
            }
        },
    }
