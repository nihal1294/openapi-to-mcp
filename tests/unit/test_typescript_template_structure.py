from __future__ import annotations

import re
from pathlib import Path

MAX_FUNCTION_LINES = 50
ERRORS_TEMPLATE = Path("openapi_to_mcp/templates/src/runtime/errors.ts.j2")
FUNCTION_START = re.compile(
    r"^(?:export\s+)?(?:async\s+)?function\s+(?P<name>[A-Za-z_$][\w$]*)\s*\(",
    re.MULTILINE,
)


def _matching_delimiter(source: str, start: int, opening: str, closing: str) -> int:
    depth = 0
    for offset in range(start, len(source)):
        if source[offset] == opening:
            depth += 1
        elif source[offset] == closing:
            depth -= 1
        if depth == 0:
            return offset
    raise AssertionError(f"Unclosed {opening!r} at offset {start}")


def _function_lengths(source: str) -> dict[str, int]:
    lengths: dict[str, int] = {}
    for match in FUNCTION_START.finditer(source):
        parameters_end = _matching_delimiter(source, match.end() - 1, "(", ")")
        body_start = source.index("{", parameters_end)
        body_end = _matching_delimiter(source, body_start, "{", "}")
        start_line = source.count("\n", 0, match.start()) + 1
        end_line = source.count("\n", 0, body_end) + 1
        lengths[match.group("name")] = end_line - start_line + 1
    return lengths


def test_error_template_functions_stay_within_structural_limit() -> None:
    source = ERRORS_TEMPLATE.read_text(encoding="utf-8")
    oversized = {
        name: lines
        for name, lines in _function_lengths(source).items()
        if lines > MAX_FUNCTION_LINES
    }

    assert oversized == {}
