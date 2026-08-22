from __future__ import annotations

from typing import TYPE_CHECKING

from openapi_to_mcp.cli import cli

if TYPE_CHECKING:
    from pathlib import Path

    from click.testing import CliRunner


def _runtime_source(output_dir: Path, name: str) -> str:
    return (output_dir / "src" / "runtime" / name).read_text(encoding="utf-8")


def test_generate_emits_observability_runtime_wiring(
    runner: CliRunner, tmp_path: Path
) -> None:
    output_dir = tmp_path / "generated-observability"

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
    observability_source = _runtime_source(output_dir, "observability.ts")
    auth_source = _runtime_source(output_dir, "auth.ts")
    executor_source = _runtime_source(output_dir, "executor.ts")
    executor_support_source = _runtime_source(output_dir, "executor_support.ts")
    request_source = _runtime_source(output_dir, "request.ts")
    response_source = _runtime_source(output_dir, "response.ts")
    errors_source = _runtime_source(output_dir, "errors.ts")

    assert "randomUUID" in observability_source
    assert "JSON.stringify" in observability_source
    assert "stdout stays reserved for MCP messages" in observability_source
    assert "unsupported http scheme:" in auth_source
    assert "X-Request-Id" in request_source
    assert "prepareRequestContext" in executor_source
    assert "tool_execution_started" in executor_support_source
    assert "tool_execution_cache_hit" in executor_support_source
    assert "tool_execution_succeeded" in executor_support_source
    assert "tool_execution_failed" in executor_support_source
    assert "instanceof ToolExecutionError" in executor_support_source
    assert "timeout: TOOL_TIMEOUT_MS" not in executor_source
    assert "_meta: { requestId }" in response_source
    assert "      meta: { requestId }," not in response_source
    assert "_meta: { requestId, error: error.meta }" in errors_source
    assert "    meta: { requestId, error: error.meta }," not in errors_source
