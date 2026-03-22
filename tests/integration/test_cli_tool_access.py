from __future__ import annotations

from typing import TYPE_CHECKING

from openapi_to_mcp.cli import cli

if TYPE_CHECKING:
    from pathlib import Path

    from click.testing import CliRunner


def test_generate_emits_tool_access_runtime_wiring(
    runner: CliRunner, tmp_path: Path
) -> None:
    output_dir = tmp_path / "generated-access"

    result = runner.invoke(
        cli,
        [
            "generate",
            "--openapi-json",
            "tests/resources/test_openapi.yaml",
            "--output-dir",
            str(output_dir),
            "--transport",
            "streamable-http",
        ],
    )

    assert result.exit_code == 0
    assert (output_dir / "src" / "runtime" / "request_context.ts").exists()
    assert (output_dir / "src" / "runtime" / "tool_access.ts").exists()
    assert (output_dir / "src" / "runtime" / "http_transport.ts").exists()

    env_example = (output_dir / ".env.example").read_text(encoding="utf-8")
    server_source = (output_dir / "src" / "server.ts").read_text(encoding="utf-8")
    transport_source = (output_dir / "src" / "transport.ts").read_text(encoding="utf-8")
    config_source = (output_dir / "src" / "runtime" / "config.ts").read_text(
        encoding="utf-8"
    )
    access_source = (output_dir / "src" / "runtime" / "tool_access.ts").read_text(
        encoding="utf-8"
    )

    assert "MCP_TOOL_ACCESS_MODE=off" in env_example
    assert "MCP_TOOL_ACCESS_DEFAULT=allow" in env_example
    assert "MCP_TOOL_IDENTITY_HEADER=" in env_example
    assert "MCP_TOOL_ALLOWLISTS=" in env_example
    assert "filterToolsForCaller(this.allTools)" in server_source
    assert "tool_execution_denied" in server_source
    assert "error.meta.source !== 'auth'" in server_source
    assert "withRequestCallerContext" in transport_source
    assert "MCP_TOOL_ACCESS_MODE" in config_source
    assert "MCP_TOOL_ALLOWLISTS must be valid JSON." in access_source
