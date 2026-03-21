from __future__ import annotations

from typing import TYPE_CHECKING

from openapi_to_mcp.cli import cli

if TYPE_CHECKING:
    from pathlib import Path

    from click.testing import CliRunner


def test_generate_emits_performance_runtime_files_and_env_defaults(
    runner: CliRunner, tmp_path: Path
) -> None:
    output_dir = tmp_path / "generated"

    result = runner.invoke(
        cli,
        [
            "generate",
            "--openapi-json",
            "tests/resources/test_openapi.yaml",
            "--output-dir",
            str(output_dir),
            "--transport",
            "stdio",
        ],
    )

    assert result.exit_code == 0
    assert (output_dir / "src" / "runtime" / "cache.ts").exists()
    assert (output_dir / "src" / "runtime" / "rate_limit.ts").exists()
    assert (output_dir / "src" / "runtime" / "request.ts").exists()

    env_example = (output_dir / ".env.example").read_text(encoding="utf-8")
    assert "MCP_CACHE_TTL_MS=0" in env_example
    assert "MCP_RATE_LIMIT_PER_MINUTE=0" in env_example
