"""Declaration-aware form media normalization."""

from pathlib import Path

import pytest

from openapi_to_mcp.common import MappingError
from openapi_to_mcp.common.form_media import FormMediaError, normalize_form_media
from openapi_to_mcp.doctor import DoctorAnalyzer
from openapi_to_mcp.mapping import Mapper
from openapi_to_mcp.policy.models import PolicyConfig, SelectorSet


def test_encoding_presence_and_version_are_preserved() -> None:
    media = {
        "schema": {
            "type": "object",
            "properties": {"tags": {"type": "array", "items": {"type": "string"}}},
        },
        "encoding": {"tags": {"explode": False}},
    }
    result = normalize_form_media({"openapi": "3.2.1"}, media)
    assert result["version32"] is True
    assert result["fields"]["tags"]["mode"] == "style"
    assert result["fields"]["tags"]["explode"] is False


def test_unsupported_encoding_is_rejected() -> None:
    media = {
        "schema": {"type": "object", "properties": {"x": {"type": "string"}}},
        "encoding": {"x": {"allowReserved": True}},
    }
    with pytest.raises(FormMediaError, match="allowReserved"):
        normalize_form_media({"openapi": "3.1.2"}, media)


def test_local_references_and_mapper_metadata() -> None:
    spec = {
        "openapi": "3.2.1",
        "info": {"title": "test", "version": "1"},
        "components": {
            "schemas": {
                "form/~": {"type": "object", "properties": {"a": {"type": "string"}}}
            },
            "parameters": {
                "whole": {
                    "name": "payload",
                    "in": "querystring",
                    "required": True,
                    "content": {
                        "application/x-www-form-urlencoded": {
                            "schema": {"$ref": "#/components/schemas/form~1~0"}
                        }
                    },
                }
            },
        },
        "paths": {
            "/send": {
                "parameters": [{"$ref": "#/components/parameters/whole"}],
                "post": {
                    "operationId": "send",
                    "responses": {"200": {"description": "OK"}},
                },
            }
        },
    }
    tool = Mapper(spec).map_tools()[0]
    assert tool["inputSchema"]["required"] == ["payload"]
    parameter = tool["_original_parameters"][0]
    assert parameter["name"] == "payload"
    assert parameter["form"]["fields"]["a"]["mode"] == "content"


def test_unsupported_encoding_honors_skip_and_exclusion() -> None:
    spec = {
        "openapi": "3.2.1",
        "paths": {
            "/send": {
                "post": {
                    "operationId": "send",
                    "requestBody": {
                        "content": {
                            "application/x-www-form-urlencoded": {
                                "schema": {
                                    "type": "object",
                                    "properties": {"a": {"type": "string"}},
                                },
                                "encoding": {"a": {"allowReserved": True}},
                            }
                        }
                    },
                    "responses": {"200": {"description": "OK"}},
                }
            }
        },
    }
    with pytest.raises(MappingError, match="allowReserved"):
        Mapper(spec).map_tools()
    mapper = Mapper(spec, on_mapping_error="skip")
    assert mapper.map_tools() == []
    assert "allowReserved" in mapper.get_report()["skipped_operations"][0]["reason"]
    policy = PolicyConfig(
        source_path=Path("policy.yaml"),
        exclude=SelectorSet(operations=frozenset({"POST /send"})),
    )
    assert Mapper(spec, policy_config=policy).map_tools() == []


@pytest.mark.parametrize(
    "encoding",
    [
        {"style": "deepObject"},
        {"allowReserved": True},
        {"contentType": "application/octet-stream"},
        {"encoding": {"nested": {}}},
    ],
)
def test_unsupported_field_encodings_fail(encoding: dict) -> None:
    media = {
        "schema": {"type": "object", "properties": {"a": {"type": "string"}}},
        "encoding": {"a": encoding},
    }
    with pytest.raises(FormMediaError):
        normalize_form_media({"openapi": "3.2.1"}, media)


def test_explicit_false_selects_style_and_ignores_content_type() -> None:
    media = {
        "schema": {"type": "object", "properties": {"a": {"type": ["string", "null"]}}},
        "encoding": {
            "a": {"allowReserved": False, "contentType": "application/octet-stream"}
        },
    }
    field = normalize_form_media({"openapi": "3.2.1"}, media)["fields"]["a"]
    assert field["mode"] == "style"
    assert field["contentType"] is None


def test_json_preference_ignores_unselected_unsupported_body() -> None:
    spec = {
        "openapi": "3.2.1",
        "paths": {
            "/send": {
                "post": {
                    "operationId": "send",
                    "requestBody": {
                        "content": {
                            "multipart/form-data": {"schema": {"type": "object"}},
                            "application/json": {"schema": {"type": "object"}},
                        }
                    },
                    "responses": {"200": {"description": "OK"}},
                }
            }
        },
    }
    body = Mapper(spec).map_tools()[0]["_original_request_body"]
    assert body["content_type"] == "application/json"
    assert "form" not in body


@pytest.mark.parametrize("conflict", ["duplicate", "query", "name", "body"])
def test_whole_query_conflicts_fail_before_mapping(conflict: str) -> None:
    parameter = {
        "name": "whole",
        "in": "querystring",
        "content": {"text/plain": {"schema": {"type": "string"}}},
    }
    operation = {"parameters": [parameter], "responses": {"200": {"description": "OK"}}}
    if conflict == "duplicate":
        operation["parameters"].append(parameter.copy())
    elif conflict == "query":
        operation["parameters"].append(
            {"name": "other", "in": "query", "schema": {"type": "string"}}
        )
    elif conflict == "name":
        operation["parameters"].append(
            {"name": "whole", "in": "header", "schema": {"type": "string"}}
        )
    else:
        parameter["name"] = "requestBody"
        operation["requestBody"] = {
            "content": {"application/json": {"schema": {"type": "object"}}}
        }
    spec = {"openapi": "3.2.1", "paths": {"/search": {"get": operation}}}
    with pytest.raises(MappingError, match="querystring"):
        Mapper(spec).map_tools()


def test_whole_query_reference_override_keeps_trace_and_schema() -> None:
    form = {"schema": {"type": "object", "properties": {"a": {"type": "string"}}}}
    spec = {
        "openapi": "3.2.1",
        "x-params": [
            {
                "name": "query",
                "in": "querystring",
                "content": {"application/x-www-form-urlencoded": form},
            }
        ],
        "paths": {
            "/items": {
                "parameters": [{"$ref": "#/x-params/0"}],
                "get": {
                    "operationId": "items",
                    "parameters": [
                        {
                            "name": "query",
                            "in": "querystring",
                            "content": {"text/plain": {"schema": {"type": "string"}}},
                        }
                    ],
                    "responses": {"200": {"description": "OK"}},
                },
            }
        },
    }
    trace: list[dict] = []
    tool = Mapper(spec, trace=trace).map_tools()[0]
    assert tool["inputSchema"]["properties"]["query"]["type"] == "string"
    assert tool["_original_parameters"][0]["content_type"] == "text/plain"
    assert (trace[0]["path"], trace[0]["status"], trace[0]["final_name"]) == (
        "/items",
        "selected",
        "items",
    )


@pytest.mark.parametrize(
    "marker",
    [
        {"format": "binary"},
        {"format": "byte"},
        {"contentEncoding": "base64"},
        {"contentMediaType": "application/octet-stream"},
    ],
)
@pytest.mark.parametrize("additional", [False, True])
def test_styled_object_binary_children_rejected_strict_and_skip(
    marker: dict, *, additional: bool
) -> None:
    child = {"type": "string", **marker}
    object_schema = (
        {
            "type": "object",
            "additionalProperties": {"$ref": "#/components/schemas/Child"},
        }
        if additional
        else {
            "type": "object",
            "properties": {"file": {"$ref": "#/components/schemas/Child"}},
        }
    )
    media = {
        "schema": {"type": "object", "properties": {"obj": object_schema}},
        "encoding": {"obj": {"style": "form"}},
    }
    spec = {
        "openapi": "3.2.1",
        "components": {"schemas": {"Child": child}},
        "paths": {
            "/send": {
                "post": {
                    "operationId": "send",
                    "requestBody": {
                        "content": {"application/x-www-form-urlencoded": media}
                    },
                    "responses": {"200": {"description": "OK"}},
                }
            }
        },
    }
    with pytest.raises(FormMediaError, match="Binary"):
        normalize_form_media(spec, media)
    with pytest.raises(MappingError, match="Binary"):
        Mapper(spec).map_tools()
    mapper = Mapper(spec, on_mapping_error="skip")
    assert mapper.map_tools() == []
    assert "Binary" in mapper.get_report()["skipped_operations"][0]["reason"]


@pytest.mark.parametrize("composition", ["allOf", "oneOf", "anyOf"])
@pytest.mark.parametrize("use_ref", [False, True])
@pytest.mark.parametrize("location", ["whole-query", "request-body"])
@pytest.mark.parametrize("target", ["form", "styled-object"])
def test_composed_expanded_form_layout_is_rejected(
    composition: str, location: str, target: str, *, use_ref: bool
) -> None:
    composed = {
        "type": "object",
        composition: [
            {"properties": {"name": {"type": "string"}}, "required": ["name"]}
        ],
    }
    referenced = {"$ref": "#/components/schemas/Composed"} if use_ref else composed
    media = (
        {"schema": referenced}
        if target == "form"
        else {
            "schema": {"type": "object", "properties": {"obj": referenced}},
            "encoding": {"obj": {"style": "form"}},
        }
    )
    operation = {"operationId": "send", "responses": {"200": {"description": "OK"}}}
    if location == "whole-query":
        operation["parameters"] = [
            {
                "name": "whole",
                "in": "querystring",
                "content": {"application/x-www-form-urlencoded": media},
            }
        ]
    else:
        operation["requestBody"] = {
            "content": {"application/x-www-form-urlencoded": media}
        }
    spec = {
        "openapi": "3.2.1",
        "components": {"schemas": {"Composed": composed}},
        "paths": {"/send": {"post": operation}},
    }
    with pytest.raises(FormMediaError, match="Composed"):
        normalize_form_media(spec, media)
    with pytest.raises(MappingError, match="Composed"):
        Mapper(spec).map_tools()
    issues = DoctorAnalyzer(spec).analyze("inline").issues
    assert any(
        issue.code == "unsupported_openapi_construct" and "Composed" in issue.hint
        for issue in issues
    )
    mapper = Mapper(spec, on_mapping_error="skip")
    assert mapper.map_tools() == []
    assert "Composed" in mapper.get_report()["skipped_operations"][0]["reason"]
    trace: list[dict] = []
    policy = PolicyConfig(
        source_path=Path("policy.yaml"),
        exclude=SelectorSet(operations=frozenset({"POST /send"})),
    )
    assert Mapper(spec, policy_config=policy, trace=trace).map_tools() == []
    assert trace[0]["status"] == "excluded_before_mapping"


@pytest.mark.parametrize("composition", ["allOf", "oneOf", "anyOf"])
def test_json_valued_object_allows_composed_schema(composition: str) -> None:
    media = {
        "schema": {
            "type": "object",
            "properties": {"obj": {"$ref": "#/components/schemas/Composed"}},
        }
    }
    spec = {
        "openapi": "3.2.1",
        "components": {
            "schemas": {
                "Composed": {
                    "type": "object",
                    composition: [{"properties": {"name": {"type": "string"}}}],
                }
            }
        },
    }
    field = normalize_form_media(spec, media)["fields"]["obj"]
    assert field["mode"] == "content"
    assert field["contentType"] == "application/json"


@pytest.mark.parametrize("target", ["form", "styled-object"])
@pytest.mark.parametrize("composition", ["allOf", "oneOf", "anyOf"])
def test_composed_schema_reference_sibling_is_not_ignored(
    target: str, composition: str
) -> None:
    sibling = {
        "$ref": "#/components/schemas/Base",
        composition: [{"properties": {"name": {"type": "string"}}}],
    }
    spec = {
        "openapi": "3.2.1",
        "components": {
            "schemas": {
                "Base": {"type": "object", "properties": {"x": {"type": "string"}}}
            }
        },
    }
    media = (
        {"schema": sibling}
        if target == "form"
        else {
            "schema": {"type": "object", "properties": {"obj": sibling}},
            "encoding": {"obj": {"style": "form"}},
        }
    )
    with pytest.raises(FormMediaError, match="Composed"):
        normalize_form_media(spec, media)


@pytest.mark.parametrize(
    "target",
    [
        "root",
        "styled",
        "styled-property",
        "styled-additional",
        "field",
        "array",
        "array-item",
        "form-additional",
    ],
)
@pytest.mark.parametrize("link", ["outer", "intermediate"])
def test_form_shape_changing_reference_siblings_are_rejected(
    target: str, link: str
) -> None:
    base = (
        {"type": "object"}
        if target in ("root", "styled")
        else {"type": "array", "items": {"type": "string"}}
        if target == "array"
        else {"type": "string"}
    )
    sibling_key = (
        "properties"
        if target in ("root", "styled")
        else "items"
        if target == "array"
        else "type"
    )
    sibling_value = (
        {"name": {"type": "string"}}
        if sibling_key == "properties"
        else {"type": "integer"}
        if sibling_key == "items"
        else "integer"
    )
    schema = {"$ref": "#/components/schemas/Base", sibling_key: sibling_value}
    spec = {"openapi": "3.2.1", "components": {"schemas": {"Base": base}}}
    if link == "intermediate":
        spec["components"]["schemas"]["Middle"] = schema
        schema = {"$ref": "#/components/schemas/Middle"}
    if target == "root":
        media = {"schema": schema}
    elif target == "styled":
        media = {
            "schema": {"type": "object", "properties": {"f": schema}},
            "encoding": {"f": {"style": "form"}},
        }
    elif target in ("styled-property", "styled-additional"):
        obj = (
            {"type": "object", "properties": {"x": schema}}
            if target == "styled-property"
            else {"type": "object", "additionalProperties": schema}
        )
        media = {
            "schema": {"type": "object", "properties": {"f": obj}},
            "encoding": {"f": {"style": "form"}},
        }
    elif target == "array-item":
        media = {
            "schema": {
                "type": "object",
                "properties": {"f": {"type": "array", "items": schema}},
            }
        }
    elif target == "form-additional":
        media = {"schema": {"type": "object", "additionalProperties": schema}}
    else:
        media = {"schema": {"type": "object", "properties": {"f": schema}}}
    with pytest.raises(FormMediaError, match="sibling"):
        normalize_form_media(spec, media)


@pytest.mark.parametrize(
    "marker",
    [
        {"format": "binary"},
        {"format": "byte"},
        {"contentEncoding": "base64"},
        {"contentMediaType": "application/octet-stream"},
    ],
)
@pytest.mark.parametrize(
    "target",
    ["field", "array-item", "styled-property", "styled-additional", "form-additional"],
)
@pytest.mark.parametrize("link", ["outer", "intermediate"])
def test_form_reference_binary_siblings_are_rejected(
    marker: dict, target: str, link: str
) -> None:
    spec = {"openapi": "3.2.1", "components": {"schemas": {"Base": {"type": "string"}}}}
    ref = {"$ref": "#/components/schemas/Base", **marker}
    if link == "intermediate":
        spec["components"]["schemas"]["Middle"] = ref
        ref = {"$ref": "#/components/schemas/Middle"}
    if target == "array-item":
        field = {"type": "array", "items": ref}
    elif target in ("styled-property", "styled-additional"):
        field = (
            {"type": "object", "properties": {"x": ref}}
            if target == "styled-property"
            else {"type": "object", "additionalProperties": ref}
        )
    else:
        field = ref
    media = (
        {"schema": {"type": "object", "additionalProperties": field}}
        if target == "form-additional"
        else {"schema": {"type": "object", "properties": {"f": field}}}
    )
    if target.startswith("styled-"):
        media["encoding"] = {"f": {"style": "form"}}
    with pytest.raises(FormMediaError, match="Binary"):
        normalize_form_media(spec, media)


@pytest.mark.parametrize("location", ["querystring", "body"])
@pytest.mark.parametrize(
    "case",
    [
        "root-properties",
        "root-required",
        "field-type",
        "item-binary",
        "styled-additional",
    ],
)
def test_form_reference_sibling_diagnostics_follow_policy(
    location: str, case: str
) -> None:
    components = {"Root": {"type": "object"}, "Field": {"type": "string"}}
    if case == "root-properties":
        media = {
            "schema": {
                "$ref": "#/components/schemas/Root",
                "properties": {"name": {"type": "string"}},
                "required": ["name"],
            }
        }
    elif case == "root-required":
        media = {"schema": {"$ref": "#/components/schemas/Root", "required": ["name"]}}
    else:
        ref = (
            {"$ref": "#/components/schemas/Field", "type": "integer"}
            if case == "field-type"
            else {"$ref": "#/components/schemas/Field", "contentEncoding": "base64"}
        )
        field = (
            {"type": "array", "items": ref}
            if case == "item-binary"
            else {"type": "object", "additionalProperties": ref}
            if case == "styled-additional"
            else ref
        )
        media = {"schema": {"type": "object", "properties": {"f": field}}}
        if case == "styled-additional":
            media["encoding"] = {"f": {"style": "form"}}
    operation = {"operationId": "send", "responses": {"200": {"description": "OK"}}}
    if location == "querystring":
        operation["parameters"] = [
            {
                "name": "whole",
                "in": "querystring",
                "content": {"application/x-www-form-urlencoded": media},
            }
        ]
    else:
        operation["requestBody"] = {
            "content": {"application/x-www-form-urlencoded": media}
        }
    spec = {
        "openapi": "3.2.1",
        "components": {"schemas": components},
        "paths": {"/send": {"post": operation}},
    }
    with pytest.raises(MappingError, match=r"sibling|Binary"):
        Mapper(spec).map_tools()
    issues = DoctorAnalyzer(spec).analyze("inline").issues
    assert any(
        issue.code == "unsupported_openapi_construct"
        and ("sibling" in issue.hint or "Binary" in issue.hint)
        for issue in issues
    )
    mapper = Mapper(spec, on_mapping_error="skip")
    assert mapper.map_tools() == []
    assert len(mapper.get_report()["skipped_operations"]) == 1
    policy = PolicyConfig(
        source_path=Path("policy.yaml"),
        exclude=SelectorSet(operations=frozenset({"POST /send"})),
    )
    trace: list[dict] = []
    assert Mapper(spec, policy_config=policy, trace=trace).map_tools() == []
    assert trace[0]["status"] == "excluded_before_mapping"


def test_opaque_object_reference_sibling_validation_is_preserved() -> None:
    from jsonschema import Draft202012Validator  # noqa: PLC0415

    inner = {
        "$ref": "#/components/schemas/Base",
        "properties": {"name": {"type": "string"}},
        "required": ["name"],
    }
    media = {"schema": {"type": "object", "properties": {"obj": inner}}}
    spec = {
        "openapi": "3.2.1",
        "components": {"schemas": {"Base": {"type": "object"}}},
        "paths": {
            "/send": {
                "post": {
                    "operationId": "send",
                    "requestBody": {
                        "content": {"application/x-www-form-urlencoded": media}
                    },
                    "responses": {"200": {"description": "OK"}},
                }
            }
        },
    }
    tool = Mapper(spec).map_tools()[0]
    assert (
        tool["_original_request_body"]["form"]["fields"]["obj"]["contentType"]
        == "application/json"
    )
    validator = Draft202012Validator(tool["inputSchema"])
    assert validator.is_valid({"requestBody": {"obj": {"name": "valid"}}})
    assert not validator.is_valid({"requestBody": {"obj": {}}})


def test_form_reference_nonstructural_siblings_remain_supported() -> None:
    spec = {
        "openapi": "3.2.1",
        "components": {
            "schemas": {
                "Root": {
                    "type": "object",
                    "properties": {
                        "f": {"$ref": "#/components/schemas/Field", "maxLength": 20}
                    },
                },
                "Field": {"type": "string"},
            }
        },
    }
    media = {
        "schema": {"$ref": "#/components/schemas/Root", "description": "Form input"}
    }
    field = normalize_form_media(spec, media)["fields"]["f"]
    assert field["kind"] == "string"
    assert field["mode"] == "content"


@pytest.mark.parametrize(
    ("keyword", "value"),
    [
        ("patternProperties", {"^x": {"type": "string"}}),
        ("dependentSchemas", {"flag": {"properties": {"x": {"type": "string"}}}}),
        ("dependencies", {"flag": {"properties": {"x": {"type": "string"}}}}),
        ("if", {"properties": {"flag": {"const": True}}}),
        ("then", {"properties": {"x": {"type": "string"}}}),
        ("else", {"properties": {"y": {"type": "string"}}}),
    ],
)
@pytest.mark.parametrize("target", ["root", "styled"])
@pytest.mark.parametrize("use_ref", [False, True])
def test_expanded_form_layout_applicators_rejected(
    keyword: str, value: object, target: str, *, use_ref: bool
) -> None:
    schema = {
        "type": "object",
        "properties": {"flag": {"type": "boolean"}},
        keyword: value,
    }
    spec = {"openapi": "3.2.1", "components": {"schemas": {"Object": schema}}}
    obj = {"$ref": "#/components/schemas/Object"} if use_ref else schema
    media = (
        {"schema": obj}
        if target == "root"
        else {
            "schema": {"type": "object", "properties": {"obj": obj}},
            "encoding": {"obj": {"style": "form"}},
        }
    )
    with pytest.raises(FormMediaError, match="layout"):
        normalize_form_media(spec, media)


@pytest.mark.parametrize(
    ("keyword", "value"),
    [
        ("patternProperties", {"^x": {"type": "string"}}),
        ("dependentSchemas", {"flag": {"properties": {"x": {"type": "string"}}}}),
        ("if", {"properties": {"flag": {"const": True}}}),
    ],
)
def test_opaque_json_object_layout_applicators_preserved(
    keyword: str, value: object
) -> None:
    media = {
        "schema": {
            "type": "object",
            "properties": {"obj": {"type": "object", keyword: value}},
        }
    }
    assert (
        normalize_form_media({"openapi": "3.2.1"}, media)["fields"]["obj"][
            "contentType"
        ]
        == "application/json"
    )


def test_expanded_object_validation_only_constraints_are_supported() -> None:
    media = {
        "schema": {
            "type": "object",
            "properties": {"a": {"type": "string"}},
            "dependentRequired": {"a": ["b"]},
            "propertyNames": {"type": "string"},
            "dependencies": {"a": ["b"]},
        }
    }
    assert (
        normalize_form_media({"openapi": "3.2.1"}, media)["fields"]["a"]["kind"]
        == "string"
    )


@pytest.mark.parametrize("location", ["querystring", "body"])
@pytest.mark.parametrize(
    "keyword", ["patternProperties", "dependentSchemas", "dependencies", "if"]
)
def test_expanded_applicators_report_mapping_and_doctor(
    location: str, keyword: str
) -> None:
    values = {
        "patternProperties": {"^x": {"type": "string"}},
        "dependentSchemas": {"a": {"properties": {"x": {"type": "string"}}}},
        "dependencies": {"a": {"properties": {"x": {"type": "string"}}}},
        "if": {"properties": {"a": {"const": "x"}}},
    }
    media = {"schema": {"$ref": "#/components/schemas/Root"}}
    op = {"operationId": "send", "responses": {"200": {"description": "OK"}}}
    if location == "querystring":
        op["parameters"] = [
            {
                "name": "whole",
                "in": "querystring",
                "content": {"application/x-www-form-urlencoded": media},
            }
        ]
    else:
        op["requestBody"] = {"content": {"application/x-www-form-urlencoded": media}}
    spec = {
        "openapi": "3.2.1",
        "components": {
            "schemas": {"Root": {"type": "object", keyword: values[keyword]}}
        },
        "paths": {"/send": {"post": op}},
    }
    with pytest.raises(MappingError, match="layouts"):
        Mapper(spec).map_tools()
    assert any(
        issue.code == "unsupported_openapi_construct" and "layouts" in issue.hint
        for issue in DoctorAnalyzer(spec).analyze("inline").issues
    )
    mapper = Mapper(spec, on_mapping_error="skip")
    assert mapper.map_tools() == []
    assert "layouts" in mapper.get_report()["skipped_operations"][0]["reason"]
    policy = PolicyConfig(
        source_path=Path("policy.yaml"),
        exclude=SelectorSet(operations=frozenset({"POST /send"})),
    )
    assert Mapper(spec, policy_config=policy).map_tools() == []
