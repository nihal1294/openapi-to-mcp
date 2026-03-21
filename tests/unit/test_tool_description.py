from openapi_to_mcp.mapping.tool_description import build_tool_description


def test_build_tool_description_prefers_summary() -> None:
    operation = {
        "summary": "Look up inventory records",
        "description": "Longer description that should not win.",
    }

    description = build_tool_description("get", "/inventory", operation)

    assert description == "Look up inventory records."


def test_build_tool_description_uses_first_description_sentence() -> None:
    operation = {
        "description": "Returns an inventory record by ID. Extra detail is not needed.",
    }

    description = build_tool_description("get", "/inventory/{inventoryId}", operation)

    assert description == "Returns an inventory record by ID."


def test_build_tool_description_humanizes_operation_id() -> None:
    operation = {"operationId": "searchInventory"}

    description = build_tool_description("post", "/inventory/search", operation)

    assert description == "Search inventory."


def test_build_tool_description_falls_back_to_method_and_path() -> None:
    operation: dict[str, str] = {}

    description = build_tool_description("get", "/pets/{petId}", operation)

    assert description == "Retrieve pets by petId."
