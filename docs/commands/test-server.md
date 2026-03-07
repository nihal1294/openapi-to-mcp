# `test-server`

Use `test-server` for quick MCP smoke checks against a running server.

## Command

```bash
openapi-to-mcp test-server [OPTIONS]
```

## Options

| Option | Required | Default | Meaning |
| --- | --- | --- | --- |
| `--transport` | Yes | None | `streamable-http` or `stdio` |
| `--host` | No | `localhost` | Hostname for `streamable-http` |
| `--port` | No | `8080` | Port for `streamable-http` |
| `--mcp-endpoint` | No | `/mcp` | HTTP MCP endpoint path |
| `--list-tools` | No | Off | Send a `tools/list` request |
| `--server-cmd` | No | None | Server startup command for `stdio` |
| `--tool-name` | No | None | Tool name for `tools/call` |
| `--tool-args` | No | None | JSON object string for tool arguments |
| `--env-source` | No | None | `stdio` env values as JSON or file path |

## Modes

### List tools

```bash
openapi-to-mcp test-server \
  --transport streamable-http \
  --host 127.0.0.1 \
  --port 8080 \
  --mcp-endpoint /mcp \
  --list-tools
```

### Call a tool over streamable HTTP

```bash
openapi-to-mcp test-server \
  --transport streamable-http \
  --host 127.0.0.1 \
  --port 8080 \
  --mcp-endpoint /mcp \
  --tool-name getPetById \
  --tool-args '{"petId":1}'
```

### List tools over stdio

```bash
openapi-to-mcp test-server \
  --transport stdio \
  --server-cmd "node ./generated-server/build/index.js" \
  --env-source ./generated-server/.env \
  --list-tools
```

### Call a tool over stdio with inline env JSON

```bash
openapi-to-mcp test-server \
  --transport stdio \
  --server-cmd "node ./generated-server/build/index.js" \
  --env-source '{"TARGET_API_BASE_URL":"https://example.com/api"}' \
  --tool-name getPetById \
  --tool-args '{"petId":1}'
```

## Validation rules

- `--server-cmd` is required for `stdio`
- `--mcp-endpoint` must start with `/`
- `--tool-args` requires `--tool-name`
- you must choose `--list-tools` or `--tool-name`

## Output behavior

`test-server` prints a formatted JSON panel with the raw response payload returned by the transport adapter.

For quick local smoke tests, this is intentionally low-friction rather than highly normalized.

## `--env-source` formats

Accepted values:

- a JSON string
- a path to a `.json` file
- a path to a `.env` file

## When to use MCP Inspector instead

Use `test-server` for automation or quick terminal checks.

Use the [MCP Inspector guide](../guides/mcp-inspector.md) when you want a GUI for exploring tools and sending requests interactively.
