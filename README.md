<p align="center">
  <img src="https://raw.githubusercontent.com/nihal1294/openapi-to-mcp/master/docs/images/openapi-to-mcp.png" alt="OpenAPI to MCP logo" width="200"/>
</p>

<h1 align="center">OpenAPI → MCP Server</h1>

<p align="center">
  <a href="https://github.com/nihal1294/openapi-to-mcp/actions/workflows/ci.yml?query=branch%3Amaster"><img alt="CI" src="https://github.com/nihal1294/openapi-to-mcp/actions/workflows/ci.yml/badge.svg?branch=master"></a>
  <a href="https://pypi.org/project/openapi-to-mcp-cli/"><img alt="PyPI version" src="https://img.shields.io/pypi/v/openapi-to-mcp-cli"></a>
  <a href="https://github.com/nihal1294/openapi-to-mcp/blob/master/LICENSE"><img alt="License" src="https://img.shields.io/github/license/nihal1294/openapi-to-mcp"></a>
</p>

Standalone CLI for diagnosing, diffing, generating, running, and testing Node.js/TypeScript MCP servers from OpenAPI specifications.

## Install

Install [`openapi-to-mcp-cli`](https://pypi.org/project/openapi-to-mcp-cli/) from PyPI. Requires Python 3.14+;
building and running generated servers also requires Node.js 22+ and npm.

```bash
uv tool install openapi-to-mcp-cli
openapi-to-mcp --help
```

The installed command remains `openapi-to-mcp`. For one-off use:

```bash
uvx --from openapi-to-mcp-cli openapi-to-mcp --help
```

See the [installation guide](https://nihal1294.github.io/openapi-to-mcp/installation/)
for upgrades, tagged Git installs, and release artifacts.

## Quickstart

Generate a reusable project:

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

Smoke-test a running server:

```bash
openapi-to-mcp test-server \
  --transport streamable-http \
  --host 127.0.0.1 \
  --port 8080 \
  --mcp-endpoint /mcp \
  --list-tools
```

## Documentation

Public product documentation lives on GitHub Pages:

- Docs home: [nihal1294.github.io/openapi-to-mcp](https://nihal1294.github.io/openapi-to-mcp/)

## Current capabilities

- `stdio` and `streamable-http` generation targets
- spec-readiness diagnostics with `doctor`
- MCP-surface comparison with `diff`
- repeatable generation policy with `mcpgen.yaml`
- regeneration-safe custom tools via `src/custom/tools.ts`
- richer generated tool descriptions and input examples from spec metadata
- optional grouped tool names with first-tag prefixes
- optional request-scoped tool allowlists for streamable-http callers
- optional redacted audit logs for request and response payloads
- optional retry budgets and circuit breakers for safe upstream calls
- reviewable performance presets built on top of the explicit runtime controls
- strict mode by default with `generation_report.json`
- generated auth env mapping for `apiKey`, bearer, OAuth2, and OpenID Connect
- generated runtime controls for concurrency, queueing, timeout, bounded caching, rate limiting, retries, and circuit breakers
- generated-server E2E coverage against a local mock API
- CLI E2E coverage for `generate`, `run`, and `test-server`
- version-aware PyPI and GitHub Releases automation on `master`

## Development

For repository-local workflows, use the repo docs directly:

- source and local workflows: [Local Workflows](https://nihal1294.github.io/openapi-to-mcp/guides/local-workflows/)
- contribution guide: [Contributing](https://github.com/nihal1294/openapi-to-mcp/blob/master/CONTRIBUTING.md)

## License

Apache License 2.0. See [LICENSE](https://github.com/nihal1294/openapi-to-mcp/blob/master/LICENSE).
