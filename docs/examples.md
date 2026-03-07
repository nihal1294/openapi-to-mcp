# Examples

## Generate from a local spec

```bash
openapi-to-mcp generate \
  --openapi-json ./openapi.yaml \
  --output-dir ./generated-server
```

## Generate a stdio server

```bash
openapi-to-mcp generate \
  --openapi-json ./openapi.yaml \
  --output-dir ./generated-stdio \
  --transport stdio
```

## Generate non-strict output for debugging

```bash
openapi-to-mcp generate \
  --openapi-json ./openapi.yaml \
  --output-dir ./generated-loose \
  --no-strict
```

## Run directly from a remote spec

```bash
openapi-to-mcp run \
  --openapi-json https://petstore.swagger.io/v2/swagger.json \
  --target-api-base-url https://petstore.swagger.io/v2
```

## Run with inline environment JSON

```bash
openapi-to-mcp run \
  --openapi-json ./openapi.yaml \
  --env-source '{"TARGET_API_BASE_URL":"https://example.com/api"}'
```

## Test a running streamable HTTP server

```bash
openapi-to-mcp test-server \
  --transport streamable-http \
  --host 127.0.0.1 \
  --port 8080 \
  --mcp-endpoint /mcp \
  --list-tools
```

## Test a running stdio server

```bash
openapi-to-mcp test-server \
  --transport stdio \
  --server-cmd "node ./generated-server/build/index.js" \
  --env-source ./generated-server/.env \
  --tool-name getPetById \
  --tool-args '{"petId":1}'
```

## More examples

- For a longer walkthrough, see [Extended Examples](USAGE_EXAMPLES.md).
- For source checkout, `just`, helper scripts, and validation shortcuts, see [Local Workflows](guides/local-workflows.md).
