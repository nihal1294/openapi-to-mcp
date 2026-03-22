# OpenAPI to MCP

Standalone CLI for diagnosing, diffing, generating, running, and testing Node.js/TypeScript MCP servers from OpenAPI specifications.

## Install first

Start with [Installation](installation.md), then confirm the binary is available:

```bash
openapi-to-mcp --help
```

## Choose a workflow

| Command | Use it when | Output |
| --- | --- | --- |
| `generate` | You want a reusable generated project on disk | A TypeScript MCP server project |
| `run` | You want one command to generate, build, and start a server locally | A running MCP server |
| `test-server` | You want to smoke-test a running server | `tools/list` or `tools/call` output |
| `doctor` | You want to assess spec readiness before generation | A readiness report with warnings and errors |
| `diff` | You want to compare MCP-surface changes between two specs | A breaking/non-breaking change report |

## First commands to try

Generate a project:

```bash
openapi-to-mcp generate \
  --openapi-json ./openapi.yaml \
  --output-dir ./generated-server
```

Run directly from a spec:

```bash
openapi-to-mcp run \
  --openapi-json https://petstore.swagger.io/v2/swagger.json \
  --target-api-base-url https://petstore.swagger.io/v2
```

List tools from a running server:

```bash
openapi-to-mcp test-server \
  --transport streamable-http \
  --host 127.0.0.1 \
  --port 8080 \
  --mcp-endpoint /mcp \
  --list-tools
```

## Start here

1. [Installation](installation.md)
2. [Getting Started](getting-started.md)
3. [generate](commands/generate.md)
4. [run](commands/run.md)
5. [test-server](commands/test-server.md)
6. [doctor](commands/doctor.md)
7. [diff](commands/diff.md)
8. [Auth and Environment](guides/auth-and-env.md)
9. [mcpgen.yaml](guides/mcpgen-policy.md)
10. [Generated Project](guides/generated-project.md)
11. [Examples](examples.md)
12. [MCP Inspector](guides/mcp-inspector.md)
13. [Troubleshooting](troubleshooting.md)
14. [Local Workflows](guides/local-workflows.md)

## Current capabilities

- `stdio` and `streamable-http` transport targets
- strict generation by default with `generation_report.json`
- richer generated tool descriptions and input examples from spec metadata
- optional grouped tool names with first-tag prefixes
- optional request-scoped tool allowlists for streamable-http callers
- optional redacted audit logs for request and response payloads
- optional retry budgets and circuit breakers for safe upstream calls
- reviewable performance presets built on top of the explicit runtime controls
- generated auth env mapping for `apiKey`, bearer, OAuth2, and OpenID Connect
- generated runtime controls for concurrency, queueing, timeout, bounded caching, rate limiting, retries, and circuit breakers
- generated-server E2E coverage against a local mock API
- CLI E2E coverage for `generate`, `run`, and `test-server`
- version-aware GitHub Releases automation on `master`
- repeatable generation policy with `mcpgen.yaml`
