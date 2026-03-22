from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from openapi_to_mcp.common.exceptions import PolicyConfigError
from openapi_to_mcp.policy.loader import load_policy_config

if TYPE_CHECKING:
    from pathlib import Path


def test_load_policy_config_parses_generation_and_tool_rules(tmp_path: Path) -> None:
    policy_path = tmp_path / "mcpgen.yaml"
    policy_path.write_text(
        """
        generate:
          transport: stdio
          runtime_validation: none
          tool_grouping: tag-prefix
        tools:
          include:
            operations: ["GET /pets"]
          rename:
            names:
              listPets: fetchPets
        auth:
          names:
            fetchPets:
              security: []
        execution:
          names:
            fetchPets:
              max_concurrency: 3
              timeout_ms: 12000
              cache_ttl_ms: 60000
              rate_limit_per_minute: 30
              retry_max_retries: 2
              retry_budget_per_minute: 10
              circuit_breaker_failure_threshold: 4
              circuit_breaker_cooldown_ms: 15000
        """,
        encoding="utf-8",
    )

    policy = load_policy_config(str(policy_path))

    assert policy is not None
    assert policy.generation.transport == "stdio"
    assert policy.generation.runtime_validation == "none"
    assert policy.generation.tool_grouping == "tag-prefix"
    assert policy.include.operations == frozenset({"GET /pets"})
    assert policy.rename_names == {"listPets": "fetchPets"}
    assert policy.auth_names["fetchPets"].security == []
    assert policy.execution_names["fetchPets"].max_concurrency == 3
    assert policy.execution_names["fetchPets"].timeout_ms == 12000
    assert policy.execution_names["fetchPets"].cache_ttl_ms == 60000
    assert policy.execution_names["fetchPets"].rate_limit_per_minute == 30
    assert policy.execution_names["fetchPets"].retry_max_retries == 2
    assert policy.execution_names["fetchPets"].retry_budget_per_minute == 10
    assert policy.execution_names["fetchPets"].circuit_breaker_failure_threshold == 4
    assert policy.execution_names["fetchPets"].circuit_breaker_cooldown_ms == 15000


def test_load_policy_config_autodiscovers_default_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    policy_path = tmp_path / "mcpgen.yml"
    policy_path.write_text("generate:\n  strict: false\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    policy = load_policy_config(None)

    assert policy is not None
    assert policy.source_path == policy_path
    assert policy.generation.strict is False


@pytest.mark.parametrize(
    ("payload", "message"),
    [
        ("tools:\n  include:\n    operations: broken\n", "tools.include.operations"),
        ("generate:\n  transport: http\n", "generate.transport"),
        ("execution:\n  names:\n    listPets:\n      timeout_ms: 0\n", "timeout_ms"),
        (
            "execution:\n  names:\n    listPets:\n      max_concurrency: true\n",
            "max_concurrency",
        ),
        (
            "execution:\n  names:\n    listPets:\n      cache_ttl_ms: -1\n",
            "cache_ttl_ms",
        ),
        (
            "execution:\n  names:\n    listPets:\n      rate_limit_per_minute: -1\n",
            "rate_limit_per_minute",
        ),
        (
            "execution:\n  names:\n    listPets:\n      retry_max_retries: -1\n",
            "retry_max_retries",
        ),
        (
            "execution:\n  names:\n    listPets:\n      retry_budget_per_minute: -1\n",
            "retry_budget_per_minute",
        ),
        (
            "execution:\n  names:\n    listPets:\n      circuit_breaker_failure_threshold: -1\n",
            "circuit_breaker_failure_threshold",
        ),
        (
            "execution:\n  names:\n    listPets:\n      circuit_breaker_cooldown_ms: 0\n",
            "circuit_breaker_cooldown_ms",
        ),
        ("generate:\n  tool_grouping: by-tag\n", "generate.tool_grouping"),
    ],
)
def test_load_policy_config_rejects_invalid_values(
    tmp_path: Path, payload: str, message: str
) -> None:
    policy_path = tmp_path / "mcpgen.yaml"
    policy_path.write_text(payload, encoding="utf-8")

    with pytest.raises(PolicyConfigError, match=message):
        load_policy_config(str(policy_path))
