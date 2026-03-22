from __future__ import annotations

from typing import TYPE_CHECKING

from openapi_to_mcp.cli import cli

if TYPE_CHECKING:
    from pathlib import Path

    from click.testing import CliRunner


def test_generate_emits_audit_runtime_files_and_hooks(
    runner: CliRunner, tmp_path: Path
) -> None:
    output_dir = tmp_path / "generated-audit"

    result = runner.invoke(
        cli,
        [
            "generate",
            "--openapi-json",
            "tests/resources/audit_openapi.yaml",
            "--output-dir",
            str(output_dir),
            "--transport",
            "streamable-http",
        ],
    )

    assert result.exit_code == 0
    assert (output_dir / "src" / "runtime" / "audit.ts").exists()
    assert (output_dir / "src" / "runtime" / "redaction.ts").exists()

    env_example = (output_dir / ".env.example").read_text(encoding="utf-8")
    config_source = (output_dir / "src" / "runtime" / "config.ts").read_text(
        encoding="utf-8"
    )
    executor_source = (output_dir / "src" / "runtime" / "executor.ts").read_text(
        encoding="utf-8"
    )
    executor_support_source = (
        output_dir / "src" / "runtime" / "executor_support.ts"
    ).read_text(encoding="utf-8")
    audit_source = (output_dir / "src" / "runtime" / "audit.ts").read_text(
        encoding="utf-8"
    )
    redaction_source = (output_dir / "src" / "runtime" / "redaction.ts").read_text(
        encoding="utf-8"
    )

    assert "MCP_AUDIT_MODE=off" in env_example
    assert "MCP_AUDIT_REDACT_HEADERS=" in env_example
    assert "MCP_AUDIT_REDACT_REQUEST_BODY_PATHS=" in env_example
    assert "MCP_AUDIT_MODE" in config_source
    assert (output_dir / "src" / "runtime" / "executor_support.ts").exists()
    assert "emitRequestAudit" in executor_source
    assert "handleExecutionError" in executor_source
    assert "buildFailureAuditResponse" in executor_support_source
    assert "tool_audit_request" in audit_source
    assert "tool_audit_response" in audit_source
    assert "requestContext.sensitiveCookieNames" in audit_source
    assert "cacheHit: response.cacheHit === true" in audit_source
    assert "if (rest.length === 0)" in redaction_source
    assert "target[index] = REDACTED_VALUE" in redaction_source
