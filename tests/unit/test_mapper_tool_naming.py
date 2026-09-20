"""Regression coverage for tool-name allocation during mapping failures."""

from typing import Any

import pytest

from openapi_to_mcp.mapping.mapper import Mapper


@pytest.mark.parametrize("leading_supported", [True, False])
def test_skipped_swagger_operation_releases_provisional_colliding_name(
    *, leading_supported: bool
) -> None:
    spec: dict[str, Any] = {
        "swagger": "2.0",
        "info": {"title": "Name allocation", "version": "1.0.0"},
        "paths": {
            "/pets-by-id": {
                "get": {
                    "responses": {"200": {"description": "OK"}},
                }
            },
            "/pets_by_id": {
                "get": {
                    "parameters": [
                        {
                            "name": "pet",
                            "in": "body",
                            "schema": {"type": "object"},
                        }
                    ],
                    "responses": {"200": {"description": "OK"}},
                }
            },
            "/pets.by.id": {
                "get": {
                    "responses": {"200": {"description": "OK"}},
                }
            },
        },
    }
    if not leading_supported:
        del spec["paths"]["/pets-by-id"]

    mapper = Mapper(spec, strict=False)

    tools = mapper.map_tools()

    expected_names = ["get_pets_by_id"]
    if leading_supported:
        expected_names.append("get_pets_by_id_2")
    assert [tool["name"] for tool in tools] == expected_names
    report = mapper.get_report()
    assert len(report["skipped_operations"]) == 1
    assert report["skipped_operations"][0]["path"] == "/pets_by_id"
    expected_warnings = (
        ["Duplicate tool name 'get_pets_by_id' deduped to 'get_pets_by_id_2'."]
        if leading_supported
        else []
    )
    assert [
        warning for warning in report["warnings"] if "Duplicate tool name" in warning
    ] == expected_warnings
