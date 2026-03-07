# Getting Started

## Step 1: install the CLI

Follow [Installation](installation.md) first.

After installation, confirm the command is available:

```bash
openapi-to-mcp --help
```

## Step 2: choose the command you need

Use `generate` when you want a reusable generated project on disk.

```bash
openapi-to-mcp generate \
  --openapi-json ./openapi.yaml \
  --output-dir ./generated-server
```

Use `run` when you want one command to generate, build, and start a server locally.

```bash
openapi-to-mcp run \
  --openapi-json https://petstore.swagger.io/v2/swagger.json \
  --target-api-base-url https://petstore.swagger.io/v2
```

Use `test-server` when you want to smoke-test a running server.

```bash
openapi-to-mcp test-server \
  --transport streamable-http \
  --host 127.0.0.1 \
  --port 8080 \
  --mcp-endpoint /mcp \
  --list-tools
```

## Step 3: know when Node.js is required

- `generate`: does not need Node.js
- `run`: needs `node` and `npm`
- generated projects themselves need Node.js to build and run

## Step 4: go deeper

- [generate](commands/generate.md)
- [run](commands/run.md)
- [test-server](commands/test-server.md)
- [Auth and Environment](guides/auth-and-env.md)
- [Examples](examples.md)

## Development and source workflows

Source checkout, `uv sync`, `just`, hooks, and helper scripts are intentionally documented separately in [Local Workflows](guides/local-workflows.md).
