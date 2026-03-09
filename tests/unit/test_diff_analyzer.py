from openapi_to_mcp.diff import DiffAnalyzer


def test_diff_analyzer_reports_added_and_removed_tools() -> None:
    before = _spec(
        {
            "/pets": {
                "get": {
                    "operationId": "listPets",
                    "responses": {"200": {"description": "OK"}},
                }
            }
        }
    )
    after = _spec(
        {
            "/orders": {
                "get": {
                    "operationId": "listOrders",
                    "responses": {"200": {"description": "OK"}},
                }
            }
        }
    )

    report = DiffAnalyzer(before, after).analyze("before.json", "after.json")
    codes = [change.code for change in report.changes]

    assert report.breaking_count() == 1
    assert report.non_breaking_count() == 1
    assert codes == ["tool_removed", "tool_added"]


def test_diff_analyzer_reports_rename_and_contract_changes() -> None:
    before = _spec(
        {
            "/pets": {
                "get": {
                    "operationId": "listPets",
                    "parameters": [
                        {
                            "name": "limit",
                            "in": "query",
                            "schema": {"type": "integer"},
                        }
                    ],
                    "responses": {
                        "200": {
                            "description": "OK",
                            "content": {
                                "application/json": {
                                    "schema": {
                                        "type": "object",
                                        "properties": {"id": {"type": "integer"}},
                                    }
                                }
                            },
                        }
                    },
                    "security": [{"apiKeyAuth": []}],
                }
            }
        },
        components={
            "securitySchemes": {
                "apiKeyAuth": {"type": "apiKey", "in": "header", "name": "X-API-Key"}
            }
        },
    )
    after = _spec(
        {
            "/pets": {
                "get": {
                    "operationId": "fetchPets",
                    "parameters": [
                        {
                            "name": "status",
                            "in": "query",
                            "required": True,
                            "schema": {"type": "string"},
                        }
                    ],
                    "responses": {
                        "200": {
                            "description": "OK",
                            "content": {
                                "application/json": {
                                    "schema": {
                                        "type": "object",
                                        "properties": {"name": {"type": "string"}},
                                    }
                                }
                            },
                        }
                    },
                    "security": [{"bearerAuth": []}],
                }
            }
        },
        components={
            "securitySchemes": {"bearerAuth": {"type": "http", "scheme": "bearer"}}
        },
    )

    report = DiffAnalyzer(before, after).analyze("before.json", "after.json")
    codes = [change.code for change in report.changes]

    assert report.breaking_count() == 4
    assert codes == [
        "tool_renamed",
        "input_schema_changed",
        "output_schema_changed",
        "auth_changed",
    ]


def test_diff_analyzer_reports_rename_only_when_contract_is_identical() -> None:
    before = _spec(
        {
            "/pets": {
                "get": {
                    "operationId": "listPets",
                    "responses": {"200": {"description": "OK"}},
                }
            }
        }
    )
    after = _spec(
        {
            "/pets": {
                "get": {
                    "operationId": "fetchPets",
                    "responses": {"200": {"description": "OK"}},
                }
            }
        }
    )

    report = DiffAnalyzer(before, after).analyze("before.json", "after.json")

    assert report.breaking_count() == 1
    assert [change.code for change in report.changes] == ["tool_renamed"]


def _spec(paths: dict, *, components: dict | None = None) -> dict:
    spec = {
        "openapi": "3.0.0",
        "info": {"title": "Diff Test", "version": "1.0.0"},
        "servers": [{"url": "https://example.com"}],
        "paths": paths,
    }
    if components is not None:
        spec["components"] = components
    return spec
