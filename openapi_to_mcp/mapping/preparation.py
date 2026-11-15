"""Shared, side-effect-free preparation of generated tool metadata."""

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from openapi_to_mcp.common.tool_runtime import (
    build_public_tools,
    build_runtime_tool_registry,
)
from openapi_to_mcp.mapping import Mapper
from openapi_to_mcp.mapping.tool_grouping import apply_tool_grouping
from openapi_to_mcp.mapping.tool_metadata import (
    apply_description_mode,
    validate_tool_names,
)
from openapi_to_mcp.policy import apply_policy

if TYPE_CHECKING:
    from openapi_to_mcp.commands.generation_models import GenerationBehavior
    from openapi_to_mcp.policy.models import PolicyConfig


@dataclass
class PreparedTools:
    """Mapped tools, projections, diagnostics and optional decision trace."""

    tools: list[dict[str, Any]]
    public_tools: list[dict[str, Any]]
    runtime_registry: dict[str, dict[str, Any]]
    mapper: Mapper
    report: dict[str, Any]
    warnings: list[dict[str, str]]
    trace: list[dict[str, Any]] | None


def prepare_tools(
    spec: dict[str, Any],
    *,
    behavior: GenerationBehavior,
    policy: PolicyConfig | None,
    trace: bool = False,
) -> PreparedTools:
    """Prepare tools using exactly the generation mapping and policy pipeline."""
    rows: list[dict[str, Any]] | None = [] if trace else None
    mapper = Mapper(
        spec=spec,
        strict=behavior.strict,
        on_mapping_error=behavior.on_mapping_error,
        on_schema_error=behavior.on_schema_error,
        policy_config=policy,
        trace=rows,
    )
    tools = apply_description_mode(mapper.map_tools(), behavior.tool_descriptions)
    if rows is not None:
        for row in rows:
            if row["status"] == "selected":
                row["decisions"].append(
                    {"kind": "description_mode", "mode": behavior.tool_descriptions}
                )
    tools = apply_policy(tools, policy, trace=rows)
    tools = apply_tool_grouping(tools, behavior.tool_grouping, trace=rows)
    warnings = validate_tool_names(tools, behavior.tool_name_policy)
    return PreparedTools(
        tools,
        build_public_tools(tools),
        build_runtime_tool_registry(tools),
        mapper,
        mapper.get_report(),
        warnings,
        rows,
    )
