from __future__ import annotations

from pathlib import Path

import pytest

from openapi_to_mcp.common.exceptions import PolicyConfigError
from openapi_to_mcp.policy.applier import apply_policy
from openapi_to_mcp.policy.models import (
    AuthOverride,
    ExecutionOverride,
    PolicyConfig,
    SelectorSet,
)


def test_apply_policy_filters_and_renames_tools() -> None:
    policy = PolicyConfig(
        source_path=_fake_path(),
        include=SelectorSet(operations=frozenset({"GET /pets", "POST /pets"})),
        exclude=SelectorSet(names=frozenset({"createPet"})),
        rename_operations={"GET /pets": "fetchPets"},
    )

    tools = apply_policy(_mapped_tools(), policy)

    assert [tool["name"] for tool in tools] == ["fetchPets"]


def test_apply_policy_overrides_auth_and_execution() -> None:
    policy = PolicyConfig(
        source_path=_fake_path(),
        auth_operations={
            "GET /pets": AuthOverride(
                security=[{"bearerAuth": []}],
                security_schemes={"bearerAuth": {"type": "http", "scheme": "bearer"}},
            )
        },
        execution_operations={
            "GET /pets": ExecutionOverride(max_concurrency=4, timeout_ms=9000)
        },
    )

    [tool] = apply_policy([_mapped_tools()[0]], policy)

    assert tool["_original_security"] == [{"bearerAuth": []}]
    assert tool["_original_security_schemes"] == {
        "bearerAuth": {"type": "http", "scheme": "bearer"}
    }
    assert tool["_policy_execution"] == {"maxConcurrency": 4, "timeoutMs": 9000}


def test_apply_policy_rejects_duplicate_names_created_by_rename() -> None:
    policy = PolicyConfig(
        source_path=_fake_path(),
        rename_operations={
            "GET /pets": "sharedTool",
            "POST /pets": "sharedTool",
        },
    )

    with pytest.raises(PolicyConfigError, match="duplicate tool name"):
        apply_policy(_mapped_tools(), policy)


def _mapped_tools() -> list[dict[str, object]]:
    return [
        {
            "name": "listPets",
            "_original_method": "GET",
            "_original_path": "/pets",
            "_original_security": None,
            "_original_security_schemes": {},
        },
        {
            "name": "createPet",
            "_original_method": "POST",
            "_original_path": "/pets",
            "_original_security": None,
            "_original_security_schemes": {},
        },
    ]


def _fake_path() -> Path:
    return Path("mcpgen.yaml")
