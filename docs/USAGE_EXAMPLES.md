# Usage Examples

Practical examples for the current `openapi-to-mcp` CLI surface:

- `generate`: create a TypeScript MCP server project from an OpenAPI spec
- `run`: generate, build, and run a server directly from a spec
- `test-server`: send basic MCP requests to a running server

## 1. Example OpenAPI Input

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

## 2. Generate a Server Project

Generate a reusable MCP server project in a directory:

```bash
uv run openapi-to-mcp generate \
  --openapi-json ./pet-api.yaml \
  --output-dir ./generated-pet-mcp \
  --mcp-server-name pet-mcp-server \
  --transport streamable-http \
  --host 127.0.0.1 \
  --port 8080 \
  --mcp-endpoint /mcp
```

This loads the spec, maps operations to MCP tools, and emits a runnable TypeScript MCP server project plus `.env.example` and `generation_report.json`.

Expected output structure:

```bash
generated-pet-mcp/
├── README.md
├── package.json
├── tsconfig.json
├── .env.example
├── generation_report.json
└── src/
    ├── index.ts
    ├── server.ts
    └── transport.ts
```

## 3. Build and Run a Generated Project Manually

After generation:

```bash
cd generated-pet-mcp
cp .env.example .env
```

Set `TARGET_API_BASE_URL` in `.env`, then:

```bash
npm install
npm run build
npm start
```

For specs with security schemes, also fill generated auth variables such as:

- `AUTH_<SCHEME_NAME>_API_KEY`
- `AUTH_<SCHEME_NAME>_TOKEN`

## 4. Run Directly from a Spec

If you do not need to keep the generated project, use `run`:

```bash
uv run openapi-to-mcp run \
  --openapi-json https://petstore.swagger.io/v2/swagger.json \
  --target-api-base-url https://petstore.swagger.io/v2
```

This command:

1. Generates a temporary project.
2. Installs Node dependencies.
3. Builds the generated TypeScript server.
4. Starts the MCP server.

Use `--output-dir` if you want to keep the generated project instead of using a temp directory:

```bash
uv run openapi-to-mcp run \
  --openapi-json ./pet-api.yaml \
  --output-dir ./generated-runtime \
  --target-api-base-url https://example.com/api
```

## 5. Test a Running Server

### Streamable HTTP: list tools

```bash
uv run openapi-to-mcp test-server \
  --transport streamable-http \
  --host 127.0.0.1 \
  --port 8080 \
  --mcp-endpoint /mcp \
  --list-tools
```

### Streamable HTTP: call a tool

```bash
uv run openapi-to-mcp test-server \
  --transport streamable-http \
  --host 127.0.0.1 \
  --port 8080 \
  --mcp-endpoint /mcp \
  --tool-name findPetsByStatus \
  --tool-args '{"status":"available"}'
```

### STDIO: list tools

```bash
uv run openapi-to-mcp test-server \
  --transport stdio \
  --server-cmd "node ./generated-pet-mcp/build/index.js" \
  --env-source ./generated-pet-mcp/.env \
  --list-tools
```

### STDIO: call a tool

```bash
uv run openapi-to-mcp test-server \
  --transport stdio \
  --server-cmd "node ./generated-pet-mcp/build/index.js" \
  --env-source ./generated-pet-mcp/.env \
  --tool-name getPetById \
  --tool-args '{"petId":1}'
```

## 6. Local Validation Shortcuts

Useful local commands:

```bash
just format
just lint
just test
just e2e-generated
just e2e-cli
```

Use `just e2e-generated` for generated-server validation and `just e2e-cli` for a CLI-level matrix over `generate`, `run`, and `test-server`.
