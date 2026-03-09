from __future__ import annotations

from typing import TYPE_CHECKING

from openapi_to_mcp.common import MappingError
from openapi_to_mcp.diff.surface import build_tool_surfaces

if TYPE_CHECKING:
    import pytest


def test_build_tool_surfaces_rejects_partial_mapper_results(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "openapi_to_mcp.diff.surface.Mapper",
        _FakeMapperWithSkippedSchemas,
    )

    try:
        build_tool_surfaces({"openapi": "3.0.0", "paths": {}})
    except MappingError as exc:
        assert "Spec mapping skipped operation schema" in str(exc)
        assert "GET /pets" in str(exc)
    else:
        raise AssertionError("Expected MappingError for skipped diff surface data.")


class _FakeMapperWithSkippedSchemas:
    def __init__(self, *_: object, **__: object) -> None:
        pass

    def map_tools(self) -> list[dict[str, object]]:
        return []

    def get_report(self) -> dict[str, object]:
        return {
            "skipped_operations": [
                {"method": "GET", "path": "/pets", "reason": "schema failure"}
            ]
        }
