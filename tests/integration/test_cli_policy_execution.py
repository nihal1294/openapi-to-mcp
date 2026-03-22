from __future__ import annotations

import json
import re
from typing import TYPE_CHECKING, Any

import yaml

from openapi_to_mcp.cli import cli

if TYPE_CHECKING:
    from pathlib import Path

    from click.testing import CliRunner


def _normalize_output(text: str) -> str:
    return " ".join(re.sub(r"\x1b\[[0-9;]*[A-Za-z]", "", text).split())


def test_generate_uses_policy_file_for_rename_auth_and_execution(
    runner: CliRunner, tmp_path: Path
) -> None:
    spec_path = _write_get_spec(tmp_path / "openapi.json")
    config_path = _write_policy(
        tmp_path / "mcpgen.yaml",
        {
            "tools": {"rename": {"operations": {"GET /test": "renamedTestTool"}}},
            "auth": {
                "operations": {
                    "GET /test": {
                        "security": [{"bearerAuth": []}],
                        "security_schemes": {
                            "bearerAuth": {"type": "http", "scheme": "bearer"}
                        },
                    }
                }
            },
            "execution": {
                "operations": {
                    "GET /test": {
                        "max_concurrency": 3,
                        "timeout_ms": 12000,
                        "cache_ttl_ms": 60000,
                        "rate_limit_per_minute": 30,
                        "retry_max_retries": 2,
                        "retry_budget_per_minute": 10,
                        "circuit_breaker_failure_threshold": 4,
                        "circuit_breaker_cooldown_ms": 15000,
                    }
                }
            },
        },
    )
    output_dir = tmp_path / "generated"

    result = runner.invoke(
        cli,
        [
            "generate",
            "--openapi-json",
            str(spec_path),
            "--config",
            str(config_path),
            "--output-dir",
            str(output_dir),
        ],
    )

    assert result.exit_code == 0
    generated_source = (output_dir / "src" / "runtime" / "generated.ts").read_text(
        encoding="utf-8"
    )
    env_example = (output_dir / ".env.example").read_text(encoding="utf-8")
    assert '"renamedTestTool"' in generated_source
    assert '"security": [' in generated_source
    assert '"securitySchemes": {' in generated_source
    assert '"execution": {' in generated_source
    assert '"maxConcurrency": 3' in generated_source
    assert '"timeoutMs": 12000' in generated_source
    assert '"cacheTtlMs": 60000' in generated_source
    assert '"rateLimitPerMinute": 30' in generated_source
    assert '"retryMaxRetries": 2' in generated_source
    assert '"retryBudgetPerMinute": 10' in generated_source
    assert '"circuitBreakerFailureThreshold": 4' in generated_source
    assert '"circuitBreakerCooldownMs": 15000' in generated_source
    assert "AUTH_BEARERAUTH_TOKEN=" in env_example


def test_generate_rejects_unsafe_policy_resilience_override(
    runner: CliRunner, tmp_path: Path
) -> None:
    spec_path = _write_post_spec(tmp_path / "openapi.json")
    config_path = _write_policy(
        tmp_path / "mcpgen.yaml",
        {
            "execution": {
                "operations": {
                    "POST /test": {
                        "cache_ttl_ms": 1000,
                        "retry_max_retries": 2,
                        "circuit_breaker_failure_threshold": 3,
                    }
                }
            }
        },
    )
    output_dir = tmp_path / "generated"

    result = runner.invoke(
        cli,
        [
            "generate",
            "--openapi-json",
            str(spec_path),
            "--config",
            str(config_path),
            "--output-dir",
            str(output_dir),
        ],
    )

    assert result.exit_code != 0
    assert "safe HTTP method" in _normalize_output(result.output)
    assert "Traceback" not in result.output


def _write_get_spec(path: Path) -> Path:
    return _write_spec(path, "get")


def _write_post_spec(path: Path) -> Path:
    return _write_spec(path, "post")


def _write_spec(path: Path, method: str) -> Path:
    payload = {
        "openapi": "3.0.0",
        "info": {"title": "Policy Test", "version": "1.0.0"},
        "servers": [{"url": "https://example.com"}],
        "paths": {
            "/test": {
                method: {
                    "operationId": "testConversionTool",
                    "responses": {"200": {"description": "OK"}},
                }
            }
        },
    }
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def _write_policy(path: Path, payload: dict[str, Any]) -> Path:
    path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")
    return path
