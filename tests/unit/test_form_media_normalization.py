"""Declaration-aware form media normalization."""

from pathlib import Path

import pytest

from openapi_to_mcp.common import MappingError
from openapi_to_mcp.common.form_media import FormMediaError, normalize_form_media
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
