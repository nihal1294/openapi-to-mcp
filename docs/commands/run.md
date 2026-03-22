# `run`

Use `run` when you want one command to generate, install, build, and start the MCP server.

## Command

```bash
openapi-to-mcp run [OPTIONS]
```

## What it does

1. generates a server from the OpenAPI spec,
2. prepares runtime environment values,
3. runs `npm install`,
4. runs `npm run build`,
5. starts `node build/index.js`.

## Options

| Option | Required | Default | Meaning |
| --- | --- | --- | --- |
| `--openapi-json`, `-o` | Yes | None | Local path or URL to a JSON or YAML OpenAPI spec |
| `--config` | No | Auto-discover `mcpgen.yaml` / `mcpgen.yml` | Policy file path for generation defaults and tool policy |
| `--output-dir`, `-d` | No | Temporary directory | Reuse a stable generated project directory |
| `--mcp-server-name`, `-n` | No | Spec title or fallback | Generated MCP server name |
| `--mcp-server-version`, `-v` | No | Spec version or fallback | Generated MCP server version |
| `--transport`, `-t` | No | `streamable-http` | Generated transport target |
| `--host` | No | `127.0.0.1` | Host for `streamable-http` |
| `--port`, `-p` | No | `8080` | Port for `streamable-http` |
| `--mcp-endpoint` | No | `/mcp` | HTTP MCP endpoint path |
| `--strict/--no-strict` | No | `--strict` | Same generation mode as `generate` |
| `--on-mapping-error` | No | strict=`fail`, non-strict=`skip` | How to handle non-schema operation mapping failures during generation |
| `--on-schema-error` | No | strict=`fail`, non-strict=`skip` | How to handle schema conversion failures during generation |
| `--runtime-validation` | No | `input` | Runtime validation mode compiled into the generated server (`none` or `input`) |
| `--tool-grouping` | No | `none` | Optional grouped tool naming strategy (`none` or `tag-prefix`) |
| `--target-api-base-url` | No | None | Override `TARGET_API_BASE_URL` explicitly |
| `--env-source` | No | None | Runtime env values as JSON string or path to `.json` or `.env` |
| `--performance-preset` | No | None | Apply a named bundle of runtime defaults; explicit runtime overrides still win |
| `--origin-allowlist` | No | None | Override `MCP_ALLOWED_ORIGINS` for `streamable-http` |
| `--host-allowlist` | No | None | Override `MCP_ALLOWED_HOSTS` for `streamable-http` |
| `--max-concurrency` | No | None | Override `MCP_MAX_CONCURRENCY` |
| `--per-tool-max-concurrency` | No | None | Override `MCP_PER_TOOL_MAX_CONCURRENCY` |
| `--max-queue-size` | No | None | Override `MCP_MAX_QUEUE_SIZE` |
| `--queue-timeout-ms` | No | None | Override `MCP_QUEUE_TIMEOUT_MS` |
| `--tool-timeout-ms` | No | None | Override `MCP_TOOL_TIMEOUT_MS` |
| `--cache-ttl-ms` | No | None | Override `MCP_CACHE_TTL_MS` for safe tools (`GET`, `HEAD`, `OPTIONS`) |
| `--cache-max-entries` | No | None | Override `MCP_CACHE_MAX_ENTRIES` for bounded in-memory caching |
| `--rate-limit-per-minute` | No | None | Override `MCP_RATE_LIMIT_PER_MINUTE` for safe tools (`GET`, `HEAD`, `OPTIONS`) |
| `--retry-max-retries` | No | None | Override `MCP_RETRY_MAX_RETRIES` for safe tools (`GET`, `HEAD`, `OPTIONS`); retries only activate when retry budget is also positive |
| `--retry-budget-per-minute` | No | None | Override `MCP_RETRY_BUDGET_PER_MINUTE` for safe tools (`GET`, `HEAD`, `OPTIONS`); retries only activate when retry count is also positive |
| `--circuit-breaker-failure-threshold` | No | None | Override `MCP_CIRCUIT_BREAKER_FAILURE_THRESHOLD` for safe tools (`GET`, `HEAD`, `OPTIONS`) |
| `--circuit-breaker-cooldown-ms` | No | None | Override `MCP_CIRCUIT_BREAKER_COOLDOWN_MS` for safe tools (`GET`, `HEAD`, `OPTIONS`); only applies when failure threshold is positive |
| `--tool-access-mode` | No | None | Override `MCP_TOOL_ACCESS_MODE` (`off` or `allowlist`) |
| `--tool-access-default` | No | None | Override `MCP_TOOL_ACCESS_DEFAULT` (`allow` or `deny`) |
| `--tool-identity-header` | No | None | Override `MCP_TOOL_IDENTITY_HEADER` for streamable-http caller identity |
| `--tool-allowlists` | No | None | Override `MCP_TOOL_ALLOWLISTS` with a JSON object mapping identities to tool names |
| `--audit-mode` | No | None | Override `MCP_AUDIT_MODE` (`off` or `logs`) |
| `--audit-redact-headers` | No | None | Override `MCP_AUDIT_REDACT_HEADERS` with comma-separated header names |
| `--audit-redact-query-params` | No | None | Override `MCP_AUDIT_REDACT_QUERY_PARAMS` with comma-separated query names |
| `--audit-redact-cookie-names` | No | None | Override `MCP_AUDIT_REDACT_COOKIE_NAMES` with comma-separated cookie names |
| `--audit-redact-request-body-paths` | No | None | Override `MCP_AUDIT_REDACT_REQUEST_BODY_PATHS` with comma-separated dot paths |
| `--audit-redact-response-body-paths` | No | None | Override `MCP_AUDIT_REDACT_RESPONSE_BODY_PATHS` with comma-separated dot paths |

## Examples

### Remote spec with explicit API base URL

```bash
openapi-to-mcp run \
  --openapi-json https://petstore.swagger.io/v2/swagger.json \
  --target-api-base-url https://petstore.swagger.io/v2
```

### Local spec with reusable output directory

```bash
openapi-to-mcp run \
  --openapi-json ./openapi.yaml \
  --output-dir ./generated-runtime \
  --env-source ./runtime.env
```

### Local spec with inline env JSON

```bash
openapi-to-mcp run \
  --openapi-json ./openapi.yaml \
  --env-source '{"TARGET_API_BASE_URL":"https://example.com/api"}'
```

### Run with policy defaults from `mcpgen.yaml`

```bash
openapi-to-mcp run \
  --openapi-json ./openapi.yaml \
  --config ./mcpgen.yaml \
  --target-api-base-url https://example.com/api
```

Explicit CLI values still override policy defaults.

### Keep going on mapping failures while staying strict elsewhere

```bash
openapi-to-mcp run \
  --openapi-json ./openapi.yaml \
  --on-mapping-error skip \
  --target-api-base-url https://example.com/api
```

### Run without generated input validation

```bash
openapi-to-mcp run \
  --openapi-json ./openapi.yaml \
  --runtime-validation none \
  --target-api-base-url https://example.com/api
```

### Run with grouped tool names from first tags

```bash
openapi-to-mcp run \
  --openapi-json ./openapi.yaml \
  --tool-grouping tag-prefix \
  --target-api-base-url https://example.com/api
```

### Override runtime controls directly from the CLI

```bash
openapi-to-mcp run \
  --openapi-json ./openapi.yaml \
  --target-api-base-url https://example.com/api \
  --origin-allowlist https://app.example.com,http://localhost:3000 \
  --max-concurrency 64 \
  --per-tool-max-concurrency 16 \
  --tool-timeout-ms 45000
```

### Apply a performance preset with one explicit override

```bash
openapi-to-mcp run \
  --openapi-json ./openapi.yaml \
  --target-api-base-url https://example.com/api \
  --performance-preset balanced \
  --cache-ttl-ms 0
```

`--performance-preset` expands to reviewable defaults. Explicit runtime overrides still
win, so this command keeps the `balanced` preset while disabling caching explicitly.

### Enable safe-method caching and rate limiting

```bash
openapi-to-mcp run \
  --openapi-json ./openapi.yaml \
  --target-api-base-url https://example.com/api \
  --cache-ttl-ms 60000 \
  --cache-max-entries 1000 \
  --rate-limit-per-minute 30
```

Use `0` to disable either control. These controls are ignored for unsafe methods such
as `POST`, `PUT`, `PATCH`, and `DELETE`.
Rate limiting uses a fixed one-minute window, so quota resets at window boundaries.

### Enable safe-method retries and circuit breaking

```bash
openapi-to-mcp run \
  --openapi-json ./openapi.yaml \
  --target-api-base-url https://example.com/api \
  --retry-max-retries 2 \
  --retry-budget-per-minute 10 \
  --circuit-breaker-failure-threshold 3 \
  --circuit-breaker-cooldown-ms 30000
```

Retries and circuit-breaking are limited to safe methods in this first implementation.
Retries are immediate, require both a positive retry count and a positive retry budget,
and the budget counts retry attempts rather than original calls. The circuit breaker
opens after the configured number of consecutive retryable failures and allows one
half-open probe after each cooldown window. Set the failure threshold to `0` to
disable the breaker entirely; the cooldown has no effect until the threshold is
positive. Circuit-breaker state is process-local and resets when the server restarts.

### Performance preset expansions

`--performance-preset` and `MCP_PERFORMANCE_PRESET` currently expand to:

| Preset | Max concurrency | Per-tool | Queue size | Queue timeout ms | Tool timeout ms | Cache TTL ms | Cache max entries | Rate limit/min | Retry max | Retry budget/min | Breaker threshold | Breaker cooldown ms |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `conservative` | 16 | 4 | 64 | 2000 | 20000 | 0 | 500 | 30 | 0 | 0 | 0 | 30000 |
| `balanced` | 32 | 8 | 256 | 5000 | 30000 | 30000 | 1000 | 60 | 1 | 30 | 3 | 15000 |
| `aggressive` | 64 | 16 | 512 | 8000 | 45000 | 120000 | 2000 | 120 | 2 | 60 | 5 | 10000 |

The `conservative` preset leaves caching off by default, but if you later enable
`MCP_CACHE_TTL_MS` explicitly it still uses the preset's `500` entry cap unless you
also override `MCP_CACHE_MAX_ENTRIES`.

### Restrict visible tools by caller identity

```bash
openapi-to-mcp run \
  --openapi-json ./openapi.yaml \
  --target-api-base-url https://example.com/api \
  --tool-access-mode allowlist \
  --tool-access-default deny \
  --tool-identity-header X-MCP-Tenant \
  --tool-allowlists '{"acme":["listPets","getPet"]}'
```

This access model is request-scoped and intended primarily for `streamable-http`.
The reserved identities are:

- `anonymous` for requests without the configured identity header
- `stdio` for stdio transport

Identity values are exact, case-sensitive matches against `MCP_TOOL_ALLOWLISTS`.
For `streamable-http`, identity is resolved from each incoming request. Sessions are not
bound to the identity observed during initialization.

### Emit redacted audit logs

```bash
openapi-to-mcp run \
  --openapi-json ./openapi.yaml \
  --target-api-base-url https://example.com/api \
  --audit-mode logs \
  --audit-redact-headers authorization,x-api-key \
  --audit-redact-query-params token \
  --audit-redact-request-body-paths credentials.token,profile.email \
  --audit-redact-response-body-paths echoed.credentials.token
```

Audit events are emitted on stderr as structured JSON. Header, query, and cookie names
are matched case-insensitively, and auth-derived cookie values are redacted by default.
Body-path redaction only applies to JSON object or array payloads and uses dot notation
with optional `*` array wildcards. Cached successes still emit paired audit events with
`cacheHit: true`. Network and runtime failures emit `tool_audit_response` with
`status: null` when there is no upstream HTTP response.

## `--env-source` formats

Accepted values:

- a JSON string
- a path to a `.json` file
- a path to a `.env` file

`run` copies `.env.example` to `.env` when needed, writes overrides, and then starts
the generated server with resolved runtime values. Generated `.env.example` files
leave preset-backed runtime override vars blank so `MCP_PERFORMANCE_PRESET` can take
effect without manual cleanup.
CLI runtime-control flags are written as the corresponding `MCP_*` env vars before startup.
`MCP_PERFORMANCE_PRESET` defaults to `off`.
`MCP_CACHE_TTL_MS` and `MCP_RATE_LIMIT_PER_MINUTE` both default to `0` (disabled).
`MCP_CACHE_MAX_ENTRIES` defaults to `1000`.
`MCP_RETRY_MAX_RETRIES` and `MCP_RETRY_BUDGET_PER_MINUTE` default to `0` (disabled).
`MCP_CIRCUIT_BREAKER_FAILURE_THRESHOLD` defaults to `0` (disabled).
`MCP_CIRCUIT_BREAKER_COOLDOWN_MS` defaults to `30000`.
`MCP_TOOL_ACCESS_MODE` defaults to `off`, and `MCP_TOOL_ACCESS_DEFAULT` defaults to `allow`.
`MCP_AUDIT_MODE` defaults to `off`.

## Base URL resolution

`TARGET_API_BASE_URL` is resolved from the first usable value in this order:

1. `--target-api-base-url`
2. values supplied by `--env-source`
3. generated `.env` or `.env.example`
4. current process environment

If no real base URL can be resolved, `run` exits early.

## Temporary vs persistent output

- without `--output-dir`, a temporary workspace is used and cleaned up on exit
- with `--output-dir`, the generated project stays on disk

## Validate after startup

In another terminal:

```bash
openapi-to-mcp test-server \
  --transport streamable-http \
  --host 127.0.0.1 \
  --port 8080 \
  --mcp-endpoint /mcp \
  --list-tools
```

## Common failure cases

- unresolved `TARGET_API_BASE_URL`
- invalid runtime-control values such as `MCP_MAX_CONCURRENCY=0`
- invalid `TARGET_API_BASE_URL` values that are not absolute `http` or `https` URLs
- missing local runtime tools such as `node` or `npm`
- `npm install` or `npm run build` failure in the generated project
- invalid `--env-source` value or unreadable env file
