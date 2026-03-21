from __future__ import annotations

import pytest

from openapi_to_mcp.common.exceptions import GenerationError
from openapi_to_mcp.mapping.tool_grouping import apply_tool_grouping


def test_apply_tool_grouping_prefixes_with_first_tag() -> None:
    tools = [
        {
            "name": "listPets",
            "_original_name": "listPets",
            "_original_tags": ["Pets", "Inventory"],
        }
    ]

    [tool] = apply_tool_grouping(tools, "tag-prefix")

    assert tool["name"] == "pets_listPets"


def test_apply_tool_grouping_skips_policy_renamed_tools() -> None:
    tools = [
        {
            "name": "fetchPets",
            "_original_name": "listPets",
            "_original_tags": ["Pets"],
        }
    ]

    [tool] = apply_tool_grouping(tools, "tag-prefix")

    assert tool["name"] == "fetchPets"


def test_apply_tool_grouping_rejects_name_collisions() -> None:
    tools = [
        {
            "name": "listPets",
            "_original_name": "listPets",
            "_original_tags": ["Pets"],
        },
        {
            "name": "pets_listPets",
            "_original_name": "pets_listPets",
            "_original_tags": [],
        },
    ]

    with pytest.raises(GenerationError, match="duplicate tool name"):
        apply_tool_grouping(tools, "tag-prefix")
