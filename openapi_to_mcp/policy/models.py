"""Typed models for mcpgen policy configuration."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from pathlib import Path


@dataclass(frozen=True)
class GenerationDefaults:
    """Generation defaults sourced from `mcpgen.yaml`."""

    mcp_server_name: str | None = None
    mcp_server_version: str | None = None
    tool_grouping: str | None = None
    transport: str | None = None
    host: str | None = None
    port: int | None = None
    mcp_endpoint: str | None = None
    strict: bool | None = None
    runtime_validation: str | None = None
    on_mapping_error: str | None = None
    on_schema_error: str | None = None


@dataclass(frozen=True)
class SelectorSet:
    """Selectors for tool names and operation keys."""

    operations: frozenset[str] = field(default_factory=frozenset)
    names: frozenset[str] = field(default_factory=frozenset)

    @property
    def is_empty(self) -> bool:
        """Return whether the selector set contains any selectors."""
        return not self.operations and not self.names


@dataclass(frozen=True)
class AuthOverride:
    """Per-tool auth override policy."""

    security: list[dict[str, Any]] | None = None
    security_schemes: dict[str, dict[str, Any]] | None = None


@dataclass(frozen=True)
class ExecutionOverride:
    """Per-tool execution limits attached to generated runtime metadata."""

    max_concurrency: int | None = None
    timeout_ms: int | None = None
    cache_ttl_ms: int | None = None
    rate_limit_per_minute: int | None = None
    retry_max_retries: int | None = None
    retry_budget_per_minute: int | None = None
    circuit_breaker_failure_threshold: int | None = None
    circuit_breaker_cooldown_ms: int | None = None


@dataclass(frozen=True)
class PolicyConfig:
    """Resolved `mcpgen.yaml` policy configuration."""

    source_path: Path
    generation: GenerationDefaults = field(default_factory=GenerationDefaults)
    include: SelectorSet = field(default_factory=SelectorSet)
    exclude: SelectorSet = field(default_factory=SelectorSet)
    rename_operations: dict[str, str] = field(default_factory=dict)
    rename_names: dict[str, str] = field(default_factory=dict)
    auth_operations: dict[str, AuthOverride] = field(default_factory=dict)
    auth_names: dict[str, AuthOverride] = field(default_factory=dict)
    execution_operations: dict[str, ExecutionOverride] = field(default_factory=dict)
    execution_names: dict[str, ExecutionOverride] = field(default_factory=dict)
