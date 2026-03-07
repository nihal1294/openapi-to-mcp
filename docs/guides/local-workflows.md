# Local Workflows

This page is for source checkout, development, and manual build or test flows.

It is not the primary end-user installation path.

## Clone and install for development

```bash
git clone https://github.com/nihal1294/openapi-to-mcp.git
cd openapi-to-mcp
uv sync --dev
```

## Running CLI commands from a source checkout

Public docs assume an installed `openapi-to-mcp` binary.

From the repository root, either:

- prefix those commands with `uv run`, or
- use the `just` shortcuts documented below.

Example:

```bash
uv run openapi-to-mcp generate \
  --openapi-json ./openapi.yaml \
  --output-dir ./generated-server
```

## `just` shortcuts

```bash
just sync
just format
just lint
just test
just docs-build
just docs-serve
just e2e-generated
just e2e-cli
just generate
just build
just run
just list
just call getPetById '{"petId":1}'
just smoke
just clean
just clean-tmp
just clean-all
```

## `scripts/workflow.sh`

Get help:

```bash
scripts/workflow.sh help
```

Available commands:

- `sync`
- `generate`
- `build-generated`
- `run-generated`
- `test-list`
- `test-call <tool-name> [json-args]`
- `smoke`
- `clean`
- `clean-tmp`
- `clean-all`

## Workflow helper environment overrides

`scripts/workflow.sh` supports:

- `OPENAPI_JSON`
- `OUTPUT_DIR`
- `MCP_SERVER_NAME`
- `TRANSPORT`
- `HOST`
- `PORT`
- `MCP_ENDPOINT`
- `TARGET_API_BASE_URL`
- `UV_CACHE_DIR`

Example:

```bash
OUTPUT_DIR=/tmp/my-mcp \
TARGET_API_BASE_URL=https://petstore.swagger.io/v2 \
scripts/workflow.sh generate
```

## Recommended local verification order

```bash
just format
just lint
just test
just docs-build
just e2e-generated
just e2e-cli
```

## Hooks

Install hooks:

```bash
just hooks-install
```

Run them manually:

```bash
just hooks-run
just hooks-run-push
```

## CI and releases

Required checks on `master` currently include:

- `quality-py314`
- `e2e-generated-server (node-20)`
- `e2e-generated-server (node-22)`
- `e2e-cli-matrix`
- `dependency-review`

Relevant workflow files:

- `ci.yml`
- `security.yml`
- `docs.yml`
- `release.yml`
- `claude.yml`

Release behavior:

- releases are automated from `master`
- a release runs when the version changes or the matching version tag is missing
- the release workflow builds the wheel and sdist, ensures the version tag exists, and creates or updates the GitHub Release

Code scanning is expected through GitHub default CodeQL setup, not a workflow in the repo.
