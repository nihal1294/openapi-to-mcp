from pathlib import Path

import pytest

from openapi_to_mcp.common.exceptions import PolicyConfigError
from openapi_to_mcp.common.tool_runtime import (
    build_public_tools,
    build_runtime_tool_registry,
)
from openapi_to_mcp.mapping.annotations import derive_tool_annotations
from openapi_to_mcp.mapping.mapper import Mapper
from openapi_to_mcp.mapping.tool_grouping import apply_tool_grouping
from openapi_to_mcp.policy.applier import apply_policy
from openapi_to_mcp.policy.parser import parse_policy_config


def _tool(method: str = "get") -> dict:
    spec = {
        "openapi": "3.2.0",
        "info": {"title": "Test", "version": "1"},
        "paths": {
            "/items": {
                method: {
                    "operationId": "items",
                    "responses": {"200": {"description": "ok"}},
                }
            }
        },
    }
    return Mapper(spec).map_tools()[0]


def _policy(annotations: dict, **tools: object):
    return parse_policy_config(
        {"tools": {"annotations": annotations, **tools}}, Path("policy.yaml")
    )


@pytest.mark.parametrize(
    ("method", "expected"),
    [
        *[
            (
                m,
                {
                    "readOnlyHint": True,
                    "destructiveHint": False,
                    "idempotentHint": True,
                },
            )
            for m in ("get", "head", "options", "query")
        ],
        ("put", {"idempotentHint": True}),
        ("delete", {"destructiveHint": True, "idempotentHint": True}),
        *[(m, {}) for m in ("post", "patch", "trace")],
    ],
)
def test_method_defaults(method, expected) -> None:
    assert _tool(method).get("annotations", {}) == expected


def test_override_replaces_defaults_and_preserves_false() -> None:
    policy = _policy(
        {
            "names": {
                "items": {
                    "read_only": False,
                    "destructive": False,
                    "idempotent": False,
                    "open_world": False,
                }
            }
        }
    )
    assert apply_policy([_tool()], policy)[0]["annotations"] == {
        "readOnlyHint": False,
        "destructiveHint": False,
        "idempotentHint": False,
        "openWorldHint": False,
    }
    policy = _policy({"names": {"items": {"destructive": True}}})
    assert apply_policy([_tool()], policy)[0]["annotations"] == {
        "destructiveHint": True
    }
    policy = _policy({"names": {"items": {}}})
    assert not apply_policy([_tool()], policy)[0].get("annotations")


def test_precedence_and_unmatched() -> None:
    policy = _policy(
        {
            "operations": {"GET /items": {"idempotent": False}},
            "names": {"items": {"destructive": True}, "renamed": {"open_world": True}},
        },
        rename={"names": {"items": "renamed"}},
    )
    assert apply_policy([_tool()], policy)[0]["annotations"] == {
        "idempotentHint": False
    }
    policy = _policy(
        {"names": {"items": {"destructive": True}, "renamed": {"open_world": True}}},
        rename={"names": {"items": "renamed"}},
    )
    assert apply_policy([_tool()], policy)[0]["annotations"] == {
        "destructiveHint": True
    }
    policy = _policy(
        {"names": {"renamed": {"open_world": True}}},
        rename={"names": {"items": "renamed"}},
    )
    assert apply_policy([_tool()], policy)[0]["annotations"] == {"openWorldHint": True}
    assert (
        apply_policy([_tool()], _policy({"names": {"other": {}}}))[0]["annotations"]
        == _tool()["annotations"]
    )


@pytest.mark.parametrize(
    "entry", [{"unknown": True}, {"read_only": 1}, {"open_world": None}]
)
def test_invalid_override(entry) -> None:
    with pytest.raises(PolicyConfigError):
        _policy({"names": {"items": entry}})


def test_custom_method_and_public_runtime_separation() -> None:

    assert derive_tool_annotations("COPY") == {}
    tool = _tool()
    tool["_original_tags"] = ["Pets"]
    [grouped] = apply_tool_grouping([tool], "tag-prefix")
    assert grouped["name"] == "pets_items"
    assert build_public_tools([grouped])[0]["annotations"] == tool["annotations"]
    assert "annotations" not in build_runtime_tool_registry([grouped])["pets_items"]
