from __future__ import annotations

from scripts.release_contracts import compare_contracts


def _runtime(**overrides: bool) -> dict[str, bool]:
    result = {
        f"{transport}_{check}": True
        for transport in ("stdio", "http")
        for check in ("compiled", "list", "call", "custom")
    }
    result.update(overrides)
    return result


def _contract(**overrides: object) -> dict[str, object]:
    contract: dict[str, object] = {
        "cli": {"generate": {"options": {"--transport": {"required": False}}}},
        "python_floor": ">=3.14",
        "node_floor": ">=22",
        "generated": {
            "tools": {"testConversionTool": {"inputSchema": {"type": "object"}}},
            "auth_env": ["AUTH_BEARERAUTH_TOKEN"],
            "runtime": _runtime(),
        },
    }
    contract.update(overrides)
    return contract


def test_compare_contracts_allows_additive_cli_and_tools() -> None:
    base = _contract()
    head = _contract(
        cli={
            "generate": {
                "options": {
                    "--transport": {"required": False},
                    "--new-option": {"required": False},
                }
            }
        },
        generated={
            "tools": {
                "testConversionTool": {"inputSchema": {"type": "object"}},
                "newTool": {"inputSchema": {"type": "object"}},
            },
            "auth_env": ["AUTH_BEARERAUTH_TOKEN"],
            "runtime": _runtime(),
        },
    )

    result = compare_contracts(base, head)

    assert result["minimum"] == "minor"
    assert result["complete"] is True
    assert "cli-option-added:generate:--new-option" in result["reasons"]
    assert "generated-tool-added:newTool" in result["reasons"]


def test_compare_contracts_marks_removed_and_required_changes_breaking() -> None:
    base = _contract()
    head = _contract(
        cli={"generate": {"options": {"--transport": {"required": True}}}},
        generated={
            "tools": {},
            "auth_env": [],
            "runtime": _runtime(),
        },
    )

    result = compare_contracts(base, head)

    assert result["minimum"] == "breaking"
    assert "cli-option-now-required:generate:--transport" in result["reasons"]
    assert "generated-tool-removed:testConversionTool" in result["reasons"]
    assert "auth-contract-removed:AUTH_BEARERAUTH_TOKEN" in result["reasons"]


def test_compare_contracts_marks_runtime_floor_increase_breaking() -> None:
    result = compare_contracts(
        _contract(),
        _contract(python_floor=">=3.15", node_floor=">=24"),
    )

    assert result["minimum"] == "breaking"
    assert "python-runtime-floor-raised:>=3.14->>=3.15" in result["reasons"]
    assert "node-runtime-floor-raised:>=22->>=24" in result["reasons"]


def test_compare_contracts_reports_incomplete_runtime_evidence() -> None:
    head = _contract(
        generated={
            "tools": {"testConversionTool": {"inputSchema": {"type": "object"}}},
            "auth_env": ["AUTH_BEARERAUTH_TOKEN"],
            "runtime": _runtime(stdio_call=False),
        }
    )

    result = compare_contracts(_contract(), head)

    assert result["minimum"] == "needs-review"
    assert result["complete"] is False
    assert "runtime-evidence-incomplete:head:stdio_call" in result["reasons"]
