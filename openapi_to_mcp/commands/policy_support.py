"""Command helpers for `mcpgen.yaml` support."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import rich_click as click

from openapi_to_mcp.policy import load_policy_config, resolve_generation_settings

if TYPE_CHECKING:
    from openapi_to_mcp.policy.models import PolicyConfig


def load_policy_and_settings(
    cli_values: dict[str, Any],
    config_path: str | None,
) -> tuple[PolicyConfig | None, dict[str, Any]]:
    """Load policy config and resolve generation defaults against CLI values."""
    ctx = click.get_current_context()
    policy = load_policy_config(config_path)
    return policy, resolve_generation_settings(ctx, policy, cli_values)
