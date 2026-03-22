from openapi_to_mcp.common.performance_presets import (
    PERFORMANCE_PRESET_NAMES,
    PERFORMANCE_PRESETS,
    performance_preset_context,
)


def test_performance_preset_names_and_values_are_stable() -> None:
    assert PERFORMANCE_PRESET_NAMES == (
        "off",
        "conservative",
        "balanced",
        "aggressive",
    )
    assert performance_preset_context() == [
        {
            "name": "conservative",
            "max_concurrency": 16,
            "per_tool_max_concurrency": 4,
            "max_queue_size": 64,
            "queue_timeout_ms": 2000,
            "tool_timeout_ms": 20000,
            "cache_ttl_ms": 0,
            "cache_max_entries": 500,
            "rate_limit_per_minute": 30,
            "retry_max_retries": 0,
            "retry_budget_per_minute": 0,
            "circuit_breaker_failure_threshold": 0,
            "circuit_breaker_cooldown_ms": 30000,
        },
        {
            "name": "balanced",
            "max_concurrency": 32,
            "per_tool_max_concurrency": 8,
            "max_queue_size": 256,
            "queue_timeout_ms": 5000,
            "tool_timeout_ms": 30000,
            "cache_ttl_ms": 30000,
            "cache_max_entries": 1000,
            "rate_limit_per_minute": 60,
            "retry_max_retries": 1,
            "retry_budget_per_minute": 30,
            "circuit_breaker_failure_threshold": 3,
            "circuit_breaker_cooldown_ms": 15000,
        },
        {
            "name": "aggressive",
            "max_concurrency": 64,
            "per_tool_max_concurrency": 16,
            "max_queue_size": 512,
            "queue_timeout_ms": 8000,
            "tool_timeout_ms": 45000,
            "cache_ttl_ms": 120000,
            "cache_max_entries": 2000,
            "rate_limit_per_minute": 120,
            "retry_max_retries": 2,
            "retry_budget_per_minute": 60,
            "circuit_breaker_failure_threshold": 5,
            "circuit_breaker_cooldown_ms": 10000,
        },
    ]
    assert [preset.name for preset in PERFORMANCE_PRESETS] == [
        "conservative",
        "balanced",
        "aggressive",
    ]
