from __future__ import annotations

import json
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path


def write_query_spec(path: Path) -> Path:
    parameters = [
        _parameter("preserved", allow_reserved=True),
        _parameter("encoded"),
        _parameter("percent", allow_reserved=True),
        _parameter("space", allow_reserved=True),
        _parameter("danger", allow_reserved=True),
        {
            "name": "tags",
            "in": "query",
            "style": "form",
            "explode": True,
            "schema": {"type": "array", "items": {"type": "string"}},
        },
        {
            "name": "filters",
            "in": "query",
            "style": "form",
            "explode": True,
            "allowReserved": True,
            "schema": {"type": "object", "additionalProperties": {"type": "string"}},
        },
        {
            "name": "deep",
            "in": "query",
            "style": "deepObject",
            "schema": {"type": "object", "properties": {"name": {"type": "string"}}},
        },
        {
            "name": "qObject",
            "in": "query",
            "style": "form",
            "explode": True,
            "schema": {"type": "object", "properties": {"q": {"type": "string"}}},
        },
        _parameter("q"),
        _parameter("foo[]"),
        _parameter("foo"),
        _parameter("auth[]"),
    ]
    spec = {
        "openapi": "3.0.0",
        "info": {"title": "Query", "version": "1.0.0"},
        "components": {
            "securitySchemes": {
                "queryAuth": {"type": "apiKey", "in": "query", "name": "auth"}
            }
        },
        "paths": {
            "/search": {
                "get": {
                    "operationId": "search",
                    "parameters": parameters,
                    "security": [{"queryAuth": []}],
                    "responses": {"200": {"description": "OK"}},
                }
            }
        },
    }
    path.write_text(json.dumps(spec), encoding="utf-8")
    return path


def _parameter(name: str, *, allow_reserved: bool = False) -> dict[str, object]:
    parameter: dict[str, object] = {
        "name": name,
        "in": "query",
        "schema": {"type": "string"},
    }
    if allow_reserved:
        parameter["allowReserved"] = True
    return parameter
