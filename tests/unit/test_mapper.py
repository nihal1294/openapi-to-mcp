from typing import Any

import pytest

from openapi_to_mcp.common.exceptions import MappingError, SchemaError
from openapi_to_mcp.mapping.mapper import Mapper


def _base_spec() -> dict[str, Any]:
    return {
        "openapi": "3.0.0",
        "info": {"title": "Mapper Test", "version": "1.0.0"},
        "paths": {
            "/items/{itemId}": {
                "parameters": [
                    {
                        "name": "itemId",
                        "in": "path",
                        "required": True,
                        "schema": {"type": "string"},
                    },
                    {
                        "name": "locale",
                        "in": "query",
                        "required": False,
                        "schema": {"type": "string"},
                        "style": "form",
                        "explode": True,
                    },
                ],
                "get": {
                    "operationId": "getItem",
                    "summary": "Get item",
                    "parameters": [
                        {
                            "name": "locale",
                            "in": "query",
                            "required": True,
                            "schema": {"type": "string", "enum": ["en", "fr"]},
                            "style": "form",
                            "explode": False,
                            "allowReserved": True,
                        },
                        {
                            "name": "session",
                            "in": "cookie",
                            "required": False,
                            "schema": {"type": "string"},
                            "style": "form",
                            "explode": True,
                        },
                    ],
                    "security": [{"ApiKeyHeader": []}, {"BearerAuth": []}],
                    "responses": {"200": {"description": "OK"}},
                },
            }
        },
        "components": {
            "securitySchemes": {
                "ApiKeyHeader": {"type": "apiKey", "in": "header", "name": "X-API-Key"},
                "BearerAuth": {"type": "http", "scheme": "bearer"},
            }
        },
    }


def test_mapper_initialization_invalid_spec() -> None:
    with pytest.raises(MappingError, match="Invalid OpenAPI specification"):
        Mapper(spec="not-a-dict")


def test_mapper_merges_path_and_operation_parameters_with_override() -> None:
    mapper = Mapper(spec=_base_spec())
    tools = mapper.map_tools()

    assert len(tools) == 1
    tool = tools[0]

    assert tool["name"] == "getItem"
    assert tool["_original_method"] == "GET"
    assert tool["_original_path"] == "/items/{itemId}"

    props = tool["inputSchema"]["properties"]
    assert set(props.keys()) == {"itemId", "locale", "session"}
    assert "itemId" in tool["inputSchema"]["required"]
    assert "locale" in tool["inputSchema"]["required"]

    # Operation-level locale must override path-level locale metadata.
    locale_param = next(
        p for p in tool["_original_parameters"] if p["name"] == "locale"
    )
    assert locale_param["in"] == "query"
    assert locale_param["explode"] is False
    assert locale_param["style"] == "form"
    assert locale_param["allow_reserved"] is True

    cookie_param = next(
        p for p in tool["_original_parameters"] if p["name"] == "session"
    )
    assert cookie_param["in"] == "cookie"


def test_mapper_extracts_operation_security_metadata() -> None:
    mapper = Mapper(spec=_base_spec())
    tool = mapper.map_tools()[0]

    assert tool["_original_security"] == [{"ApiKeyHeader": []}, {"BearerAuth": []}]
    schemes = tool["_original_security_schemes"]
    assert set(schemes.keys()) == {"ApiKeyHeader", "BearerAuth"}
    assert schemes["ApiKeyHeader"]["type"] == "apiKey"
    assert schemes["BearerAuth"]["scheme"] == "bearer"


def test_mapper_duplicate_operation_id_strict_mode_fails() -> None:
    spec = {
        "openapi": "3.0.0",
        "info": {"title": "Dup", "version": "1.0.0"},
        "paths": {
            "/a": {
                "get": {
                    "operationId": "sameName",
                    "responses": {"200": {"description": "OK"}},
                }
            },
            "/b": {
                "get": {
                    "operationId": "sameName",
                    "responses": {"200": {"description": "OK"}},
                }
            },
        },
    }

    mapper = Mapper(spec=spec, strict=True)
    with pytest.raises(MappingError, match="Duplicate tool name"):
        mapper.map_tools()


def test_mapper_duplicate_operation_id_non_strict_dedupes_with_warning() -> None:
    spec = {
        "openapi": "3.0.0",
        "info": {"title": "Dup", "version": "1.0.0"},
        "paths": {
            "/a": {
                "get": {
                    "operationId": "sameName",
                    "responses": {"200": {"description": "OK"}},
                }
            },
            "/b": {
                "get": {
                    "operationId": "sameName",
                    "responses": {"200": {"description": "OK"}},
                }
            },
        },
    }

    mapper = Mapper(spec=spec, strict=False)
    tools = mapper.map_tools()

    assert [tool["name"] for tool in tools] == ["sameName", "sameName_2"]
    report = mapper.get_report()
    assert report["mapped_tools"] == 2
    assert report["skipped_operations"] == []
    assert any("deduped" in warning for warning in report["warnings"])


def test_mapper_non_strict_dedupe_avoids_existing_suffix_collisions() -> None:
    spec = {
        "openapi": "3.0.0",
        "info": {"title": "Dup Suffix", "version": "1.0.0"},
        "paths": {
            "/a": {
                "get": {
                    "operationId": "sameName",
                    "responses": {"200": {"description": "OK"}},
                }
            },
            "/b": {
                "get": {
                    "operationId": "sameName_2",
                    "responses": {"200": {"description": "OK"}},
                }
            },
            "/c": {
                "get": {
                    "operationId": "sameName",
                    "responses": {"200": {"description": "OK"}},
                }
            },
        },
    }

    mapper = Mapper(spec=spec, strict=False)
    tools = mapper.map_tools()

    assert [tool["name"] for tool in tools] == ["sameName", "sameName_2", "sameName_3"]
    report = mapper.get_report()
    assert any("sameName_3" in warning for warning in report["warnings"])


def test_mapper_mapping_fail_overrides_non_strict_dedupe() -> None:
    spec = {
        "openapi": "3.0.0",
        "info": {"title": "Dup Fail", "version": "1.0.0"},
        "paths": {
            "/a": {
                "get": {
                    "operationId": "sameName",
                    "responses": {"200": {"description": "OK"}},
                }
            },
            "/b": {
                "get": {
                    "operationId": "sameName",
                    "responses": {"200": {"description": "OK"}},
                }
            },
        },
    }

    mapper = Mapper(spec=spec, strict=False, on_mapping_error="fail")
    with pytest.raises(MappingError, match="Duplicate tool name"):
        mapper.map_tools()


def test_mapper_mapping_error_skip_overrides_strict() -> None:
    spec = {
        "openapi": "3.0.0",
        "info": {"title": "Skip Override", "version": "1.0.0"},
        "paths": {
            "/ok": {
                "get": {
                    "operationId": "okTool",
                    "responses": {"200": {"description": "OK"}},
                }
            },
            "/bad": {
                "get": {
                    "operationId": ["invalid", "unhashable"],
                    "responses": {"200": {"description": "OK"}},
                }
            },
        },
    }

    mapper = Mapper(spec=spec, strict=True, on_mapping_error="skip")
    tools = mapper.map_tools()

    assert [tool["name"] for tool in tools] == ["okTool"]
    report = mapper.get_report()
    assert report["on_mapping_error"] == "skip"
    assert report["mapped_tools"] == 1
    assert report["skipped_operations"][0]["path"] == "/bad"


def test_mapper_non_strict_skips_invalid_operation_and_reports() -> None:
    spec = {
        "openapi": "3.0.0",
        "info": {"title": "Skip", "version": "1.0.0"},
        "paths": {
            "/ok": {
                "get": {
                    "operationId": "okTool",
                    "responses": {"200": {"description": "OK"}},
                }
            },
            "/bad": {
                "get": {
                    "operationId": ["invalid", "unhashable"],
                    "responses": {"200": {"description": "OK"}},
                }
            },
        },
    }

    mapper = Mapper(spec=spec, strict=False)
    tools = mapper.map_tools()

    assert [tool["name"] for tool in tools] == ["okTool"]
    report = mapper.get_report()
    assert report["mapped_tools"] == 1
    assert len(report["skipped_operations"]) == 1
    assert report["skipped_operations"][0]["method"] == "GET"
    assert report["skipped_operations"][0]["path"] == "/bad"


def test_mapper_schema_error_skip_overrides_strict(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    spec = {
        "openapi": "3.0.0",
        "info": {"title": "Schema Skip", "version": "1.0.0"},
        "paths": {
            "/ok": {
                "get": {
                    "operationId": "okTool",
                    "parameters": [
                        {"name": "q", "in": "query", "schema": {"type": "string"}}
                    ],
                    "responses": {"200": {"description": "OK"}},
                }
            },
            "/bad": {
                "get": {
                    "operationId": "badTool",
                    "parameters": [
                        {
                            "name": "q",
                            "in": "query",
                            "schema": {"type": "string", "description": "raise"},
                        }
                    ],
                    "responses": {"200": {"description": "OK"}},
                }
            },
        },
    }

    def fake_convert(
        schema: dict[str, Any], _: dict[str, Any], *, raise_on_error: bool = False
    ) -> dict[str, Any]:
        if schema.get("description") == "raise":
            raise SchemaError("Broken schema")
        return {"type": "string"}

    monkeypatch.setattr(
        "openapi_to_mcp.mapping.mapper.openapi_schema_to_json_schema", fake_convert
    )
    mapper = Mapper(spec=spec, strict=True, on_schema_error="skip")

    tools = mapper.map_tools()

    assert [tool["name"] for tool in tools] == ["okTool"]
    report = mapper.get_report()
    assert report["on_schema_error"] == "skip"
    assert report["mapped_tools"] == 1
    assert report["skipped_operations"][0]["path"] == "/bad"


def test_mapper_schema_error_fail_overrides_non_strict(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    spec = {
        "openapi": "3.0.0",
        "info": {"title": "Schema Fail", "version": "1.0.0"},
        "paths": {
            "/bad": {
                "get": {
                    "operationId": "badTool",
                    "parameters": [
                        {
                            "name": "q",
                            "in": "query",
                            "schema": {"type": "string", "description": "raise"},
                        }
                    ],
                    "responses": {"200": {"description": "OK"}},
                }
            }
        },
    }

    def fake_convert(
        schema: dict[str, Any], _: dict[str, Any], *, raise_on_error: bool = False
    ) -> dict[str, Any]:
        if schema.get("description") == "raise":
            raise SchemaError("Broken schema")
        return {"type": "string"}

    monkeypatch.setattr(
        "openapi_to_mcp.mapping.mapper.openapi_schema_to_json_schema", fake_convert
    )
    mapper = Mapper(spec=spec, strict=False, on_schema_error="fail")

    with pytest.raises(
        SchemaError, match="Schema error while mapping operation GET /bad"
    ):
        mapper.map_tools()


def test_mapper_invalid_paths_object_raises() -> None:
    mapper = Mapper(
        spec={
            "openapi": "3.0.0",
            "info": {"title": "Invalid", "version": "1.0.0"},
            "paths": "not-a-dict",
        }
    )

    with pytest.raises(MappingError, match="Invalid 'paths' object"):
        mapper.map_tools()
