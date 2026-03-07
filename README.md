<p align="center">
  <img src="docs/images/openapi-to-mcp.png" alt="OpenAPI to MCP logo" width="200"/>
</p>

<h1 align="center">OpenAPI → MCP Server</h1>

Generate, run, and test Node.js/TypeScript [MCP (Model Context Protocol)](https://modelcontextprotocol.io/) servers directly from [OpenAPI](https://www.openapis.org/) specifications.

This Python CLI accepts OpenAPI v3 specs from local files or URLs, maps each operation to an MCP tool, generates a runnable TypeScript server, and can also validate or start that server for local development.

The generated server acts as an API proxy: it receives MCP tool calls and translates them into HTTP requests against the target API defined by the OpenAPI specification.

## ✨ Features

* Parses OpenAPI v3 JSON or YAML from local files or URLs.
* Validates the OpenAPI specification structure.
* Maps OpenAPI operations (GET, POST, PUT, DELETE, PATCH) to MCP tools.
* Generates MCP tool `inputSchema` (JSON Schema) based on OpenAPI parameters and request bodies (handles basic types, objects, arrays, enums, formats, simple local `$ref`s, basic cycle detection).
* Generates a runnable Node.js/TypeScript MCP server project:
  * Uses `@modelcontextprotocol/sdk`.
  * Configurable transport (`stdio`, `streamable-http`).
  * Streamable HTTP endpoint configuration (`host`, `port`, `mcp-endpoint`).
  * Strict mode by default with `generation_report.json` output.
  * Reads target API base URL and generated auth credentials from a `.env` file.
  * Supports OpenAPI parameter styles (including `cookie`) and security scheme env mapping for `apiKey`, bearer, OAuth2, and OpenID Connect schemes.
  * Includes runtime execution controls (global/per-tool concurrency, queueing, timeout).
  * Includes basic error mapping from HTTP status codes to MCP error codes.
  * Includes `package.json`, `tsconfig.json` (with strict settings), and **an** example `.env` file.
  * Provides clear setup and run instructions in a generated `README.md`.
* Integrated linting and formatting (`ruff`).
* Unit and integration tests (`pytest`).
* Generated-server E2E coverage for `stdio` and `streamable-http`, including auth flows against a local mock API.
* Rich CLI help and command output via `rich-click` and `rich`.
* Structured console and JSON logging via `structlog`.
* Local Git hook support.

## Quickstart

1. Install dependencies:

```bash
uv sync
```

(Use `uv sync --dev` for development dependencies.)

1. Generate a server from your OpenAPI spec:

```bash
uv run openapi-to-mcp generate 
  --openapi-json <path_or_url> 
  --output-dir ./mcp-server
```

1. Follow the instructions in the generated `README.md` in `./mcp-server` to build and run the server.

1. Validate the generated-server path locally:

```bash
just e2e-generated
```

1. Or run a generated server directly from a spec in one command:

```bash
uv run openapi-to-mcp run \
  --openapi-json <path_or_url> \
  --target-api-base-url <api_base_url>
```

See [docs/USAGE_EXAMPLES.md](docs/USAGE_EXAMPLES.md) for detailed examples.

## ⚡ Fast Workflow Script

Use the bundled Bash helper to run the common flow quickly:

```bash
scripts/workflow.sh help
```

Common commands:

```bash
# Install Python deps (dev included)
scripts/workflow.sh sync

# Generate + .env setup (defaults to /tmp/mcp-smoke + Swagger Petstore v2)
scripts/workflow.sh generate

# Install Node deps + build generated server
scripts/workflow.sh build-generated

# Run generated server
scripts/workflow.sh run-generated

# List tools from running server
scripts/workflow.sh test-list

# Call a tool from running server
scripts/workflow.sh test-call getPetById '{"petId":1}'

# Full quick path (sync + generate + build)
scripts/workflow.sh smoke

# Clean caches/temp artifacts in this repo
scripts/workflow.sh clean

# clean + remove generated temp outputs (e.g. /tmp/mcp-smoke*)
scripts/workflow.sh clean-all
```

You can override defaults with env vars, for example:

```bash
OUTPUT_DIR=/tmp/my-mcp TARGET_API_BASE_URL=https://petstore.swagger.io/v2 scripts/workflow.sh generate
```

If you use [`just`](https://github.com/casey/just), equivalent short commands are available:

```bash
just sync
just hooks-install
just hooks-run
just hooks-run-push
just format
just lint
just test
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

For a full local validation of generated servers over both `stdio` and `streamable-http`
against a local mock target API, run:

```bash
scripts/e2e_generated_server.sh
```

Or, if you use `just`:

```bash
just e2e-generated
```

The generated-server E2E runner chooses free local ports automatically by default.
If you want to force specific ports, set `MOCK_API_PORT` and/or `HTTP_PORT`.

The E2E suite covers:

* basic tool listing and tool calls for both transports
* generated auth wiring for `apiKey` in `header`, `query`, and `cookie`
* generated bearer token wiring
* missing-credential failure for bearer auth

For a CLI-level E2E matrix that exercises `generate`, `run`, and `test-server`
across the main supported combinations, run:

```bash
scripts/e2e_cli_matrix.sh
```

Or:

```bash
just e2e-cli
```

If you want to remove generated validation artifacts under `/tmp`, run:

```bash
scripts/workflow.sh clean-tmp
```

Or:

```bash
just clean-tmp
```

## 🚀 Installation / Setup

**Prerequisites:**

* **Python:** Version 3.14 or higher is required (assumed to be installed).
* **uv:** Used for environment and dependency management.
* **Node.js:** Version 20 or higher is required for the generated server (assumed to be installed).

**Steps:**

1. **Navigate to Project Directory:**
    Open your terminal in the directory containing this `openapi-to-mcp` code.

2. **Install Dependencies:**
    * **For running the tool:**

        ```bash
        uv sync
        ```

        This installs only the core dependencies needed to run the generator.
    * **For development (including running tests, linting, formatting):**

        ```bash
        uv sync --dev
        ```

        This installs all dependencies, including development tools like `pytest` and `ruff`.

3. **Activate Virtual Environment (Optional but Recommended):**
    `uv` creates a `.venv` virtual environment. You can activate it to run commands directly:

    ```bash
    source .venv/bin/activate
    ```

    Alternatively, you can prefix commands with `uv run`.

## 📋 Usage

The tool provides three main commands: `generate`, `run`, and `test-server`.

Run commands from within the project directory (or with the virtual environment activated):

```bash
# Using uv run
uv run openapi-to-mcp [COMMAND] [OPTIONS]

# Or, if inside the activated virtual environment
openapi-to-mcp [COMMAND] [OPTIONS]
```

### 🛠️ `generate` Command

This command generates the MCP server code.

**Options:**

* `--openapi-json`, `-o` (**Required**): Path or URL to the OpenAPI specification file (JSON or YAML).
* `--output-dir`, `-d` (**Required**): Output directory for the generated MCP server files.
* `--mcp-server-name`, `-n`: Name for the generated MCP server package. (Default: spec `info.title` or fallback)
* `--mcp-server-version`, `-v`: Version for the generated MCP server package. (Default: spec `info.version` or fallback)
* `--transport`, `-t`: Transport mechanism for the generated server (`stdio` or `streamable-http`). (Default: `streamable-http`)
* `--host`: Host for `streamable-http`. (Default: `127.0.0.1`)
* `--port`, `-p`: Port for `streamable-http`. (Default: `8080`)
* `--mcp-endpoint`: Endpoint path for `streamable-http`. (Default: `/mcp`)
* `--strict / --no-strict`: Fail on mapping issues (strict default on).
* `--help`: Show help for the `generate` command.

**Example:**

For STDIO transport, you can run the following command to generate a server for the Swagger Petstore API example:

```bash
uv run openapi-to-mcp generate \
  --openapi-json https://petstore3.swagger.io/api/v3/openapi.json \
  --output-dir ./generated-petstore-mcp \
  --mcp-server-name petstore-mcp \
  --transport stdio
```

This command will:

1. Fetch and validate `https://petstore3.swagger.io/api/v3/openapi.json`.
2. Map the API operations to MCP tools.
3. Generate the Node.js/TypeScript MCP server code in the `./generated-petstore-mcp` directory.
4. Configure the generated server to use STDIO transport.

For streamable HTTP transport, you can run the following command to generate a server for the Swagger Petstore API example:

```bash
uv run openapi-to-mcp generate \
  --openapi-json https://petstore3.swagger.io/api/v3/openapi.json \
  --output-dir ./generated-petstore-mcp \
  --mcp-server-name petstore-mcp \
  --transport streamable-http \
  --host 127.0.0.1 \
  --port 8080 \
  --mcp-endpoint /mcp
```

This command will:

1. Fetch and validate `https://petstore3.swagger.io/api/v3/openapi.json`.
2. Map the API operations to MCP tools.
3. Generate the Node.js/TypeScript MCP server code in the `./generated-petstore-mcp` directory.
4. Configure the generated server to use streamable HTTP transport on `127.0.0.1:8080/mcp`.

#### Post-Generation Steps

After running the `generate` command, follow these steps in the generated server directory (`<output-dir>` specified during generation):

1. Navigate to the output directory:

    ```bash
    cd <output-dir> 
    ```

2. Create/edit the `.env` file (the generator creates an `.env.example` file you can copy) and provide the required values:
    * `TARGET_API_BASE_URL`: The base URL of the target API the generated server will interact with. The generated server validates this value on startup and will not run with placeholder URLs.
    * Scheme-specific auth env vars generated from the OpenAPI spec, for example:
      * `AUTH_<SCHEME_NAME>_API_KEY` for `apiKey` schemes
      * `AUTH_<SCHEME_NAME>_TOKEN` for bearer, OAuth2, or OpenID Connect schemes
    * `TARGET_API_AUTH_HEADER`: (Optional) A full authorization header string for APIs that need a raw fallback header instead of generated scheme-specific env vars.
3. Install dependencies:

    ```bash
    npm install
    ```

4. Build the TypeScript code:

    ```bash
    npm run build
    ```

5. Start the server:

    ```bash
    npm start
    ```

The generated server's own `README.md` file also contains these setup instructions. You can then test the running server using the [test-server](#test-server-command) command or the [MCP Inspector](#testing-with-mcp-inspector).

### `run` Command

This command performs the full local flow in one step:

1. generate a server from the OpenAPI spec
2. install Node dependencies
3. build the generated TypeScript project
4. start the generated MCP server

By default it uses a temporary output directory and cleans it up when the server exits. If you want to keep or reuse the generated project, pass `--output-dir`.

**Common options:**

* `--openapi-json`, `-o` (**Required**): Path or URL to the OpenAPI specification file.
* `--target-api-base-url`: Override `TARGET_API_BASE_URL` for the generated runtime. Required when the spec does not define `servers[0].url`.
* `--env-source`: Additional runtime env vars as a JSON string or path to a JSON/.env file.
* `--output-dir`, `-d`: Optional directory to reuse instead of a temporary workspace.
* `--transport`, `--host`, `--port`, `--mcp-endpoint`, `--strict`: Same meaning as in `generate`.

**Examples:**

```bash
uv run openapi-to-mcp run \
  --openapi-json https://petstore.swagger.io/v2/swagger.json \
  --target-api-base-url https://petstore.swagger.io/v2
```

```bash
uv run openapi-to-mcp run \
  --openapi-json ./openapi.yaml \
  --output-dir ./generated-runtime \
  --env-source ./runtime.env
```

### `test-server` Command

This command allows you to send basic JSON-RPC requests (`ListTools`, `CallTool`) to a running MCP server (generated by this tool or any other).

**Options:**

* `--transport {streamable-http,stdio}`: (Required) Specify the transport the server is using.
* `--host <hostname>`: Hostname for `streamable-http` (default: `localhost`).
* `--port <port_number>`: Port for `streamable-http` (default: `8080`).
* `--mcp-endpoint <path>`: Endpoint path for `streamable-http` (default: `/mcp`).
* `--server-cmd "<command>"`: (Required for stdio) The command to start the server (e.g., `"node ./generated-server/build/index.js"`). Ensure the path is correct relative to where you run the command.
* `--list-tools`: Send a `ListTools` request.
* `--tool-name <tool_name>`: Specify a tool name for a `CallTool` request.
* `--tool-args '<json_string>'`: (Requires `--tool-name`) Provide arguments for the tool as a JSON string (e.g., `'{"petId": 123}'`).
* `--env-source <source>`: (Optional, for stdio only) Provide environment variables to the server process. `<source>` can be:
  * A direct JSON string: `'{"VAR1":"value1", "VAR2":"value2"}'`
  * A path to a JSON file: `./my_env.json`
  * A path to a `.env` file: `./generated-server/.env`
* `--help`: Show help for the `test-server` command.

**Examples:**

* **List tools via streamable HTTP (server running on `127.0.0.1:8080/mcp`):**

    ```bash
    uv run openapi-to-mcp test-server --transport streamable-http --host 127.0.0.1 --port 8080 --mcp-endpoint /mcp --list-tools
    ```

* **Call a tool via streamable HTTP:**

    ```bash
    uv run openapi-to-mcp test-server --transport streamable-http --host 127.0.0.1 --port 8080 --mcp-endpoint /mcp \
      --tool-name getPetById --tool-args '{"petId": 1}'
    ```

* **List tools via stdio (using .env file):**

    ```bash
    # Ensure TARGET_API_BASE_URL is set in ./generated-petstore-mcp/.env
    uv run openapi-to-mcp test-server --transport stdio \
      --server-cmd "node ./generated-petstore-mcp/build/index.js" --list-tools \
      --env-source ./generated-petstore-mcp/.env
    ```

* **Call a tool via stdio (using JSON string for env):**

    ```bash
    uv run openapi-to-mcp test-server --transport stdio \
      --server-cmd "node ./generated-petstore-mcp/build/index.js" \
      --tool-name addPet --tool-args '{"requestBody": {"name": "doggie", "photoUrls": []}}' \
      --env-source '{"TARGET_API_BASE_URL": "https://petstore3.swagger.io/api/v3"}'
    ```

## Usage Examples

For detailed, step-by-step usage examples—including sample OpenAPI v3 input specs, CLI commands, generated output structure, and before/after code samples—see [docs/USAGE_EXAMPLES.md](docs/USAGE_EXAMPLES.md).

A summary is provided below:

### Example OpenAPI v3 Input (JSON)

```json
{
  "openapi": "3.0.3",
  "info": { "title": "Simple Pet API", "version": "1.0.0" },
  "paths": {
    "/pet/{petId}": {
      "get": {
        "operationId": "getPetById",
        "parameters": [
          { "name": "petId", "in": "path", "required": true, "schema": { "type": "integer" } }
        ],
        "responses": { "200": { "description": "A pet object." } }
      }
    }
  }
}
```

### Example OpenAPI v3 Input (YAML)

```yaml
openapi: 3.0.3
info:
  title: Simple Pet API
  version: 1.0.0
paths:
  /pet/{petId}:
    get:
      operationId: getPetById
      parameters:
        - name: petId
          in: path
          required: true
          schema:
            type: integer
      responses:
        '200':
          description: A pet object.
```

### Generate an MCP Server

```bash
uv run openapi-to-mcp generate \
  --openapi-json pet-api.json \
  --output-dir ./generated-pet-mcp \
  --mcp-server-name pet-mcp-server \
  --transport stdio
```

### Output Structure

```bash
generated-pet-mcp/
├── README.md
├── package.json
├── tsconfig.json
├── .env.example
├── src/
│   ├── index.ts
│   ├── server.ts
│   └── ...
```

### Before/After Example

**Before (OpenAPI YAML):**

```yaml
paths:
  /pet/{petId}:
    get:
      operationId: getPetById
      parameters:
        - name: petId
          in: path
          required: true
          schema:
            type: integer
```

**After (Generated TypeScript):**

```typescript
{
  name: 'getPetById',
  inputSchema: {
    type: 'object',
    properties: { petId: { type: 'integer' } },
    required: ['petId']
  },
  // ...handler code...
}
```

See the [full usage guide](docs/USAGE_EXAMPLES.md) for more details and explanations.

## Testing with MCP Inspector

Besides the `test-server` command, the [MCP Inspector](https://modelcontextprotocol.io/docs/tools/inspector) provides a graphical interface for interacting with any running MCP server.

1. Follow the installation instructions on the MCP Inspector documentation page.
2. Launch the Inspector.
3. Configure a new connection:
    * Select the appropriate transport (`stdio` or `streamable-http`).
    * For `stdio`, provide the full command to start your generated server (e.g., `node /path/to/your/generated-server/build/index.js`).
    * For `streamable-http`, provide the URL including endpoint path (e.g., `http://127.0.0.1:8080/mcp`).
4. Connect to the server.
5. Use the Inspector UI to view available tools (`ListTools`) and send `CallTool` requests with arguments.

This offers a more interactive way to explore and test the generated server.

## 🤝 Contributing

Interested in contributing? We welcome contributions of all kinds to `openapi-to-mcp`! Whether you’re fixing bugs, adding features, improving documentation, or sharing ideas, your input is valuable to help us improve the project.

Please refer to our [CONTRIBUTING.md](CONTRIBUTING.md) for detailed guidelines on how to get started.

## 💻 Development Workflow

Ensure you have installed dependencies using `uv sync --dev`.

Recommended local verification order:

```bash
just format
just lint
just test
just e2e-generated
just e2e-cli
```

* **Git hooks:** Install the local `pre-commit` and `pre-push` hooks:

    ```bash
    uv run pre-commit install --hook-type pre-commit --hook-type pre-push
    ```

    Or:

    ```bash
    just hooks-install
    ```

    Behavior:
    `pre-commit` runs fast local checks (`ruff format`, `ruff check --fix`).
    `pre-push` runs the Python test suite.
    Generated-server E2E is available locally via `just e2e-generated` and runs in CI.

* **Formatting:** Apply code formatting using Ruff:

    ```bash
    uv run ruff format .
    ```

* **Linting:** Check for code style issues and apply automatic fixes using Ruff:

    ```bash
    uv run ruff check --fix .
    ```

* **Testing:** Run unit and integration tests using Pytest with coverage reporting:

    ```bash
    uv run pytest --cov=openapi_to_mcp
    ```

    Coverage reports (terminal and HTML) will be generated (check `htmlcov/` directory for HTML report).
* **All Checks:** Run formatting, linting, and tests sequentially:

    ```bash
    uv run ruff format .
    uv run ruff check --fix .
    uv run pytest --cov=openapi_to_mcp
    ```

* **Run hooks manually:** Validate the configured hook stages without committing or pushing:

    ```bash
    just hooks-run
    just hooks-run-push
    ```

* **When dependency constraints change:** refresh the lockfile:

    ```bash
    uv lock
    ```

* **Clean Temporary Files:** Remove temporary files and directories created during the build process:

    ```bash
    find . -name __pycache__ -type d -exec rm -rf {} + && rm -rf .pytest_cache .ruff_cache .coverage dist output mcp-server
    ```

## 📄 License

This project is licensed under the Apache License 2.0. See the [LICENSE](LICENSE) file for details.
See [CHANGELOG.md](CHANGELOG.md) for release notes.

## 📚 References

* [OpenAPI](https://www.openapis.org/)
* [Model Context Protocol (MCP)](https://modelcontextprotocol.io/)
* [Python](https://www.python.org/)
* [uv](https://docs.astral.sh/uv/)
* [Click](https://click.palletsprojects.com/)
* [Jinja2](https://jinja.palletsprojects.com/)
* [ruff](https://beta.ruff.rs/)
* [pytest](https://docs.pytest.org/)
* [TypeScript](https://www.typescriptlang.org/)
* [Node.js](https://nodejs.org/)
