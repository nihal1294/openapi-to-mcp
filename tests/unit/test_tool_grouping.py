from __future__ import annotations

import pytest

from openapi_to_mcp.common.exceptions import GenerationError
from openapi_to_mcp.mapping.tool_grouping import apply_tool_grouping


def test_apply_tool_grouping_prefixes_with_first_tag() -> None:
    [tool] = apply_tool_grouping(
        [_tool("listPets", tags=["Pets", "Inventory"])], "tag-prefix"
    )

    assert tool["name"] == "pets_listPets"


def test_apply_tool_grouping_prefixes_digit_leading_tags_conservatively() -> None:
    [tool] = apply_tool_grouping([_tool("loginUser", tags=["2FA"])], "tag-prefix")

    assert tool["name"] == "group_2fa_loginUser"


@pytest.mark.parametrize(
    "tool",
    [
        {"name": "listPets", "_original_name": "listPets"},
        {"name": "listPets", "_original_name": "listPets", "_original_tags": []},
        {"name": "listPets", "_original_name": "listPets", "_original_tags": ["---"]},
    ],
)
def test_apply_tool_grouping_keeps_original_name_without_usable_tags(
    tool: dict[str, object],
) -> None:
    [grouped_tool] = apply_tool_grouping([tool], "tag-prefix")

    assert grouped_tool["name"] == "listPets"


def test_apply_tool_grouping_skips_invalid_tags_until_it_finds_a_valid_one() -> None:
    [tool] = apply_tool_grouping(
        [_tool("listPets", tags=["---", "Pets"])], "tag-prefix"
    )

    assert tool["name"] == "pets_listPets"


def test_apply_tool_grouping_skips_policy_renamed_tools() -> None:
    [tool] = apply_tool_grouping(
        [_tool("fetchPets", original_name="listPets", tags=["Pets"])],
        "tag-prefix",
    )

    assert tool["name"] == "fetchPets"


def test_apply_tool_grouping_handles_mixed_tagged_and_untagged_tools() -> None:
    tools = apply_tool_grouping(
        [
            _tool("listPets", tags=["Pets"]),
            _tool("listOrders"),
        ],
        "tag-prefix",
    )

    assert [tool["name"] for tool in tools] == ["pets_listPets", "listOrders"]


def test_apply_tool_grouping_rejects_unsupported_mode() -> None:
    with pytest.raises(GenerationError, match="Unsupported tool grouping mode"):
        apply_tool_grouping([_tool("listPets", tags=["Pets"])], "by-tag")


def test_apply_tool_grouping_rejects_name_collisions() -> None:
    tools = [
        _tool("listPets", tags=["Pets"]),
        _tool("pets_listPets"),
    ]

    with pytest.raises(GenerationError, match="duplicate tool name"):
        apply_tool_grouping(tools, "tag-prefix")


def _tool(
    name: str,
    *,
    original_name: str | None = None,
    tags: list[str] | None = None,
) -> dict[str, object]:
    tool = {"name": name, "_original_name": original_name or name}
    if tags is not None:
        tool["_original_tags"] = tags
    return tool
