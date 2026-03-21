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
- optional in-memory response caching for safe methods (`GET`, `HEAD`, `OPTIONS`)
- optional per-tool fixed-window rate limiting for safe methods
- bounded cache size via `MCP_CACHE_MAX_ENTRIES`
- object-shaped response schemas emitted as MCP `outputSchema`
- structured JSON object results returned as `structuredContent`
- structured tool-error results with machine-readable metadata under `meta.error`
- per-tool request IDs exposed under `meta.requestId` and forwarded upstream as `X-Request-Id`
- structured JSON runtime logs for tool start, success, and failure events
- optional per-tool execution overrides for concurrency, timeout, cache TTL, and rate limit

`meta.error.retryable` is advisory only. It tells callers whether an immediate retry is
reasonable, but it does not guarantee success on retry and does not imply any backoff policy.

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
