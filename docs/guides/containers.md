# Container deployment reference

The [Docker Compose example](https://github.com/nihal1294/openapi-to-mcp/tree/master/examples/container)
builds a generated Streamable HTTP server and runs it alongside a synthetic API.
It tests the full path: CLI generation, TypeScript compilation, tool discovery,
API-key injection, and an MCP tool call across the Compose network.

## Run the example

Clone the repository, install Python 3.14+, uv, and Docker Compose v2, then follow
the example's README. Generated files go into the directory named by
`MCP_CONTAINER_DIR`; the generator's normal output remains unchanged.

The MCP endpoint is `http://127.0.0.1:8080/mcp`. The mock API is reachable only
inside Compose at `http://mock-api:8081`. Host loopback and container service
names are different network addresses: a generated server running in a container
cannot reach another container through its own `localhost`.

## Local health and readiness

HTTP servers reserve the fixed `/healthz` and `/readyz` paths, including their
case and trailing-slash equivalents. `GET /healthz` returns `200` with
`{"status":"ok"}` and `GET /readyz` returns `200` with `{"status":"ready"}`
once the local listener is ready. A listener marked not ready returns `503`
with `{"status":"not_ready"}`; before the listener binds, probes are unreachable.
Both responses set `Cache-Control: no-store`.

These probes require no MCP session, tool identity, upstream credentials, or
dependency availability. They use the same `MCP_ALLOWED_HOSTS` and
`MCP_ALLOWED_ORIGINS` checks as the MCP endpoint. `HEAD` follows the GET status
semantics; other methods return `405`. The probes stop succeeding when the
server shuts down. Readiness does not add a draining grace period or promise
upstream availability.

If an existing `MCP_HTTP_ENDPOINT` equals or matches either reserved route,
change it to a separate path such as `/mcp` and update clients before deploying
the regenerated server. Conflicting endpoint patterns fail at startup.

## Adapt the Dockerfile

Copy `Dockerfile` and `.dockerignore` into a generated project. The build stage
installs dependencies and compiles TypeScript. The runtime stage contains the
compiled application and production dependencies, and runs as the non-root
`node` user. An existing `package-lock.json` is honored with `npm ci`.

Provide `TARGET_API_BASE_URL` and the generated `AUTH_*` variables as runtime
environment values. The image does not copy `.env`, source configuration, or
build logs. The example's API key is synthetic and only protects its mock API.

For HTTP servers, set `MCP_HTTP_HOST=0.0.0.0` inside the container and configure
`MCP_ALLOWED_HOSTS` and `MCP_ALLOWED_ORIGINS` for the client-facing address.
The example publishes only to host loopback. Remote deployments also need their
own TLS and MCP-client authorization setup; upstream API credentials do not
authenticate incoming MCP clients.

For stdio servers, use `docker run --rm -i` with runtime environment variables
and no HTTP port. Avoid `-t`, which allocates a terminal to the protocol stream.

## Verification

Run `bash scripts/e2e_container.sh` from the repository root. It uses a unique
Compose project and temporary generated directory, verifies non-root execution
and `.env` exclusion, calls `getWidget`, and removes its containers and build
output. The `container` GitHub Actions workflow runs the same check on Linux.
