from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from click.testing import CliRunner

from openapi_to_mcp.cli import cli

if TYPE_CHECKING:
    from pathlib import Path

    from pytest_mock import MockerFixture


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


def test_run_applies_cache_and_rate_limit_overrides(
    runner: CliRunner, tmp_path: Path, mocker: MockerFixture
) -> None:
    output_dir = tmp_path / "generated"
    subprocess_run = mocker.patch("openapi_to_mcp.commands.run_support.subprocess.run")
    mocker.patch(
        "openapi_to_mcp.commands.run_support.shutil.which", return_value="/usr/bin/tool"
    )
    _mock_generation_output(mocker, output_dir)

    result = runner.invoke(
        cli,
        [
            "run",
            "--openapi-json",
            str(tmp_path / "openapi.yaml"),
            "--output-dir",
            str(output_dir),
            "--cache-ttl-ms",
            "60000",
            "--cache-max-entries",
            "512",
            "--rate-limit-per-minute",
            "30",
        ],
    )

    assert result.exit_code == 0
    env_contents = (output_dir / ".env").read_text(encoding="utf-8")
    assert "MCP_CACHE_TTL_MS=60000" in env_contents
    assert "MCP_CACHE_MAX_ENTRIES=512" in env_contents
    assert "MCP_RATE_LIMIT_PER_MINUTE=30" in env_contents
    assert subprocess_run.call_args_list[0].kwargs["env"]["MCP_CACHE_TTL_MS"] == "60000"
    assert (
        subprocess_run.call_args_list[0].kwargs["env"]["MCP_CACHE_MAX_ENTRIES"] == "512"
    )
    assert (
        subprocess_run.call_args_list[0].kwargs["env"]["MCP_RATE_LIMIT_PER_MINUTE"]
        == "30"
    )


def test_run_explicit_zero_performance_overrides_beat_env_source(
    runner: CliRunner, tmp_path: Path, mocker: MockerFixture
) -> None:
    output_dir = tmp_path / "generated"
    subprocess_run = mocker.patch("openapi_to_mcp.commands.run_support.subprocess.run")
    mocker.patch(
        "openapi_to_mcp.commands.run_support.shutil.which", return_value="/usr/bin/tool"
    )
    _mock_generation_output(mocker, output_dir)

    result = runner.invoke(
        cli,
        [
            "run",
            "--openapi-json",
            str(tmp_path / "openapi.yaml"),
            "--output-dir",
            str(output_dir),
            "--env-source",
            '{"MCP_CACHE_TTL_MS":"5000","MCP_CACHE_MAX_ENTRIES":"250","MCP_RATE_LIMIT_PER_MINUTE":"10"}',
            "--cache-ttl-ms",
            "0",
            "--cache-max-entries",
            "50",
            "--rate-limit-per-minute",
            "0",
        ],
    )

    assert result.exit_code == 0
    env_contents = (output_dir / ".env").read_text(encoding="utf-8")
    assert "MCP_CACHE_TTL_MS=0" in env_contents
    assert "MCP_CACHE_MAX_ENTRIES=50" in env_contents
    assert "MCP_RATE_LIMIT_PER_MINUTE=0" in env_contents
    assert subprocess_run.call_args_list[0].kwargs["env"]["MCP_CACHE_TTL_MS"] == "0"
    assert (
        subprocess_run.call_args_list[0].kwargs["env"]["MCP_CACHE_MAX_ENTRIES"] == "50"
    )
    assert (
        subprocess_run.call_args_list[0].kwargs["env"]["MCP_RATE_LIMIT_PER_MINUTE"]
        == "0"
    )


def test_run_writes_performance_preset_and_explicit_override(
    runner: CliRunner, tmp_path: Path, mocker: MockerFixture
) -> None:
    output_dir = tmp_path / "generated"
    subprocess_run = mocker.patch("openapi_to_mcp.commands.run_support.subprocess.run")
    mocker.patch(
        "openapi_to_mcp.commands.run_support.shutil.which", return_value="/usr/bin/tool"
    )
    _mock_generation_output(mocker, output_dir)

    result = runner.invoke(
        cli,
        [
            "run",
            "--openapi-json",
            str(tmp_path / "openapi.yaml"),
            "--output-dir",
            str(output_dir),
            "--performance-preset",
            "balanced",
            "--cache-ttl-ms",
            "0",
        ],
    )

    assert result.exit_code == 0
    env_contents = (output_dir / ".env").read_text(encoding="utf-8")
    assert "MCP_PERFORMANCE_PRESET=balanced" in env_contents
    assert "MCP_CACHE_TTL_MS=0" in env_contents
    assert subprocess_run.call_args_list[0].kwargs["env"]["MCP_PERFORMANCE_PRESET"] == (
        "balanced"
    )
    assert subprocess_run.call_args_list[0].kwargs["env"]["MCP_CACHE_TTL_MS"] == "0"


def test_run_preset_is_not_shadowed_by_blank_generated_env_values(
    runner: CliRunner,
    tmp_path: Path,
    mocker: MockerFixture,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    output_dir = tmp_path / "generated"
    subprocess_run = mocker.patch("openapi_to_mcp.commands.run_support.subprocess.run")
    mocker.patch(
        "openapi_to_mcp.commands.run_support.shutil.which", return_value="/usr/bin/tool"
    )
    for env_name in (
        "MCP_MAX_CONCURRENCY",
        "MCP_CACHE_TTL_MS",
        "MCP_CACHE_MAX_ENTRIES",
        "MCP_RATE_LIMIT_PER_MINUTE",
        "MCP_RETRY_MAX_RETRIES",
        "MCP_RETRY_BUDGET_PER_MINUTE",
        "MCP_CIRCUIT_BREAKER_FAILURE_THRESHOLD",
        "MCP_CIRCUIT_BREAKER_COOLDOWN_MS",
    ):
        monkeypatch.delenv(env_name, raising=False)
    env_example = """TARGET_API_BASE_URL=https://example.com
MCP_PERFORMANCE_PRESET=off
MCP_MAX_CONCURRENCY=
MCP_CACHE_TTL_MS=
MCP_CACHE_MAX_ENTRIES=
MCP_RATE_LIMIT_PER_MINUTE=
MCP_RETRY_MAX_RETRIES=
MCP_RETRY_BUDGET_PER_MINUTE=
MCP_CIRCUIT_BREAKER_FAILURE_THRESHOLD=
MCP_CIRCUIT_BREAKER_COOLDOWN_MS=
"""
    _mock_generation_output(
        mocker,
        output_dir,
        env_example,
    )

    result = runner.invoke(
        cli,
        [
            "run",
            "--openapi-json",
            str(tmp_path / "openapi.yaml"),
            "--output-dir",
            str(output_dir),
            "--performance-preset",
            "balanced",
        ],
    )

    assert result.exit_code == 0
    env_contents = (output_dir / ".env").read_text(encoding="utf-8")
    assert "MCP_PERFORMANCE_PRESET=balanced" in env_contents
    assert "MCP_MAX_CONCURRENCY=" in env_contents
    assert "MCP_CACHE_TTL_MS=" in env_contents
    runtime_env = subprocess_run.call_args_list[0].kwargs["env"]
    assert runtime_env["MCP_PERFORMANCE_PRESET"] == "balanced"
    assert "MCP_MAX_CONCURRENCY" not in runtime_env
    assert "MCP_CACHE_TTL_MS" not in runtime_env


def _mock_generation_output(
    mocker: MockerFixture, output_dir: Path, env_example: str | None = None
) -> None:
    def fake_generate_project(**_: object) -> None:
        output_dir.mkdir(parents=True, exist_ok=True)
        (output_dir / ".env.example").write_text(
            env_example or "TARGET_API_BASE_URL=https://example.com\n",
            encoding="utf-8",
        )

    mocker.patch(
        "openapi_to_mcp.commands.run.generate_project",
        side_effect=fake_generate_project,
    )
