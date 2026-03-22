from __future__ import annotations

from typing import TYPE_CHECKING

from openapi_to_mcp.cli import cli
from openapi_to_mcp.common.performance_presets import PERFORMANCE_PRESETS

if TYPE_CHECKING:
    from pathlib import Path

    from click.testing import CliRunner


def test_generate_emits_performance_runtime_files_and_env_placeholders(
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
    assert (output_dir / "src" / "runtime" / "performance_preset.ts").exists()
    assert (output_dir / "src" / "runtime" / "rate_limit.ts").exists()
    assert (output_dir / "src" / "runtime" / "request.ts").exists()

    env_example = (output_dir / ".env.example").read_text(encoding="utf-8")
    preset_source = (
        output_dir / "src" / "runtime" / "performance_preset.ts"
    ).read_text(encoding="utf-8")
    assert "MCP_PERFORMANCE_PRESET=off" in env_example
    assert "MCP_MAX_CONCURRENCY=" in env_example
    assert "MCP_CACHE_TTL_MS=" in env_example
    assert "MCP_CACHE_MAX_ENTRIES=" in env_example
    assert "MCP_RATE_LIMIT_PER_MINUTE=" in env_example
    assert "MCP_MAX_CONCURRENCY=32" not in env_example
    assert "MCP_CACHE_TTL_MS=0" not in env_example
    assert "MCP_CACHE_MAX_ENTRIES=1000" not in env_example
    assert "MCP_RATE_LIMIT_PER_MINUTE=0" not in env_example
    assert (
        "Object.prototype.hasOwnProperty.call(PERFORMANCE_PRESETS, raw)"
        in preset_source
    )
    for preset in PERFORMANCE_PRESETS:
        assert f"'{preset.name}':" in preset_source
        assert f"cacheTtlMs: {preset.cache_ttl_ms}" in preset_source
        assert (
            f"circuitBreakerFailureThreshold: "
            f"{preset.circuit_breaker_failure_threshold}" in preset_source
        )
