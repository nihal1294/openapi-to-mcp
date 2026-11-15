"""Whole-query JSON schemas preserve inline and local boolean semantics."""

from __future__ import annotations

from typing import Any

import pytest

from openapi_to_mcp.common import MappingError
from openapi_to_mcp.common.form_media import FormMediaError, resolve_local
from openapi_to_mcp.common.openapi_compatibility import openapi_operation_findings
from openapi_to_mcp.common.operations import iter_operations
from openapi_to_mcp.doctor import DoctorAnalyzer
from openapi_to_mcp.mapping import Mapper


def _spec(schema: object, *, target: object = True) -> dict[str, Any]:
    return {
        "openapi": "3.2.1",
        "info": {"title": "Boolean query", "version": "1"},
        "components": {
            "schemas": {
                "Boolean": target,
                "Alias": {"$ref": "#/components/schemas/Boolean"},
                "Cycle": {"$ref": "#/components/schemas/Cycle"},
            }
        },
        "x-schemas": {
            "Slash/Value": target,
            "Tilde~Value": target,
            "Literal~1Value": target,
            "Slash/Alias": {"$ref": "#/x-schemas/Slash~1Value"},
            "Tilde~Alias": {"$ref": "#/x-schemas/Tilde%7E0Value"},
        },
        "paths": {
            "/send": {
                "get": {
                    "operationId": "send",
                    "parameters": [
                        {
                            "name": "whole",
                            "in": "querystring",
                            "required": True,
                            "description": "Whole JSON value",
                            "example": {"label": "a + b"},
                            "content": {"application/json": {"schema": schema}},
                        }
                    ],
                    "responses": {"200": {"description": "OK"}},
                }
            }
        },
    }


@pytest.mark.parametrize("boolean", [True, False])
@pytest.mark.parametrize(
    "reference",
    [
        None,
        "#/components/schemas/Boolean",
        "#/components/schemas/Alias",
        "#/x-schemas/Slash~1Value",
        "#/x-schemas/Tilde~0Value",
        "#/x-schemas/Slash~1Alias",
        "#/x-schemas/Tilde~0Alias",
        "#/x-schemas%2FSlash%7E1Value",
        "#/x-schemas/Tilde%7E0Value",
        "#/x-schemas/Literal~01Value",
    ],
)
def test_whole_json_boolean_schema_equivalence(
    *, boolean: bool, reference: str | None
) -> None:
    schema = boolean if reference is None else {"$ref": reference}
    spec = _spec(schema, target=boolean)
    assert openapi_operation_findings(spec, iter_operations(spec)[0]) == []
    assert not any(
        issue.code == "unsupported_openapi_construct"
        for issue in DoctorAnalyzer(spec).analyze("inline").issues
    )
    expected = {
        **({} if boolean else {"not": {}}),
        "description": "Whole JSON value",
        "examples": [{"label": "a + b"}],
    }
    for error_mode in ("fail", "skip"):
        mapper = Mapper(spec, on_mapping_error=error_mode)
        tools = mapper.map_tools()
        assert len(tools) == 1
        assert tools[0]["inputSchema"]["properties"]["whole"] == expected
        assert tools[0]["inputSchema"]["required"] == ["whole"]
        assert mapper.get_report()["skipped_operations"] == []


@pytest.mark.parametrize(
    ("schema", "target"),
    [
        ({"$ref": "#/components/schemas/Missing"}, True),
        ({"$ref": "#/components/schemas/Boolean"}, None),
        ({"$ref": "#/components/schemas/Boolean"}, []),
        ({"$ref": "#/components/schemas/Boolean"}, "true"),
        ({"$ref": "#/components/schemas/Boolean"}, 1),
        ({"$ref": "#/components/schemas/Cycle"}, True),
        (
            {"$ref": "#/components/schemas/Alias"},
            {"$ref": "#/components/schemas/Alias"},
        ),
        ({"$ref": "#/components/schemas/Alias"}, {"$ref": "external.json#/Any"}),
        (
            {"$ref": "#/components/schemas/Alias"},
            {"$ref": "#/components/schemas/Missing"},
        ),
        ({"$ref": "#/components/schemas/Alias"}, {"$ref": None}),
        ({"$ref": "external.json#/Any"}, True),
        ({"$ref": 1}, True),
    ],
)
def test_whole_json_invalid_schema_references_remain_findings(
    schema: object, target: object
) -> None:
    spec = _spec(schema, target=target)
    findings = openapi_operation_findings(spec, iter_operations(spec)[0])
    assert len(findings) == 1
    assert "reference" in findings[0].guidance
    with pytest.raises(MappingError, match="reference"):
        Mapper(spec).map_tools()
    mapper = Mapper(spec, on_mapping_error="skip")
    assert mapper.map_tools() == []
    assert "reference" in mapper.get_report()["skipped_operations"][0]["reason"]
    assert any(
        issue.code == "unsupported_openapi_construct"
        for issue in DoctorAnalyzer(spec).analyze("inline").issues
    )


@pytest.mark.parametrize("boolean", [True, False])
@pytest.mark.parametrize(
    "content_type", ["text/plain", "application/x-www-form-urlencoded"]
)
@pytest.mark.parametrize("referenced", [False, True])
def test_boolean_schemas_still_require_json_media(
    *, boolean: bool, content_type: str, referenced: bool
) -> None:
    schema = {"$ref": "#/components/schemas/Boolean"} if referenced else boolean
    spec = _spec(schema, target=boolean)
    param = spec["paths"]["/send"]["get"]["parameters"][0]
    param["content"] = {content_type: {"schema": schema}}
    with pytest.raises(MappingError):
        Mapper(spec).map_tools()
    mapper = Mapper(spec, on_mapping_error="skip")
    assert mapper.map_tools() == []


@pytest.mark.parametrize("boolean", [True, False])
def test_reference_objects_remain_dictionary_only(*, boolean: bool) -> None:
    spec = _spec(schema=True, target=boolean)
    with pytest.raises(FormMediaError, match="invalid local reference or schema"):
        resolve_local(spec, {"$ref": "#/components/schemas/Boolean"})
    param = spec["paths"]["/send"]["get"]["parameters"][0]
    param["content"] = {"application/json": {"$ref": "#/components/schemas/Boolean"}}
    with pytest.raises(MappingError, match="invalid local reference or schema"):
        Mapper(spec).map_tools()


@pytest.mark.parametrize("boolean", [True, False])
@pytest.mark.parametrize("location", ["parameter", "requestBody"])
def test_boolean_targets_do_not_become_reference_objects(
    *, boolean: bool, location: str
) -> None:
    spec = _spec(schema=True, target=boolean)
    operation = spec["paths"]["/send"]["get"]
    reference = {"$ref": "#/components/schemas/Boolean"}
    if location == "parameter":
        operation["parameters"] = [reference]
    else:
        operation["requestBody"] = reference
    with pytest.raises(MappingError, match="reference"):
        Mapper(spec).map_tools()
    mapper = Mapper(spec, on_mapping_error="skip")
    assert mapper.map_tools() == []


@pytest.mark.parametrize(
    "reference",
    [
        "#/x-schemas/Slash~1Alias",
        "#/x-schemas/Tilde~0Alias",
        "#/x-schemas%2FSlash%7E1Value",
        "#/x-schemas/Tilde%7E0Value",
        "#/x-schemas/Literal~01Value",
    ],
)
def test_escaped_dictionary_whole_json_schema_keeps_validation(reference: str) -> None:
    target = {"type": "string", "minLength": 3}
    spec = _spec({"$ref": reference}, target=target)
    for error_mode in ("fail", "skip"):
        tool = Mapper(spec, on_mapping_error=error_mode).map_tools()[0]
        schema = tool["inputSchema"]["properties"]["whole"]
        assert schema["type"] == "string"
        assert schema["minLength"] == 3
