"""Basic security metadata agrees across generation and doctor."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

import pytest

from openapi_to_mcp.cli import cli
from openapi_to_mcp.common.tool_runtime import derive_auth_env_vars
from tests.integration.basic_auth_support import (
    BASIC_SCHEME,
    PASSWORD_ENV,
    USERNAME_ENV,
    basic_spec,
    generate_basic_project,
)

if TYPE_CHECKING:
    from pathlib import Path

    from click.testing import CliRunner


def test_basic_env_names_are_normalized_and_deduplicated() -> None:
    metadata = {"securitySchemes": basic_spec()["components"]["securitySchemes"]}
    assert derive_auth_env_vars({"one": metadata, "two": metadata}) == [
        PASSWORD_ENV,
        USERNAME_ENV,
        "AUTH_BEARER_TOKEN",
        "AUTH_EXTRAKEY_API_KEY",
    ]


@pytest.mark.parametrize("scope", ["global", "operation"])
def test_doctor_accepts_basic_without_runtime_credentials(
    runner: CliRunner, tmp_path: Path, scope: str
) -> None:
    spec = basic_spec()
    if scope == "operation":
        requirement = spec.pop("security")
        spec["paths"]["/inherited"]["get"]["security"] = requirement
    path = tmp_path / "basic.json"
    path.write_text(json.dumps(spec), encoding="utf-8")

    result = runner.invoke(cli, ["doctor", "-o", str(path)])

    assert result.exit_code == 0, result.output


def test_generated_basic_env_and_public_tools(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv(USERNAME_ENV, "generation-user-secret")
    monkeypatch.setenv(PASSWORD_ENV, "generation-password-secret")
    output = generate_basic_project(tmp_path / "generated")
    env = (output / ".env.example").read_text()
    assert f"{USERNAME_ENV}=\n" in env
    assert f"{PASSWORD_ENV}=\n" in env
    runtime = (output / "src/runtime/generated.ts").read_text()
    public_tools = runtime.split("export const toolRuntimeData")[0]
    assert BASIC_SCHEME not in public_tools
    for path in output.rglob("*"):
        if path.is_file():
            contents = path.read_text()
            assert "generation-user-secret" not in contents
            assert "generation-password-secret" not in contents
