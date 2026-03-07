# Usage Examples

Practical examples for the current `openapi-to-mcp` command surface.

## 1. Example OpenAPI input

### YAML

**`pet-api.yaml`**

```yaml
openapi: 3.0.3
info:
  title: Simple Pet API
  version: 1.0.0
paths:
  /pet/{petId}:
    get:
      summary: Get a pet by ID
      operationId: getPetById
      parameters:
        - name: petId
          in: path
          required: true
          schema:
            type: integer
      responses:
        "200":
          description: A pet object.
```

## 2. Generate a reusable server project

```bash
openapi-to-mcp generate \
  --openapi-json ./pet-api.yaml \
  --output-dir ./generated-pet-mcp \
  --mcp-server-name pet-mcp-server \
  --transport streamable-http \
  --host 127.0.0.1 \
  --port 8080 \
  --mcp-endpoint /mcp
```

Expected output:

```text
generated-pet-mcp/
  README.md
  package.json
  tsconfig.json
  .env.example
  generation_report.json
  src/
```

## 3. Build and run a generated project manually

```bash
cd generated-pet-mcp
cp .env.example .env
npm install
npm run build
npm start
```

For secured specs, also fill generated auth variables such as:

- `AUTH_<SCHEME_NAME>_API_KEY`
- `AUTH_<SCHEME_NAME>_TOKEN`

## 4. Run directly from a spec

```bash
openapi-to-mcp run \
  --openapi-json https://petstore.swagger.io/v2/swagger.json \
  --target-api-base-url https://petstore.swagger.io/v2
```

To keep the generated project:

```bash
openapi-to-mcp run \
  --openapi-json ./pet-api.yaml \
  --output-dir ./generated-runtime \
  --target-api-base-url https://example.com/api
```

## 5. Use `--env-source`

Inline JSON:

```bash
openapi-to-mcp run \
  --openapi-json ./pet-api.yaml \
  --env-source '{"TARGET_API_BASE_URL":"https://example.com/api"}'
```

`.env` file:

```bash
openapi-to-mcp test-server \
  --transport stdio \
  --server-cmd "node ./generated-pet-mcp/build/index.js" \
  --env-source ./generated-pet-mcp/.env \
  --list-tools
```

## 6. Test a running server

### Streamable HTTP: list tools

```bash
openapi-to-mcp test-server \
  --transport streamable-http \
  --host 127.0.0.1 \
  --port 8080 \
  --mcp-endpoint /mcp \
  --list-tools
```

### Streamable HTTP: call a tool

```bash
openapi-to-mcp test-server \
  --transport streamable-http \
  --host 127.0.0.1 \
  --port 8080 \
  --mcp-endpoint /mcp \
  --tool-name findPetsByStatus \
  --tool-args '{"status":"available"}'
```

### STDIO: call a tool

```bash
openapi-to-mcp test-server \
  --transport stdio \
  --server-cmd "node ./generated-pet-mcp/build/index.js" \
  --env-source ./generated-pet-mcp/.env \
  --tool-name getPetById \
  --tool-args '{"petId":1}'
```

## 7. Non-strict generation

```bash
openapi-to-mcp generate \
  --openapi-json ./pet-api.yaml \
  --output-dir ./generated-loose \
  --no-strict
```

Use this when you want warnings and a `generation_report.json` summary instead of strict failure.

## 8. Development and repo-local workflows

For source checkout, `uv sync`, `just`, helper scripts, and local validation shortcuts, see [Local Workflows](guides/local-workflows.md).
