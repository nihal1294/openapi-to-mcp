"""Shared generated runtime performance preset definitions."""

from __future__ import annotations

from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class PerformancePreset:
    """Reviewable preset values for generated runtime controls."""

    name: str
    max_concurrency: int
    per_tool_max_concurrency: int
    max_queue_size: int
    queue_timeout_ms: int
    tool_timeout_ms: int
    cache_ttl_ms: int
    cache_max_entries: int
    rate_limit_per_minute: int
    retry_max_retries: int
    retry_budget_per_minute: int
    circuit_breaker_failure_threshold: int
    circuit_breaker_cooldown_ms: int


PERFORMANCE_PRESETS = (
    PerformancePreset(
        name="conservative",
        max_concurrency=16,
        per_tool_max_concurrency=4,
        max_queue_size=64,
        queue_timeout_ms=2000,
        tool_timeout_ms=20000,
        cache_ttl_ms=0,
        cache_max_entries=500,
        rate_limit_per_minute=30,
        retry_max_retries=0,
        retry_budget_per_minute=0,
        circuit_breaker_failure_threshold=0,
        circuit_breaker_cooldown_ms=30000,
    ),
    PerformancePreset(
        name="balanced",
        max_concurrency=32,
        per_tool_max_concurrency=8,
        max_queue_size=256,
        queue_timeout_ms=5000,
        tool_timeout_ms=30000,
        cache_ttl_ms=30000,
        cache_max_entries=1000,
        rate_limit_per_minute=60,
        retry_max_retries=1,
        retry_budget_per_minute=30,
        circuit_breaker_failure_threshold=3,
        circuit_breaker_cooldown_ms=15000,
    ),
    PerformancePreset(
        name="aggressive",
        max_concurrency=64,
        per_tool_max_concurrency=16,
        max_queue_size=512,
        queue_timeout_ms=8000,
        tool_timeout_ms=45000,
        cache_ttl_ms=120000,
        cache_max_entries=2000,
        rate_limit_per_minute=120,
        retry_max_retries=2,
        retry_budget_per_minute=60,
        circuit_breaker_failure_threshold=5,
        circuit_breaker_cooldown_ms=10000,
    ),
)
PERFORMANCE_PRESET_NAMES = ("off", *(preset.name for preset in PERFORMANCE_PRESETS))


def performance_preset_context() -> list[dict[str, int | str]]:
    """Return preset rows suitable for template rendering."""
    return [asdict(preset) for preset in PERFORMANCE_PRESETS]
