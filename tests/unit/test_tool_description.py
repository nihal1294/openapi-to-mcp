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


def test_build_tool_description_preserves_user_text_with_legacy_substring() -> None:
    operation = {"description": "Describes the read operation for /accounts."}

    description = build_tool_description("get", "/accounts", operation)

    assert description == "Describes the read operation for /accounts."


def test_build_tool_description_handles_acronyms_in_operation_id() -> None:
    operation = {"operationId": "getHTTPSStatus"}

    description = build_tool_description("get", "/status", operation)

    assert description == "Get https status."


def test_build_tool_description_allows_single_word_operation_id() -> None:
    operation = {"operationId": "search"}

    description = build_tool_description("post", "/inventory/search", operation)

    assert description == "Search."


def test_build_tool_description_falls_back_to_method_and_path() -> None:
    operation: dict[str, str] = {}

    description = build_tool_description("get", "/pets/{petId}", operation)

    assert description == "Retrieve pets by petId."


def test_build_tool_description_uses_resource_for_parameter_only_paths() -> None:
    operation: dict[str, str] = {}

    description = build_tool_description("get", "/{petId}", operation)

    assert description == "Retrieve resource by petId."
