from __future__ import annotations

import re
from re import Match
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Iterable, Mapping


def generate_tool_name(method: str, path: str) -> str:
    """
    Generate a valid MCP tool name from an HTTP method and path.

    Args:
        method: HTTP method (GET, POST, etc.)
        path: URL path, potentially with path parameters in {braces}

    Returns:
        A valid MCP tool name in the format "method_path_by_param"
    """
    # Normalize method to lowercase
    method_part = method.lower()

    # Handle query parameters and normalize path
    if "?" in path:
        # Include the query part in the name
        path_parts = path.split("?")
        # Parse the query string
        query_part = path_parts[1]
        # If the format is param=value, extract only the value part
        if "=" in query_part:
            query_parts = query_part.split("=")
            # We only use the value to avoid duplication like query_query_term
            path_part = f"{path_parts[0].strip('/')}_query_{query_parts[1]}"
        else:
            # If no equals sign, use the whole query part
            path_part = f"{path_parts[0].strip('/')}_query_{query_part}"
    else:
        path_part = path.strip("/")

    # Handle empty path
    if not path_part:
        return f"{method_part}_root"

    # Replace path parameters {param} with _by_param
    def param_replacer(match: Match[str]) -> str:
        param_name = match.group(1)
        # Replace dots and hyphens in parameter names
        clean_param = re.sub(r"[.-]", "_", param_name)
        return f"_by_{clean_param}"

    path_part = re.sub(r"\{([^}]+)\}", param_replacer, path_part)

    # Replace invalid characters with underscores
    path_part = re.sub(r"[^a-zA-Z0-9_]", "_", path_part)

    # Collapse multiple underscores to single ones
    path_part = re.sub(r"_+", "_", path_part)

    # Remove leading underscore if exists
    path_part = path_part.lstrip("_")

    # Combine method and path
    return f"{method_part}_{path_part}"


def next_available_tool_name(
    candidate_name: str,
    used_names: set[str],
    name_counts: Mapping[str, int],
) -> str:
    """Return the deterministic non-strict name available for one candidate."""
    if candidate_name not in used_names:
        return candidate_name
    count = name_counts.get(candidate_name, 1)
    while True:
        count += 1
        allocated_name = f"{candidate_name}_{count}"
        if allocated_name not in used_names:
            return allocated_name


def allocate_tool_names(candidate_names: Iterable[str]) -> list[str]:
    """Allocate deterministic non-strict pre-rename names in source order."""
    used_names: set[str] = set()
    name_counts: dict[str, int] = {}
    allocated_names: list[str] = []
    for candidate_name in candidate_names:
        allocated_name = next_available_tool_name(
            candidate_name, used_names, name_counts
        )
        used_names.add(allocated_name)
        if allocated_name == candidate_name:
            name_counts[candidate_name] = max(name_counts.get(candidate_name, 0), 1)
        else:
            name_counts[candidate_name] = int(
                allocated_name.removeprefix(f"{candidate_name}_")
            )
        allocated_names.append(allocated_name)
    return allocated_names
