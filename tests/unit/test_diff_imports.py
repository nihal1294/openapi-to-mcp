from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest


@pytest.mark.parametrize(
    "imports",
    [
        "from openapi_to_mcp.diff import DiffAnalyzer",
        "from openapi_to_mcp.diff.surface import build_tool_surfaces\nfrom openapi_to_mcp.diff import DiffAnalyzer",
        "from openapi_to_mcp.cli import cli\nfrom openapi_to_mcp.diff import DiffAnalyzer",
    ],
)
def test_diff_import_orders_in_fresh_interpreter(imports: str) -> None:
    script = (
        imports
        + """
spec = {"openapi": "3.0.0", "info": {"title": "Test", "version": "1"}, "paths": {
    "/pets": {"get": {"operationId": "listPets", "responses": {"200": {"description": "OK"}}}}
}}
report = DiffAnalyzer(spec, spec).analyze("before", "after")
assert report.changes == []
"""
    )
    result = subprocess.run(  # noqa: S603
        [sys.executable, "-c", script],
        cwd=Path(__file__).resolve().parents[2],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
