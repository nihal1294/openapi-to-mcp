# Auth and Environment

Generated projects use `.env` values for runtime configuration.

## Base URL

The generated runtime needs `TARGET_API_BASE_URL`.

Resolution order:

1. explicit `--target-api-base-url`
2. values from `--env-source`
3. generated `.env` / `.env.example`
4. current process environment

If no real base URL can be resolved, startup fails.
If the base URL is present but not an absolute `http` or `https` URL, startup also fails.

## `--env-source` formats

Accepted by `run` and `test-server`:

- JSON string
- path to `.json`
- path to `.env`

Examples:

```bash
--env-source '{"TARGET_API_BASE_URL":"https://example.com/api"}'
--env-source ./runtime.env
--env-source ./runtime.json
```

## Generated auth env vars

Auth env var placeholders are derived from OpenAPI security schemes.

Examples:

- `AUTH_HEADERAPIKEY_API_KEY`
- `AUTH_QUERYAPIKEY_API_KEY`
- `AUTH_COOKIEAPIKEY_API_KEY`
- `AUTH_BEARERAUTH_TOKEN`

Supported mapping today:

- `apiKey` in `header`
- `apiKey` in `query`
- `apiKey` in `cookie`
- HTTP bearer auth
- OAuth2 token injection
- OpenID Connect token injection

## Optional raw auth header

Generated `.env.example` also includes:

```dotenv
#TARGET_API_AUTH_HEADER=Authorization: Bearer YOUR_TOKEN
```

Use this only when a raw header fallback is more practical than the generated scheme-specific variables.

## Generated runtime env keys

Current generated `.env.example` includes:

- `TARGET_API_BASE_URL`
- `TARGET_API_AUTH_HEADER`
- `MCP_HTTP_HOST`
- `MCP_HTTP_PORT`
- `MCP_HTTP_ENDPOINT`
- `MCP_ALLOWED_ORIGINS`
- `MCP_ALLOWED_HOSTS`
- `MCP_MAX_CONCURRENCY`
- `MCP_PER_TOOL_MAX_CONCURRENCY`
- `MCP_MAX_QUEUE_SIZE`
- `MCP_QUEUE_TIMEOUT_MS`
- `MCP_TOOL_TIMEOUT_MS`
- auth env vars derived from the OpenAPI security schemes

Invalid runtime-control values fail fast at startup instead of silently using defaults.

## Security behavior

Generated auth wiring is covered by generated-server E2E tests against a local mock API, including missing-credential failure paths.
