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
- `AUTH_BASICAUTH_USERNAME`
- `AUTH_BASICAUTH_PASSWORD`

Supported mapping today:

- `apiKey` in `header`
- `apiKey` in `query`
- `apiKey` in `cookie`
- HTTP bearer auth
- HTTP Basic auth
- OAuth2 token injection
- OpenID Connect token injection

## HTTP Basic authentication

For an OpenAPI 3 security scheme named `BasicAuth`:

```yaml
components:
  securitySchemes:
    BasicAuth:
      type: http
      scheme: basic
security:
  - BasicAuth: []
```

Set `AUTH_BASICAUTH_USERNAME` and `AUTH_BASICAUTH_PASSWORD` in the server's
environment or `.env` file. Scheme names are uppercased, then characters outside
`A-Z` and `0-9` become underscores (for example, `basic-auth` becomes
`AUTH_BASIC_AUTH_USERNAME`, and `Básic-Auth` becomes `AUTH_B_SIC_AUTH_USERNAME`).
These variables configure credentials sent to the upstream API; they do not
authenticate incoming MCP clients.

The runtime requires a nonempty username and a defined password. An explicitly
empty password is supported for APIs that use a token as the username. Spaces
are preserved, and passwords may contain colons. Usernames cannot contain colons;
neither value may contain ASCII control characters. Missing or invalid values
produce nonretryable `missing_credentials` or `invalid_credentials` tool errors
before an upstream request. Diagnostics identify variables without exposing values.

Credentials are encoded as UTF-8 Base64 in the `Authorization: Basic` header.
There is no challenge negotiation or legacy character-set fallback. Use HTTPS
for upstream connections: Base64 is encoding, not encryption.
The generated header takes precedence over `TARGET_API_AUTH_HEADER`, and the
Authorization header is redacted in audit logs by default. See
[RFC 7617](https://www.rfc-editor.org/rfc/rfc7617.html) for the Basic scheme.

Security requirement alternatives (OR), combined schemes (AND), and explicit
public operations follow the same rules as the other supported auth types.
Combined schemes cannot send different values in the same HTTP header (header
names are case-insensitive). For example, Basic and Bearer cannot both occupy
`Authorization`. Doctor warns about shared auth headers; the runtime rejects
conflicting values with `invalid_credentials` or tries the next alternative.
Swagger 2 security definitions still require conversion or a policy override
using supported OpenAPI 3 security metadata.

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
