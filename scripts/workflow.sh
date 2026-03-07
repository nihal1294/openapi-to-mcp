#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

OPENAPI_JSON="${OPENAPI_JSON:-https://petstore.swagger.io/v2/swagger.json}"
OUTPUT_DIR="${OUTPUT_DIR:-/tmp/mcp-smoke}"
MCP_SERVER_NAME="${MCP_SERVER_NAME:-petstore-mcp}"
TRANSPORT="${TRANSPORT:-streamable-http}"
HOST="${HOST:-127.0.0.1}"
PORT="${PORT:-8091}"
MCP_ENDPOINT="${MCP_ENDPOINT:-/mcp}"
TARGET_API_BASE_URL="${TARGET_API_BASE_URL:-https://petstore.swagger.io/v2}"

usage() {
  cat <<'EOF'
Usage: scripts/workflow.sh <command> [args]

Commands:
  sync
    Install Python dependencies (dev included).

  generate
    Generate MCP server in OUTPUT_DIR and create/update .env.

  build-generated
    Install npm deps and build generated server in OUTPUT_DIR.

  run-generated
    Start generated server from OUTPUT_DIR.

  test-list
    Call tools/list against running streamable-http MCP server.

  test-call <tool-name> [json-args]
    Call tools/call against running streamable-http MCP server.
    Example:
      scripts/workflow.sh test-call getPetById '{"petId":1}'

  smoke
    Run sync + generate + build-generated.

  clean
    Remove repo cache/temp artifacts.

  clean-tmp
    Remove generated temp MCP server outputs under /tmp.

  clean-all
    clean + clean-tmp.

Environment overrides:
  OPENAPI_JSON, OUTPUT_DIR, MCP_SERVER_NAME, TRANSPORT, HOST, PORT, MCP_ENDPOINT,
  TARGET_API_BASE_URL, UV_CACHE_DIR
EOF
}

ensure_command() {
  local cmd="$1"
  if ! command -v "$cmd" >/dev/null 2>&1; then
    echo "Missing required command: $cmd" >&2
    exit 1
  fi
}

run_uv() {
  if [[ -n "${UV_CACHE_DIR:-}" ]]; then
    env UV_CACHE_DIR="$UV_CACHE_DIR" uv "$@"
  else
    uv "$@"
  fi
}

replace_or_append_env_var() {
  local file="$1"
  local key="$2"
  local value="$3"
  local tmp_file
  tmp_file="$(mktemp)"

  if [[ -f "$file" ]]; then
    awk -v key="$key" -v value="$value" '
      BEGIN { replaced = 0 }
      {
        if ($0 ~ ("^" key "=")) {
          print key "=" value
          replaced = 1
        } else {
          print $0
        }
      }
      END {
        if (replaced == 0) {
          print key "=" value
        }
      }
    ' "$file" >"$tmp_file"
  else
    printf '%s=%s\n' "$key" "$value" >"$tmp_file"
  fi

  mv "$tmp_file" "$file"
}

is_tmp_path() {
  local path="$1"
  case "$path" in
    /tmp|/tmp/*|/private/tmp|/private/tmp/*)
      return 0
      ;;
    *)
      return 1
      ;;
  esac
}

do_sync() {
  ensure_command uv
  (cd "$REPO_ROOT" && run_uv sync --dev)
}

do_generate() {
  ensure_command uv
  mkdir -p "$OUTPUT_DIR"
  (cd "$REPO_ROOT" && run_uv run openapi-to-mcp generate \
    --openapi-json "$OPENAPI_JSON" \
    --output-dir "$OUTPUT_DIR" \
    --mcp-server-name "$MCP_SERVER_NAME" \
    --transport "$TRANSPORT" \
    --host "$HOST" \
    --port "$PORT" \
    --mcp-endpoint "$MCP_ENDPOINT")

  if [[ -f "${OUTPUT_DIR}/.env.example" && ! -f "${OUTPUT_DIR}/.env" ]]; then
    cp "${OUTPUT_DIR}/.env.example" "${OUTPUT_DIR}/.env"
  fi

  replace_or_append_env_var "${OUTPUT_DIR}/.env" "TARGET_API_BASE_URL" "$TARGET_API_BASE_URL"
}

do_build_generated() {
  ensure_command npm
  (cd "$OUTPUT_DIR" && npm install && npm run build)
}

do_run_generated() {
  ensure_command npm
  (cd "$OUTPUT_DIR" && npm start)
}

do_test_list() {
  ensure_command uv
  (cd "$REPO_ROOT" && run_uv run openapi-to-mcp test-server \
    --transport streamable-http \
    --host "$HOST" \
    --port "$PORT" \
    --mcp-endpoint "$MCP_ENDPOINT" \
    --list-tools)
}

do_test_call() {
  ensure_command uv
  local tool_name="${1:-}"
  local tool_args="${2:-{}}"
  if [[ -z "$tool_name" ]]; then
    echo "Usage: scripts/workflow.sh test-call <tool-name> [json-args]" >&2
    exit 1
  fi

  (cd "$REPO_ROOT" && run_uv run openapi-to-mcp test-server \
    --transport streamable-http \
    --host "$HOST" \
    --port "$PORT" \
    --mcp-endpoint "$MCP_ENDPOINT" \
    --tool-name "$tool_name" \
    --tool-args "$tool_args")
}

do_clean() {
  rm -rf \
    "${REPO_ROOT}/.mypy_cache" \
    "${REPO_ROOT}/.pre-commit-cache" \
    "${REPO_ROOT}/.pytest_cache" \
    "${REPO_ROOT}/.ruff_cache" \
    "${REPO_ROOT}/.uv-cache" \
    "${REPO_ROOT}/dist" \
    "${REPO_ROOT}/build" \
    "${REPO_ROOT}/site" \
    "${REPO_ROOT}/htmlcov"
  rm -f "${REPO_ROOT}/.coverage" "${REPO_ROOT}/coverage.xml"
  find "${REPO_ROOT}" -type d -name "__pycache__" -prune -exec rm -rf {} +
  find "${REPO_ROOT}" -type f -name "*.pyc" -delete
}

do_clean_all() {
  do_clean
  do_clean_tmp
}

do_clean_tmp() {
  if is_tmp_path "$OUTPUT_DIR"; then
    rm -rf "$OUTPUT_DIR"
  fi

  rm -rf \
    /tmp/mcp-smoke \
    /tmp/mcp-smoke-* \
    /tmp/openapi-to-mcp-e2e \
    /tmp/openapi-to-mcp-e2e-* \
    /private/tmp/mcp-smoke \
    /private/tmp/mcp-smoke-* \
    /private/tmp/openapi-to-mcp-e2e \
    /private/tmp/openapi-to-mcp-e2e-*
}

main() {
  local cmd="${1:-help}"
  shift || true

  case "$cmd" in
    sync)
      do_sync
      ;;
    generate)
      do_generate
      ;;
    build-generated)
      do_build_generated
      ;;
    run-generated)
      do_run_generated
      ;;
    test-list)
      do_test_list
      ;;
    test-call)
      do_test_call "$@"
      ;;
    smoke)
      do_sync
      do_generate
      do_build_generated
      ;;
    clean)
      do_clean
      ;;
    clean-tmp)
      do_clean_tmp
      ;;
    clean-all)
      do_clean_all
      ;;
    help|-h|--help)
      usage
      ;;
    *)
      echo "Unknown command: $cmd" >&2
      usage
      exit 1
      ;;
  esac
}

main "$@"
