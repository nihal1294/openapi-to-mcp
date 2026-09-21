# Generated server in Docker Compose

Run the generator, build its TypeScript output in a multi-stage Node image, and
call an API on the Compose network. The example uses synthetic data and a local
API key. Only the MCP port is published, on `127.0.0.1`.

From the repository root, with Python 3.14+, uv, and Docker Compose v2 installed:

```bash
export MCP_CONTAINER_DIR="$(mktemp -d)"
uv run openapi-to-mcp generate \
  --openapi-json examples/container/openapi.yaml \
  --output-dir "$MCP_CONTAINER_DIR" --mcp-server-name container-example \
  --transport streamable-http
cp examples/container/Dockerfile examples/container/.dockerignore "$MCP_CONTAINER_DIR/"
docker compose -f examples/container/compose.yaml up --build --wait
uv run openapi-to-mcp test-server \
  --transport streamable-http --host 127.0.0.1 --port 8080 \
  --tool-name getWidget --tool-args '{"widgetId":"42"}'
docker compose -f examples/container/compose.yaml down
```

The tool returns `{"id":"42","source":"compose-mock"}`. Set
`MCP_CONTAINER_PORT` to use another local port and use that port in the test URL.
Set `EXAMPLE_API_KEY` to override the synthetic key shared by the mock and MCP
services. Docker receives it at runtime; `.env` files are excluded from builds.

Compose waits for `GET /readyz` before marking the generated server healthy. The
server also exposes `GET /healthz`; both return bounded JSON with
`Cache-Control: no-store`, need no MCP session or upstream API, and use the same
`MCP_ALLOWED_HOSTS` and `MCP_ALLOWED_ORIGINS` checks as the MCP endpoint.

The Dockerfile uses `npm ci` when the generated project has a `package-lock.json`.
Otherwise it uses `npm install` for the initial build. Keep a lockfile with a
deployed project to reproduce its dependency resolution.

Run `bash scripts/e2e_container.sh` for an isolated build/call/cleanup check.
For adaptation details, see the [container guide](../../docs/guides/containers.md).
