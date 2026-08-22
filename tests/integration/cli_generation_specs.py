"""OpenAPI fixtures for CLI generation integration tests."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path


def write_duplicate_operation_spec(path: Path) -> Path:
    """Write a spec whose generated operation names collide."""
    spec = {
        "openapi": "3.0.0",
        "info": {"title": "Generated Name Collision API", "version": "1.0.0"},
        "servers": [{"url": "https://example.com/api"}],
        "paths": {
            "/a-b": {
                "get": {
                    "summary": "Dash path",
                    "responses": {"200": {"description": "OK"}},
                }
            },
            "/a_b": {
                "get": {
                    "summary": "Underscore path",
                    "responses": {"200": {"description": "OK"}},
                }
            },
        },
    }
    path.write_text(json.dumps(spec), encoding="utf-8")
    return path


def write_mapping_policy_spec(path: Path) -> Path:
    """Write a two-operation spec for mapping-error policy tests."""
    spec = {
        "openapi": "3.0.0",
        "info": {"title": "Mapping Policy API", "version": "1.0.0"},
        "servers": [{"url": "https://example.com/api"}],
        "paths": {
            "/ok": {
                "get": {
                    "operationId": "okTool",
                    "responses": {"200": {"description": "OK"}},
                }
            },
            "/bad": {
                "get": {
                    "operationId": "badTool",
                    "responses": {"200": {"description": "OK"}},
                }
            },
        },
    }
    path.write_text(json.dumps(spec), encoding="utf-8")
    return path
