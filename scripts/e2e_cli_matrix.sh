#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

TMP_ROOT="${TMP_ROOT:-${RUNNER_TEMP:-/tmp}/openapi-to-mcp-cli-e2e}"
BASIC_OPENAPI_SPEC="${OPENAPI_SPEC:-${REPO_ROOT}/tests/resources/test_openapi.yaml}"
MOCK_API_HOST="${MOCK_API_HOST:-127.0.0.1}"
MOCK_API_PORT="${MOCK_API_PORT:-}"
SPEC_HOST="${SPEC_HOST:-127.0.0.1}"
SPEC_PORT="${SPEC_PORT:-}"
HTTP_HOST="${HTTP_HOST:-127.0.0.1}"
HTTP_PORT="${HTTP_PORT:-}"
RUN_HTTP_PORT="${RUN_HTTP_PORT:-}"
MCP_ENDPOINT="${MCP_ENDPOINT:-/mcp}"
KEEP_TMP="${KEEP_TMP:-0}"
TARGET_API_BASE_URL=""
SPEC_URL=""
STDIO_OUTPUT_DIR="${TMP_ROOT}/generated-stdio"
HTTP_OUTPUT_DIR="${TMP_ROOT}/generated-http"
RUN_OUTPUT_DIR="${TMP_ROOT}/run-generated"
RUN_NO_VALIDATION_OUTPUT_DIR="${TMP_ROOT}/run-no-validation"
HTTP_SERVER_PID=""
RUN_SERVER_PID=""
PIDS=()

ensure_command() { command -v "$1" >/dev/null 2>&1 || { echo "Missing required command: $1" >&2; exit 1; }; }

run_uv() {
  if [[ -n "${UV_CACHE_DIR:-}" ]]; then
    env UV_CACHE_DIR="$UV_CACHE_DIR" uv "$@"
  else
    uv "$@"
  fi
}

choose_free_port() {
  python3 - "$1" <<'PY'
import socket, sys
with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
    sock.bind((sys.argv[1], 0))
    print(sock.getsockname()[1])
PY
}

write_duplicate_operation_spec() {
  local path="$1"
  cat >"$path" <<'EOF'
{
  "openapi": "3.0.0",
  "info": {"title": "Generated Name Collision API", "version": "1.0.0"},
  "servers": [{"url": "https://example.com/api"}],
  "paths": {
    "/a-b": {"get": {"summary": "Dash path", "responses": {"200": {"description": "OK"}}}},
    "/a_b": {"get": {"summary": "Underscore path", "responses": {"200": {"description": "OK"}}}}
  }
}
EOF
}

strip_ansi() {
  python3 -c '
import re
import sys

print(re.sub(r"\x1b\[[0-9;]*[A-Za-z]", "", sys.stdin.read()), end="")
'
}

wait_for_http_status() {
  local url="$1" expected="$2" status=""
  for _ in $(seq 1 60); do
    status="$(curl --silent --output /dev/null --write-out '%{http_code}' "$url" || true)"
    [[ "$status" == "$expected" ]] && return 0
    sleep 1
  done
  echo "Timed out waiting for ${url}. Last status: ${status:-none}" >&2
  return 1
}

replace_or_append_env_var() {
  local file="$1" key="$2" value="$3" tmp_file
  tmp_file="$(mktemp)"
  if [[ -f "$file" ]]; then
    awk -v key="$key" -v value="$value" '
      BEGIN { replaced = 0 }
      { if ($0 ~ ("^" key "=")) { print key "=" value; replaced = 1 } else { print $0 } }
      END { if (replaced == 0) { print key "=" value } }
    ' "$file" >"$tmp_file"
  else
    printf '%s=%s\n' "$key" "$value" >"$tmp_file"
  fi
  mv "$tmp_file" "$file"
}

prepare_env_file() {
  local output_dir="$1" http_port="${2:-}"
  if [[ -f "${output_dir}/.env.example" && ! -f "${output_dir}/.env" ]]; then
    cp "${output_dir}/.env.example" "${output_dir}/.env"
  fi
  replace_or_append_env_var "${output_dir}/.env" "TARGET_API_BASE_URL" "$TARGET_API_BASE_URL"
  replace_or_append_env_var "${output_dir}/.env" "MCP_ALLOWED_HOSTS" "${HTTP_HOST},127.0.0.1,localhost"
  if [[ -n "$http_port" ]]; then
    replace_or_append_env_var "${output_dir}/.env" "MCP_HTTP_PORT" "$http_port"
  fi
}

cleanup_pid() {
  local pid="$1"
  [[ -z "$pid" ]] && return 0
  pkill -P "$pid" >/dev/null 2>&1 || true
  kill "$pid" >/dev/null 2>&1 || true
  wait "$pid" >/dev/null 2>&1 || true
}

cleanup() {
  local exit_code="$?"
  trap - EXIT
  cleanup_pid "$RUN_SERVER_PID"
  cleanup_pid "$HTTP_SERVER_PID"
  for pid in "${PIDS[@]:-}"; do cleanup_pid "$pid"; done
  [[ "$KEEP_TMP" != "1" ]] && rm -rf "$TMP_ROOT"
  exit "$exit_code"
}

assert_output_contains() {
  local expected="$1"; shift
  local cleaned output
  output="$("$@" 2>&1)"
  cleaned="$(printf '%s' "$output" | strip_ansi)"
  printf '%s\n' "$output"
  grep -Fq -- "$expected" <<<"$cleaned" || { echo "Expected output to contain: $expected" >&2; exit 1; }
}

assert_output_matches() {
  local pattern="$1"; shift
  local output
  output="$("$@" 2>&1)"
  printf '%s\n' "$output"
  python3 -c '
import re
import sys

pattern = sys.argv[1]
text = sys.stdin.read()
text = re.sub(r"\x1b\[[0-9;]*[A-Za-z]", "", text)
if re.search(pattern, text, flags=re.MULTILINE | re.DOTALL) is None:
    raise SystemExit(1)
' "$pattern" <<<"$output" || { echo "Expected output to match regex: $pattern" >&2; exit 1; }
}

assert_failure_contains() {
  local expected="$1"; shift
  local cleaned output status
  set +e
  output="$("$@" 2>&1)"
  status="$?"
  set -e
  cleaned="$(printf '%s' "$output" | strip_ansi)"
  if [[ "$status" -eq 0 ]]; then
    printf '%s\n' "$output"
    echo "Expected command to fail" >&2
    exit 1
  fi
  if ! grep -Fq -- "$expected" <<<"$cleaned"; then
    printf '%s\n' "$output"
    echo "Expected failure output to contain: $expected" >&2
    exit 1
  fi
  if [[ "${E2E_VERBOSE:-0}" == "1" ]]; then
    printf '%s\n' "$output"
  else
    echo "Verified expected failure: $expected"
  fi
}

assert_file_contains() {
  local expected="$1" path="$2"
  grep -Fq -- "$expected" "$path" || {
    echo "Expected ${path} to contain: $expected" >&2
    exit 1
  }
}

generate_server() {
  local output_dir="$1" transport="$2" spec_source="$3"; shift 3
  rm -rf "$output_dir"
  (
    cd "$REPO_ROOT"
    run_uv run openapi-to-mcp generate \
      --openapi-json "$spec_source" \
      --output-dir "$output_dir" \
      --mcp-server-name "$(basename "$output_dir")" \
      --transport "$transport" \
      --host "$HTTP_HOST" \
      --port "${HTTP_PORT:-8080}" \
      --mcp-endpoint "$MCP_ENDPOINT" \
      "$@"
  )
}

build_generated_server() { (cd "$1" && npm install && npm run build); }

start_generated_http_server() {
  local output_dir="$1" log_file="$2"
  HTTP_PORT="${HTTP_PORT:-$(choose_free_port "$HTTP_HOST")}"
  prepare_env_file "$output_dir" "$HTTP_PORT"
  (cd "$output_dir" && node build/index.js >"$log_file" 2>&1) &
  HTTP_SERVER_PID="$!"
  wait_for_http_status "http://${HTTP_HOST}:${HTTP_PORT}${MCP_ENDPOINT}" 400
}

stop_run_command() {
  cleanup_pid "$RUN_SERVER_PID"
  RUN_SERVER_PID=""
}

start_run_command() {
  local log_file="$1" output_dir="$2"; shift 2
  RUN_HTTP_PORT="$(choose_free_port "$HTTP_HOST")"
  local cmd=(
    uv run openapi-to-mcp run
    --openapi-json "$BASIC_OPENAPI_SPEC"
    --output-dir "$output_dir"
    --transport streamable-http
    --host "$HTTP_HOST"
    --port "$RUN_HTTP_PORT"
    --mcp-endpoint "$MCP_ENDPOINT"
    --target-api-base-url "$TARGET_API_BASE_URL"
    "$@"
  )
  stop_run_command
  rm -rf "$output_dir"
  (
    cd "$REPO_ROOT"
    if [[ -n "${UV_CACHE_DIR:-}" ]]; then
      exec env UV_CACHE_DIR="$UV_CACHE_DIR" "${cmd[@]}"
    fi
    exec "${cmd[@]}"
  ) &
  RUN_SERVER_PID="$!"
  wait_for_http_status "http://${HTTP_HOST}:${RUN_HTTP_PORT}${MCP_ENDPOINT}" 400
}

trap cleanup EXIT

main() {
  local duplicate_spec="${TMP_ROOT}/duplicate-operation-spec.json"
  local duplicate_output_dir="${TMP_ROOT}/generated-duplicate-fail"
  ensure_command uv; ensure_command npm; ensure_command node; ensure_command python3; ensure_command curl
  mkdir -p "$TMP_ROOT"
  MOCK_API_PORT="${MOCK_API_PORT:-$(choose_free_port "$MOCK_API_HOST")}"
  SPEC_PORT="${SPEC_PORT:-$(choose_free_port "$SPEC_HOST")}"
  TARGET_API_BASE_URL="http://${MOCK_API_HOST}:${MOCK_API_PORT}"
  SPEC_URL="http://${SPEC_HOST}:${SPEC_PORT}/test_openapi.yaml"

  (cd "$REPO_ROOT" && run_uv run python scripts/mock_target_api.py --host "$MOCK_API_HOST" --port "$MOCK_API_PORT") >"${TMP_ROOT}/mock.log" 2>&1 &
  PIDS+=("$!")
  (cd "${REPO_ROOT}/tests/resources" && python3 -m http.server "$SPEC_PORT" --bind "$SPEC_HOST") >"${TMP_ROOT}/spec.log" 2>&1 &
  PIDS+=("$!")
  wait_for_http_status "${TARGET_API_BASE_URL}/health" 200
  wait_for_http_status "$SPEC_URL" 200

  assert_output_contains "generate" uv run openapi-to-mcp --help
  assert_output_contains "--openapi-json" uv run openapi-to-mcp generate --help
  assert_output_contains "--target-api-base-url" uv run openapi-to-mcp run --help
  assert_output_contains "--server-cmd" uv run openapi-to-mcp test-server --help

  generate_server "$STDIO_OUTPUT_DIR" "stdio" "$BASIC_OPENAPI_SPEC" --no-strict
  prepare_env_file "$STDIO_OUTPUT_DIR"
  build_generated_server "$STDIO_OUTPUT_DIR"
  assert_output_contains "testConversionTool" uv run openapi-to-mcp test-server --transport stdio --server-cmd "node ${STDIO_OUTPUT_DIR}/build/index.js" --env-source "${STDIO_OUTPUT_DIR}/.env" --list-tools
  assert_output_matches '"isError"\s*:\s*false' uv run openapi-to-mcp test-server --transport stdio --server-cmd "node ${STDIO_OUTPUT_DIR}/build/index.js" --env-source "${STDIO_OUTPUT_DIR}/.env" --tool-name testConversionTool --tool-args '{"status":"available"}'

  generate_server "$HTTP_OUTPUT_DIR" "streamable-http" "$SPEC_URL"
  build_generated_server "$HTTP_OUTPUT_DIR"
  start_generated_http_server "$HTTP_OUTPUT_DIR" "${TMP_ROOT}/generated-http.log"
  assert_output_contains "testConversionTool" uv run openapi-to-mcp test-server --transport streamable-http --host "$HTTP_HOST" --port "$HTTP_PORT" --mcp-endpoint "$MCP_ENDPOINT" --list-tools
  assert_output_matches '"result"\s*:\s*\{' uv run openapi-to-mcp test-server --transport streamable-http --host "$HTTP_HOST" --port "$HTTP_PORT" --mcp-endpoint "$MCP_ENDPOINT" --tool-name testConversionTool --tool-args '{"status":"available"}'

  assert_failure_contains "--server-cmd is required for stdio transport" uv run openapi-to-mcp test-server --transport stdio --list-tools
  assert_failure_contains "TARGET_API_BASE_URL is unresolved" uv run openapi-to-mcp run --openapi-json "$BASIC_OPENAPI_SPEC"
  write_duplicate_operation_spec "$duplicate_spec"
  assert_failure_contains "Duplicate tool name detected" uv run openapi-to-mcp generate --openapi-json "$duplicate_spec" --output-dir "$duplicate_output_dir" --no-strict --on-mapping-error fail

  start_run_command "${TMP_ROOT}/run.log" "$RUN_OUTPUT_DIR" --max-concurrency 7
  assert_file_contains "MCP_MAX_CONCURRENCY=7" "${RUN_OUTPUT_DIR}/.env"
  assert_output_contains "testConversionTool" uv run openapi-to-mcp test-server --transport streamable-http --host "$HTTP_HOST" --port "$RUN_HTTP_PORT" --mcp-endpoint "$MCP_ENDPOINT" --list-tools
  assert_output_matches '"result"\s*:\s*\{' uv run openapi-to-mcp test-server --transport streamable-http --host "$HTTP_HOST" --port "$RUN_HTTP_PORT" --mcp-endpoint "$MCP_ENDPOINT" --tool-name testConversionTool --tool-args '{"status":"available"}'
  assert_output_contains "Input validation failed" uv run openapi-to-mcp test-server --transport streamable-http --host "$HTTP_HOST" --port "$RUN_HTTP_PORT" --mcp-endpoint "$MCP_ENDPOINT" --tool-name testConversionTool --tool-args '{"status":{"bad":1}}'

  start_run_command "${TMP_ROOT}/run-no-validation.log" "$RUN_NO_VALIDATION_OUTPUT_DIR" --runtime-validation none
  assert_output_contains '"bad": "1"' uv run openapi-to-mcp test-server --transport streamable-http --host "$HTTP_HOST" --port "$RUN_HTTP_PORT" --mcp-endpoint "$MCP_ENDPOINT" --tool-name testConversionTool --tool-args '{"status":{"bad":1}}'

  echo "CLI E2E matrix passed"
}

main "$@"
