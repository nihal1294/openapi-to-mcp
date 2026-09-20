#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"
command -v docker >/dev/null
docker compose version
docker info >/dev/null

MCP_CONTAINER_DIR="$(mktemp -d "${RUNNER_TEMP:-${TMPDIR:-/tmp}}/mcp-container.XXXXXX")"
export MCP_CONTAINER_DIR
export MCP_CONTAINER_PORT=0
export EXAMPLE_API_KEY=container-test-key
COMPOSE_PROJECT="mcp-container-${RANDOM}-$$"

compose() {
  docker compose --project-name "$COMPOSE_PROJECT" -f examples/container/compose.yaml "$@"
}

cleanup() {
  local result=$?
  trap - EXIT
  if [[ "$result" != 0 ]]; then compose logs --no-color || true; fi
  compose down --volumes --rmi local >/dev/null 2>&1 || true
  rm -rf "$MCP_CONTAINER_DIR"
  exit "$result"
}
trap cleanup EXIT

uv run openapi-to-mcp generate \
  --openapi-json examples/container/openapi.yaml \
  --output-dir "$MCP_CONTAINER_DIR" --mcp-server-name container-example --transport streamable-http
cp examples/container/Dockerfile examples/container/.dockerignore "$MCP_CONTAINER_DIR/"
printf 'BUILD_CONTEXT_SENTINEL=must-not-be-copied\n' > "$MCP_CONTAINER_DIR/.env"
compose up --build --wait --wait-timeout 120
compose exec -T mcp node -e \
  "if (process.getuid() === 0 || require('node:fs').existsSync('/app/.env')) process.exit(1)"
PUBLISHED_ADDRESS="$(compose port mcp 8080)"
uv run python -m scripts.assert_container_server "http://${PUBLISHED_ADDRESS}/mcp"
