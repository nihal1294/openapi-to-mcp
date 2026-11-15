from __future__ import annotations

import click
import pytest

from openapi_to_mcp.cli import cli
from scripts.release_contracts import _option_type, compare_contracts


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


def _choice_contract(option_type, **overrides):
    metadata = {"required": False, "default": "none", "type": option_type}
    metadata.update(overrides)
    return _contract(cli={"diff": {"options": {"--fail-on": metadata}}})


def _choice(choices, **properties):
    return {"kind": "choice", "choices": choices, "case_sensitive": True, **properties}


def test_strict_choice_superset_is_minor() -> None:
    result = compare_contracts(
        _choice_contract(_choice(["none", "breaking"])),
        _choice_contract(_choice(["none", "review", "breaking"])),
    )
    assert result == {
        "minimum": "minor",
        "complete": True,
        "reasons": ["cli-option-choices-added:diff:--fail-on"],
    }


def test_actual_diff_choice_extension_is_minor() -> None:
    current = next(p for p in cli.commands["diff"].params if p.name == "fail_on")
    previous = click.Option(
        ["--fail-on"],
        type=click.Choice(["breaking", "none"], case_sensitive=False),
        default="none",
    )
    before, after = _option_type(previous), _option_type(current)
    assert before == _choice(["breaking", "none"], case_sensitive=False)
    assert after == _choice(["breaking", "none", "review"], case_sensitive=False)
    assert current.default == previous.default == "none"
    result = compare_contracts(_choice_contract(before), _choice_contract(after))
    assert result == {
        "minimum": "minor",
        "complete": True,
        "reasons": ["cli-option-choices-added:diff:--fail-on"],
    }


@pytest.mark.parametrize(
    ("original", "alias"), [("none", "NONE"), ("straße", "STRASSE")]
)
def test_casefold_collision_can_change_actual_click_conversion(original, alias) -> None:
    before = click.Option(
        ["--mode"], type=click.Choice([original], case_sensitive=False)
    )
    after = click.Option(
        ["--mode"], type=click.Choice([alias, original], case_sensitive=False)
    )
    assert before.type.convert(original, before, None) == original
    assert after.type.convert(original, after, None) == alias
    result = compare_contracts(
        _choice_contract(_option_type(before)),
        _choice_contract(_option_type(after)),
    )
    assert result["minimum"] == "breaking"
    assert result["reasons"] == ["cli-option-type-changed:diff:--fail-on"]


@pytest.mark.parametrize("choices", [["NONE", "none"], ["STRASSE", "straße"]])
def test_casefold_collision_in_baseline_is_not_a_valid_extension(choices) -> None:
    result = compare_contracts(
        _choice_contract(_choice(choices, case_sensitive=False)),
        _choice_contract(_choice([*choices, "review"], case_sensitive=False)),
    )
    assert result["minimum"] == "breaking"
    assert result["reasons"] == ["cli-option-type-changed:diff:--fail-on"]


@pytest.mark.parametrize(
    ("original", "addition", "case_sensitive"),
    [("none", "review", False), ("none", "NONE", True), ("straße", "STRASSE", True)],
)
def test_disjoint_normalized_choices_preserve_click_conversion(
    original, addition, case_sensitive
) -> None:
    before = click.Option(
        ["--mode"], type=click.Choice([original], case_sensitive=case_sensitive)
    )
    after = click.Option(
        ["--mode"],
        type=click.Choice([addition, original], case_sensitive=case_sensitive),
    )
    assert before.type.convert(original, before, None) == original
    assert after.type.convert(original, after, None) == original
    assert after.type.convert(addition, after, None) == addition
    result = compare_contracts(
        _choice_contract(_option_type(before)),
        _choice_contract(_option_type(after)),
    )
    assert result["minimum"] == "minor"
    assert result["reasons"] == ["cli-option-choices-added:diff:--fail-on"]


@pytest.mark.parametrize("case_sensitive", [True, False])
def test_option_type_captures_choice_case_sensitivity(case_sensitive) -> None:
    option = click.Option(
        ["--mode"], type=click.Choice(["b", "a"], case_sensitive=case_sensitive)
    )
    assert _option_type(option) == _choice(["a", "b"], case_sensitive=case_sensitive)


@pytest.mark.parametrize("choices", [["none", "breaking"], ["breaking", "none"]])
def test_equivalent_captured_choices_have_no_impact(choices) -> None:
    before = _option_type(click.Option(["--mode"], type=click.Choice(choices)))
    after = _option_type(
        click.Option(["--mode"], type=click.Choice(["breaking", "none"]))
    )
    assert (
        compare_contracts(_choice_contract(before), _choice_contract(after))["minimum"]
        == "none"
    )


@pytest.mark.parametrize(
    ("before", "after"),
    [
        (_choice(["breaking", "none"]), _choice(["none"])),
        (_choice(["breaking", "none"]), _choice(["none", "review"])),
        (_choice(["none"]), _choice(["none", "review"], case_sensitive=False)),
        (_choice(["none"], exists=False), _choice(["none", "review"], exists=True)),
        ({"kind": "string"}, _choice(["none", "review"])),
        (_choice(["none"]), {"kind": "string"}),
        ({"kind": "integer", "min": 1}, {"kind": "integer", "min": 0}),
        ({"kind": "choice", "choices": ["none"]}, _choice(["none", "review"])),
        (_choice(["none"]), {"kind": "choice", "choices": ["none", "review"]}),
        (_choice(["none"]), _choice(["none", "review"], case_sensitive=1)),
        (None, _choice(["none", "review"])),
        ("choice", _choice(["none", "review"])),
        ({}, _choice(["none", "review"])),
        (_choice([]), _choice(["none", "review"])),
        (_choice("none"), _choice(["none", "review"])),
        (_choice([1]), _choice(["1", "review"])),
        (_choice(["none", "none"]), _choice(["none", "review"])),
        (_choice(["none"]), _choice(["none", "review", "review"])),
        (_choice(["none"]), _choice(["none", "review", 1])),
    ],
)
def test_other_cli_type_changes_remain_breaking(before, after) -> None:
    result = compare_contracts(_choice_contract(before), _choice_contract(after))
    assert result["minimum"] == "breaking"
    assert "cli-option-type-changed:diff:--fail-on" in result["reasons"]
    assert "cli-option-choices-added:diff:--fail-on" not in result["reasons"]


@pytest.mark.parametrize(
    ("overrides", "reason"),
    [
        ({"required": True}, "cli-option-now-required:diff:--fail-on"),
        ({"default": "review"}, "cli-option-default-changed:diff:--fail-on"),
    ],
)
def test_choice_extension_preserves_other_breaking_gates(overrides, reason) -> None:
    result = compare_contracts(
        _choice_contract(_choice(["none"])),
        _choice_contract(_choice(["none", "review"]), **overrides),
    )
    assert result["minimum"] == "breaking"
    assert reason in result["reasons"]


def test_choice_extension_requires_complete_runtime_evidence() -> None:
    head = _choice_contract(_choice(["none", "review"]))
    head["generated"]["runtime"]["http_custom"] = False
    result = compare_contracts(_choice_contract(_choice(["none"])), head)
    assert result["minimum"] == "needs-review"
    assert result["complete"] is False
    assert "runtime-evidence-incomplete:head:http_custom" in result["reasons"]
