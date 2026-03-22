# Generated Project

A generated project is a standalone Node.js/TypeScript MCP server.

## Typical output

```text
<output-dir>/
  README.md
  package.json
  tsconfig.json
  .env.example
  generation_report.json
  src/
```

## Key files

- `src/index.ts`: runtime entrypoint
- `src/server.ts`: thin MCP server shell and request wiring
- `src/custom/tools.ts`: preserved custom tool entry point for user-owned extensions
- `src/runtime/generated.ts`: public tool definitions and runtime metadata registry
- `src/runtime/executor.ts`: HTTP execution, concurrency, auth, and request shaping
- `src/runtime/*.ts`: focused generated runtime helpers for config, validation, auth, errors, and serialization
- `src/transport.ts`: selected transport implementation
- `.env.example`: generated runtime and auth placeholders
- `generation_report.json`: warnings, skipped operations, mapped tool count, and applied policy file
- generated `README.md`: build/run instructions for the emitted project

## Transport model

Only two generation targets exist:

- `stdio`
- `streamable-http`

SSE generation is intentionally gone.

## Runtime behavior included today

- parameter metadata for serialization
- generated security scheme env resolution
- bounded concurrency and queue controls
- tool timeout with abort propagation
- streamable HTTP host and origin allowlist handling
- fail-fast startup validation for base URL and runtime-control env values
- runtime input validation against generated `inputSchema` by default
- shaped tool descriptions from operation summaries, descriptions, and fallbacks
- generated input examples from parameter, request-body, default, and enum metadata when available
- optional grouped tool names via first-tag prefixes when generation enables `tool_grouping=tag-prefix`
- optional request-scoped tool allowlists keyed by caller identity for `streamable-http`
- optional stderr audit events with deterministic redaction for headers, query params,
  cookie names, request bodies, and response bodies
- optional in-memory response caching for safe methods (`GET`, `HEAD`, `OPTIONS`)
- optional per-tool fixed-window rate limiting for safe methods
- optional retry budgets and bounded retries for safe methods
- optional circuit breakers with open, half-open, and closed state for safe methods
- optional reviewable performance presets for runtime defaults
- circuit-breaker state is process-local and resets on process restart
- bounded cache size via `MCP_CACHE_MAX_ENTRIES`
- object-shaped response schemas emitted as MCP `outputSchema`
- structured JSON object results returned as `structuredContent`
- structured tool-error results with machine-readable metadata under `meta.error`
- per-tool request IDs exposed under `meta.requestId` and forwarded upstream as `X-Request-Id`
- structured JSON runtime logs for tool start, success, and failure events
- optional `tool_audit_request` and `tool_audit_response` events with redacted payloads
- auth-derived cookie values redacted by default in audit events
- `tool_audit_response` emitted for cached successes and non-HTTP failures
- optional per-tool execution overrides for concurrency, timeout, cache TTL, and rate limit
- optional per-tool execution overrides for retry counts, retry budgets, and circuit-breaker settings
- tool list filtering and structured denial errors for disallowed tool calls when access control is enabled

When access control is enabled:

- identity values are exact, case-sensitive matches
- `stdio` uses the reserved `stdio` identity
- `streamable-http` resolves identity per request, and sessions are not bound to the
  identity observed during initialization

`meta.error.retryable` is advisory only. It tells callers whether an immediate retry is
reasonable, but it does not guarantee success on retry and does not imply any backoff policy.
When retry budgets or circuit breakers reject a call, `meta.error` also includes
structured runtime metadata such as `retryAfterMs` and `attempts` when available.
Circuit-breaker cooldown only applies when the configured failure threshold is positive.

`MCP_PERFORMANCE_PRESET` currently expands to these global defaults:

- `conservative`: `16 / 4 / 64 / 2000 / 20000 / 0 / 500 / 30 / 0 / 0 / 0 / 30000`
- `balanced`: `32 / 8 / 256 / 5000 / 30000 / 30000 / 1000 / 60 / 1 / 30 / 3 / 15000`
- `aggressive`: `64 / 16 / 512 / 8000 / 45000 / 120000 / 2000 / 120 / 2 / 60 / 5 / 10000`

Those values correspond to:

- max concurrency
- per-tool concurrency
- queue size
- queue timeout
- tool timeout
- cache TTL
- cache max entries
- rate limit
- retry max retries
- retry budget per minute
- breaker failure threshold
- breaker cooldown

Explicit env vars and per-tool execution overrides still win over preset-expanded values.
Generated `.env.example` files leave preset-backed override vars blank so presets can
take effect without manual cleanup.
The `conservative` preset leaves caching off by default, but if you later enable
`MCP_CACHE_TTL_MS` explicitly it still uses the preset's `500` entry cap unless you
also override `MCP_CACHE_MAX_ENTRIES`.

## Customization boundary

Generated projects reserve `src/custom/` for user-owned extensions.

- `src/custom/tools.ts` is created only when missing
- regeneration does not overwrite files under `src/custom/`
- `src/server.ts` imports custom tools from `src/custom/tools.ts`

Use this boundary for local tools or helper modules you want to keep across regeneration.
Do not edit `src/server.ts` or `src/runtime/*.ts` directly.

## `generation_report.json`

Use the report to check:

- whether strict mode was enabled
- selected transport
- mapped tool count
- skipped operations
- warnings emitted during generation
