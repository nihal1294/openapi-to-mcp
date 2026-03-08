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
| `--target-api-base-url` | No | None | Override `TARGET_API_BASE_URL` explicitly |
| `--env-source` | No | None | Runtime env values as JSON string or path to `.json` or `.env` |

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

### Keep going on mapping failures while staying strict elsewhere

```bash
openapi-to-mcp run \
  --openapi-json ./openapi.yaml \
  --on-mapping-error skip \
  --target-api-base-url https://example.com/api
```

## `--env-source` formats

Accepted values:

- a JSON string
- a path to a `.json` file
- a path to a `.env` file

`run` copies `.env.example` to `.env` when needed, writes overrides, and then starts the generated server with resolved runtime values.

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
- missing local runtime tools such as `node` or `npm`
- `npm install` or `npm run build` failure in the generated project
- invalid `--env-source` value or unreadable env file
