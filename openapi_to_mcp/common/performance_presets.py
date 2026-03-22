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
        "conservative", 16, 4, 64, 2000, 20000, 0, 500, 30, 0, 0, 0, 30000
    ),
    PerformancePreset(
        "balanced", 32, 8, 256, 5000, 30000, 30000, 1000, 60, 1, 30, 3, 15000
    ),
    PerformancePreset(
        "aggressive", 64, 16, 512, 8000, 45000, 120000, 2000, 120, 2, 60, 5, 10000
    ),
)
PERFORMANCE_PRESET_NAMES = ("off", *(preset.name for preset in PERFORMANCE_PRESETS))


def performance_preset_context() -> list[dict[str, int | str]]:
    """Return preset rows suitable for template rendering."""
    return [asdict(preset) for preset in PERFORMANCE_PRESETS]
