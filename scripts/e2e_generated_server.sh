#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

TMP_ROOT="${TMP_ROOT:-${RUNNER_TEMP:-/tmp}/openapi-to-mcp-e2e}"
BASIC_OPENAPI_SPEC="${OPENAPI_SPEC:-${REPO_ROOT}/tests/resources/test_openapi.yaml}"
AUTH_OPENAPI_SPEC="${AUTH_OPENAPI_SPEC:-${REPO_ROOT}/tests/resources/auth_openapi.yaml}"
AUDIT_OPENAPI_SPEC="${AUDIT_OPENAPI_SPEC:-${REPO_ROOT}/tests/resources/audit_openapi.yaml}"
MOCK_API_HOST="${MOCK_API_HOST:-127.0.0.1}"
MOCK_API_PORT="${MOCK_API_PORT:-}"
HTTP_HOST="${HTTP_HOST:-127.0.0.1}"
HTTP_PORT="${HTTP_PORT:-}"
MCP_ENDPOINT="${MCP_ENDPOINT:-/mcp}"
KEEP_TMP="${KEEP_TMP:-0}"
TARGET_API_BASE_URL=""
CURRENT_HTTP_PORT=""
STDIO_OUTPUT_DIR="${TMP_ROOT}/generated-stdio"
HTTP_OUTPUT_DIR="${TMP_ROOT}/generated-http"
NO_VALIDATION_OUTPUT_DIR="${TMP_ROOT}/generated-no-validation-stdio"
GROUPED_OUTPUT_DIR="${TMP_ROOT}/generated-grouped-stdio"
AUTH_STDIO_OUTPUT_DIR="${TMP_ROOT}/generated-auth-stdio"
AUTH_HTTP_OUTPUT_DIR="${TMP_ROOT}/generated-auth-http"
AUDIT_HTTP_OUTPUT_DIR="${TMP_ROOT}/generated-audit-http"
AUTH_HEADER_API_KEY="${AUTH_HEADER_API_KEY:-header-secret}"
AUTH_QUERY_API_KEY="${AUTH_QUERY_API_KEY:-query-secret}"
AUTH_COOKIE_API_KEY="${AUTH_COOKIE_API_KEY:-cookie-secret}"
AUTH_BEARER_TOKEN="${AUTH_BEARER_TOKEN:-bearer-secret}"

HTTP_SERVER_PID=""
PIDS=()

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

cleanup() {
  local exit_code="$?"
  trap - EXIT

  if [[ -n "$HTTP_SERVER_PID" ]] && kill -0 "$HTTP_SERVER_PID" >/dev/null 2>&1; then
    kill "$HTTP_SERVER_PID" >/dev/null 2>&1 || true
    wait "$HTTP_SERVER_PID" >/dev/null 2>&1 || true
  fi

  for pid in "${PIDS[@]:-}"; do
    if kill -0 "$pid" >/dev/null 2>&1; then
      kill "$pid" >/dev/null 2>&1 || true
      wait "$pid" >/dev/null 2>&1 || true
    fi
  done

  if [[ "$KEEP_TMP" != "1" ]]; then
    rm -rf "$TMP_ROOT"
  fi

  exit "$exit_code"
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

build_allowed_hosts() {
  local candidate_host="$1"
  printf '%s\n' \
    "127.0.0.1" \
    "localhost" \
    "$candidate_host" | awk 'NF && !seen[$0]++ { print }' | paste -sd',' -
}

ensure_process_alive() {
  local pid="$1"
  local name="$2"
  local log_file="${3:-}"
  if kill -0 "$pid" >/dev/null 2>&1; then
    return 0
  fi

  echo "${name} exited unexpectedly." >&2
  if [[ -n "$log_file" && -f "$log_file" ]]; then
    echo "--- ${name} log ---" >&2
    cat "$log_file" >&2
    echo "--- end ${name} log ---" >&2
  fi
  return 1
}

choose_free_port() {
  local host="$1"
  python3 - "$host" <<'PY'
import socket
import sys

host = sys.argv[1]
with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
    sock.bind((host, 0))
    print(sock.getsockname()[1])
PY
}

initialize_ports() {
  if [[ -z "$MOCK_API_PORT" ]]; then
    MOCK_API_PORT="$(choose_free_port "$MOCK_API_HOST")"
  fi
  TARGET_API_BASE_URL="http://${MOCK_API_HOST}:${MOCK_API_PORT}"
}

wait_for_http_status() {
  local url="$1"
  shift
  local expected_statuses=("$@")
  local status

  for _ in $(seq 1 60); do
    status="$(curl --silent --output /dev/null --write-out '%{http_code}' "$url" || true)"
    for expected in "${expected_statuses[@]}"; do
      if [[ "$status" == "$expected" ]]; then
        return 0
      fi
    done
    sleep 1
  done

  echo "Timed out waiting for ${url}. Last status: ${status:-none}" >&2
  return 1
}

wait_for_mock_api_ready() {
  local pid="$1"
  local log_file="$2"

  ensure_process_alive "$pid" "mock target API" "$log_file"
  wait_for_http_status "http://${MOCK_API_HOST}:${MOCK_API_PORT}/health" 200
  ensure_process_alive "$pid" "mock target API" "$log_file"
  wait_for_http_status "http://${MOCK_API_HOST}:${MOCK_API_PORT}/auth/header" 401
  ensure_process_alive "$pid" "mock target API" "$log_file"
}

prepare_env_file() {
  local output_dir="$1"

  if [[ -f "${output_dir}/.env.example" && ! -f "${output_dir}/.env" ]]; then
    cp "${output_dir}/.env.example" "${output_dir}/.env"
  fi

  replace_or_append_env_var "${output_dir}/.env" "TARGET_API_BASE_URL" "$TARGET_API_BASE_URL"
  replace_or_append_env_var "${output_dir}/.env" "MCP_ALLOWED_HOSTS" "$(build_allowed_hosts "$HTTP_HOST")"
}

prepare_auth_env_file() {
  local output_dir="$1"
  replace_or_append_env_var "${output_dir}/.env" "AUTH_HEADERAPIKEY_API_KEY" "$AUTH_HEADER_API_KEY"
  replace_or_append_env_var "${output_dir}/.env" "AUTH_QUERYAPIKEY_API_KEY" "$AUTH_QUERY_API_KEY"
  replace_or_append_env_var "${output_dir}/.env" "AUTH_COOKIEAPIKEY_API_KEY" "$AUTH_COOKIE_API_KEY"
  replace_or_append_env_var "${output_dir}/.env" "AUTH_BEARERAUTH_TOKEN" "$AUTH_BEARER_TOKEN"
}

create_missing_bearer_env_file() {
  local output_dir="$1"
  local missing_env="${output_dir}/.env.missing-bearer"
  cp "${output_dir}/.env" "$missing_env"
  replace_or_append_env_var "$missing_env" "AUTH_BEARERAUTH_TOKEN" ""
  printf '%s\n' "$missing_env"
}

generate_server() {
  local output_dir="$1"
  local transport="$2"
  local openapi_spec="$3"
  local server_name="$4"
  local runtime_validation="${5:-input}"
  local tool_grouping="${6:-none}"

  rm -rf "$output_dir"

  local args=(
    generate
    --openapi-json "$openapi_spec"
    --output-dir "$output_dir"
    --mcp-server-name "$server_name"
    --transport "$transport"
    --runtime-validation "$runtime_validation"
    --tool-grouping "$tool_grouping"
  )

  if [[ "$transport" == "streamable-http" ]]; then
    local generate_http_port="${HTTP_PORT:-8080}"
    args+=(
      --host "$HTTP_HOST"
      --port "$generate_http_port"
      --mcp-endpoint "$MCP_ENDPOINT"
    )
  fi

  (
    cd "$REPO_ROOT"
    run_uv run openapi-to-mcp "${args[@]}"
  )

  prepare_env_file "$output_dir"
}

build_generated_server() {
  local output_dir="$1"
  (
    cd "$output_dir"
    npm install
    npm run build
  )
}

start_streamable_http_server() {
  local output_dir="$1"
  local log_file
  log_file="$(http_server_log_file "$output_dir")"
  local runtime_http_port="${HTTP_PORT:-}"

  if [[ -n "$HTTP_SERVER_PID" ]] && kill -0 "$HTTP_SERVER_PID" >/dev/null 2>&1; then
    kill "$HTTP_SERVER_PID" >/dev/null 2>&1 || true
    wait "$HTTP_SERVER_PID" >/dev/null 2>&1 || true
  fi

  if [[ -z "$runtime_http_port" ]]; then
    runtime_http_port="$(choose_free_port "$HTTP_HOST")"
  fi

  replace_or_append_env_var "${output_dir}/.env" "MCP_HTTP_PORT" "$runtime_http_port"
  CURRENT_HTTP_PORT="$runtime_http_port"

  (
    cd "$output_dir"
    node build/index.js >"$log_file" 2>&1
  ) &
  HTTP_SERVER_PID="$!"
  PIDS+=("$HTTP_SERVER_PID")

  ensure_process_alive "$HTTP_SERVER_PID" "generated HTTP server" "$log_file"
  wait_for_http_status "http://${HTTP_HOST}:${CURRENT_HTTP_PORT}${MCP_ENDPOINT}" 400
  ensure_process_alive "$HTTP_SERVER_PID" "generated HTTP server" "$log_file"
}

http_server_log_file() {
  local output_dir="$1"
  printf '%s/%s.log\n' "$TMP_ROOT" "$(basename "$output_dir")"
}

run_suite_assertions() {
  local suite="$1"
  local transport="$2"
  local output_dir="$3"
  local env_source="${4:-}"
  local args=(--suite "$suite" --transport "$transport")

  if [[ "$transport" == "stdio" ]]; then
    args+=(--server-cmd "node ${output_dir}/build/index.js" --env-source "$env_source")
  else
    args+=(--endpoint-url "http://${HTTP_HOST}:${CURRENT_HTTP_PORT}${MCP_ENDPOINT}")
  fi

  (
    cd "$REPO_ROOT"
    run_uv run python scripts/assert_generated_server.py "${args[@]}"
  )
}

run_performance_suite_assertions() {
  local suite="$1"
  local tool_name="${2:-testConversionTool}"

  (
    cd "$REPO_ROOT"
    run_uv run python scripts/assert_generated_server_performance.py \
      --suite "$suite" \
      --tool-name "$tool_name" \
      --endpoint-url "http://${HTTP_HOST}:${CURRENT_HTTP_PORT}${MCP_ENDPOINT}"
  )
}

run_resilience_suite_assertions() {
  local suite="$1"
  local tool_name="${2:-testConversionTool}"
  local cooldown_ms="${3:-2000}"

  (
    cd "$REPO_ROOT"
    run_uv run python scripts/assert_generated_server_resilience.py \
      --suite "$suite" \
      --tool-name "$tool_name" \
      --cooldown-ms "$cooldown_ms" \
      --mock-base-url "$TARGET_API_BASE_URL" \
      --endpoint-url "http://${HTTP_HOST}:${CURRENT_HTTP_PORT}${MCP_ENDPOINT}"
  )
}

run_access_suite_assertions() {
  local suite="$1"
  local tool_name="$2"
  local identity_header="${3:-}"
  local identity_value="${4:-}"
  local args=(
    --suite "$suite"
    --tool-name "$tool_name"
    --endpoint-url "http://${HTTP_HOST}:${CURRENT_HTTP_PORT}${MCP_ENDPOINT}"
  )

  if [[ -n "$identity_header" ]]; then
    args+=(--identity-header "$identity_header")
  fi
  if [[ -n "$identity_value" ]]; then
    args+=(--identity-value "$identity_value")
  fi

  (
    cd "$REPO_ROOT"
    run_uv run python scripts/assert_generated_server_access.py "${args[@]}"
  )
}

run_audit_assertion() {
  local output_dir="$1"
  local tool_name="$2"
  local tool_arguments="$3"
  shift 3

  (
    cd "$REPO_ROOT"
    run_uv run python scripts/assert_generated_server_audit.py \
      --endpoint-url "http://${HTTP_HOST}:${CURRENT_HTTP_PORT}${MCP_ENDPOINT}" \
      --tool-name "$tool_name" \
      --tool-arguments "$tool_arguments" \
      --log-file "$(http_server_log_file "$output_dir")" \
      "$@"
  )
}

run_cached_audit_assertion() {
  local output_dir="$1"
  local tool_name="${2:-testConversionTool}"
  local tool_arguments="${3:-{\"status\":\"cached\"}}"

  (
    cd "$REPO_ROOT"
    run_uv run python scripts/assert_generated_server_cached_audit.py \
      --endpoint-url "http://${HTTP_HOST}:${CURRENT_HTTP_PORT}${MCP_ENDPOINT}" \
      --tool-name "$tool_name" \
      --tool-arguments "$tool_arguments" \
      --log-file "$(http_server_log_file "$output_dir")"
  )
}

run_observability_assertion() {
  local transport="$1"
  local output_dir="$2"
  local tool_arguments="$3"
  local expect_error="${4:-0}"
  local args=(--transport "$transport" --tool-name "testConversionTool" --tool-arguments "$tool_arguments")

  if [[ "$transport" == "stdio" ]]; then
    args+=(--server-cmd "node ${output_dir}/build/index.js" --env-source "${output_dir}/.env")
  else
    args+=(--endpoint-url "http://${HTTP_HOST}:${CURRENT_HTTP_PORT}${MCP_ENDPOINT}")
  fi
  if [[ "$expect_error" == "1" ]]; then
    args+=(--expect-error)
  fi

  (
    cd "$REPO_ROOT"
    run_uv run python scripts/assert_runtime_observability.py "${args[@]}"
  )
}

assert_startup_failure() {
  local output_dir="$1"
  local env_key="$2"
  local env_value="$3"
  local expected_message="$4"
  local base_env="${output_dir}/.env"
  local invalid_env="${output_dir}/.env.invalid"
  local log_file="${TMP_ROOT}/$(basename "$output_dir")-invalid.log"

  cp "$base_env" "$invalid_env"
  replace_or_append_env_var "$invalid_env" "$env_key" "$env_value"

  set +e
  (
    cd "$output_dir"
    set -a
    # shellcheck disable=SC1090
    source "$invalid_env"
    set +a
    node build/index.js
  ) >"$log_file" 2>&1
  local exit_code="$?"
  set -e

  if [[ "$exit_code" -eq 0 ]]; then
    echo "Expected startup failure for ${env_key}, but server started successfully." >&2
    cat "$log_file" >&2
    exit 1
  fi

  if ! grep -Fq -- "$expected_message" "$log_file"; then
    echo "Startup failure log did not contain expected message: ${expected_message}" >&2
    cat "$log_file" >&2
    exit 1
  fi
}

trap 'exit 1' INT TERM
trap cleanup EXIT

main() {
  ensure_command uv
  ensure_command npm
  ensure_command node
  ensure_command python3
  ensure_command curl

  initialize_ports
  mkdir -p "$TMP_ROOT"

  echo "Starting mock target API on ${TARGET_API_BASE_URL}"
  local mock_log_file="${TMP_ROOT}/mock-target-api.log"
  (
    cd "$REPO_ROOT"
    run_uv run python scripts/mock_target_api.py \
      --host "$MOCK_API_HOST" \
      --port "$MOCK_API_PORT"
  ) >"$mock_log_file" 2>&1 &
  local mock_pid="$!"
  PIDS+=("$mock_pid")

  wait_for_mock_api_ready "$mock_pid" "$mock_log_file"

  echo "Generating and validating stdio server"
  generate_server \
    "$STDIO_OUTPUT_DIR" "stdio" "$BASIC_OPENAPI_SPEC" "generated-stdio-e2e"
  build_generated_server "$STDIO_OUTPUT_DIR"
  run_suite_assertions "basic" "stdio" "$STDIO_OUTPUT_DIR" "${STDIO_OUTPUT_DIR}/.env"
  run_suite_assertions "validation-failure" "stdio" \
    "$STDIO_OUTPUT_DIR" "${STDIO_OUTPUT_DIR}/.env"
  run_observability_assertion "stdio" "$STDIO_OUTPUT_DIR" '{"status":"available"}'
  assert_startup_failure \
    "$STDIO_OUTPUT_DIR" "TARGET_API_BASE_URL" "ftp://example.com" \
    "TARGET_API_BASE_URL must use http or https."
  assert_startup_failure \
    "$STDIO_OUTPUT_DIR" "MCP_MAX_CONCURRENCY" "0" \
    "MCP_MAX_CONCURRENCY must be an integer >= 1."
  assert_startup_failure \
    "$STDIO_OUTPUT_DIR" "MCP_CACHE_TTL_MS" "-1" \
    "MCP_CACHE_TTL_MS must be an integer >= 0."
  assert_startup_failure \
    "$STDIO_OUTPUT_DIR" "MCP_CACHE_MAX_ENTRIES" "0" \
    "MCP_CACHE_MAX_ENTRIES must be an integer >= 1."
  assert_startup_failure \
    "$STDIO_OUTPUT_DIR" "MCP_PERFORMANCE_PRESET" "toString" \
    "MCP_PERFORMANCE_PRESET must be one of: off, conservative, balanced, aggressive."
  assert_startup_failure \
    "$STDIO_OUTPUT_DIR" "MCP_RETRY_MAX_RETRIES" "-1" \
    "MCP_RETRY_MAX_RETRIES must be an integer >= 0."
  assert_startup_failure \
    "$STDIO_OUTPUT_DIR" "MCP_CIRCUIT_BREAKER_COOLDOWN_MS" "0" \
    "MCP_CIRCUIT_BREAKER_COOLDOWN_MS must be an integer >= 1."
  assert_startup_failure \
    "$STDIO_OUTPUT_DIR" "MCP_TOOL_ALLOWLISTS" "{bad-json" \
    "MCP_TOOL_ALLOWLISTS must be valid JSON."

  echo "Generating and validating streamable-http server"
  generate_server \
    "$HTTP_OUTPUT_DIR" "streamable-http" "$BASIC_OPENAPI_SPEC" "generated-http-e2e"
  build_generated_server "$HTTP_OUTPUT_DIR"
  start_streamable_http_server "$HTTP_OUTPUT_DIR"
  run_suite_assertions "basic" "streamable-http" "$HTTP_OUTPUT_DIR"
  run_suite_assertions "validation-failure" "streamable-http" "$HTTP_OUTPUT_DIR"
  run_suite_assertions "upstream-server-error" "streamable-http" "$HTTP_OUTPUT_DIR"
  run_observability_assertion "streamable-http" "$HTTP_OUTPUT_DIR" '{"status":"available"}'
  run_observability_assertion "streamable-http" "$HTTP_OUTPUT_DIR" '{"status":"server_error"}' 1
  replace_or_append_env_var "${HTTP_OUTPUT_DIR}/.env" "MCP_TOOL_ACCESS_MODE" "allowlist"
  replace_or_append_env_var "${HTTP_OUTPUT_DIR}/.env" "MCP_TOOL_ACCESS_DEFAULT" "deny"
  replace_or_append_env_var "${HTTP_OUTPUT_DIR}/.env" "MCP_TOOL_IDENTITY_HEADER" "X-MCP-Tenant"
  replace_or_append_env_var "${HTTP_OUTPUT_DIR}/.env" "MCP_TOOL_ALLOWLISTS" '{"acme":[" testConversionTool "]}'
  start_streamable_http_server "$HTTP_OUTPUT_DIR"
  run_access_suite_assertions "allowed" "testConversionTool" "X-MCP-Tenant" "acme"
  run_access_suite_assertions "denied" "testConversionTool" "X-MCP-Tenant" "blocked"
  replace_or_append_env_var "${HTTP_OUTPUT_DIR}/.env" "MCP_TOOL_ACCESS_MODE" "off"
  replace_or_append_env_var "${HTTP_OUTPUT_DIR}/.env" "MCP_TOOL_ACCESS_DEFAULT" "allow"
  replace_or_append_env_var "${HTTP_OUTPUT_DIR}/.env" "MCP_TOOL_IDENTITY_HEADER" ""
  replace_or_append_env_var "${HTTP_OUTPUT_DIR}/.env" "MCP_TOOL_ALLOWLISTS" ""
  replace_or_append_env_var "${HTTP_OUTPUT_DIR}/.env" "MCP_CACHE_TTL_MS" "60000"
  replace_or_append_env_var "${HTTP_OUTPUT_DIR}/.env" "MCP_CACHE_MAX_ENTRIES" "1000"
  replace_or_append_env_var "${HTTP_OUTPUT_DIR}/.env" "MCP_RATE_LIMIT_PER_MINUTE" "0"
  replace_or_append_env_var "${HTTP_OUTPUT_DIR}/.env" "MCP_AUDIT_MODE" "logs"
  start_streamable_http_server "$HTTP_OUTPUT_DIR"
  run_performance_suite_assertions "cached"
  run_cached_audit_assertion "$HTTP_OUTPUT_DIR"
  replace_or_append_env_var "${HTTP_OUTPUT_DIR}/.env" "MCP_CACHE_TTL_MS" "60000"
  replace_or_append_env_var "${HTTP_OUTPUT_DIR}/.env" "MCP_CACHE_MAX_ENTRIES" "1000"
  replace_or_append_env_var "${HTTP_OUTPUT_DIR}/.env" "MCP_RATE_LIMIT_PER_MINUTE" "1"
  replace_or_append_env_var "${HTTP_OUTPUT_DIR}/.env" "MCP_AUDIT_MODE" "off"
  start_streamable_http_server "$HTTP_OUTPUT_DIR"
  run_performance_suite_assertions "cached-rate-limited"
  replace_or_append_env_var "${HTTP_OUTPUT_DIR}/.env" "MCP_CACHE_TTL_MS" "0"
  replace_or_append_env_var "${HTTP_OUTPUT_DIR}/.env" "MCP_CACHE_MAX_ENTRIES" "1000"
  replace_or_append_env_var "${HTTP_OUTPUT_DIR}/.env" "MCP_RATE_LIMIT_PER_MINUTE" "1"
  start_streamable_http_server "$HTTP_OUTPUT_DIR"
  run_performance_suite_assertions "rate-limited"
  replace_or_append_env_var "${HTTP_OUTPUT_DIR}/.env" "MCP_CACHE_TTL_MS" "0"
  replace_or_append_env_var "${HTTP_OUTPUT_DIR}/.env" "MCP_RATE_LIMIT_PER_MINUTE" "0"
  replace_or_append_env_var "${HTTP_OUTPUT_DIR}/.env" "MCP_PERFORMANCE_PRESET" "balanced"
  replace_or_append_env_var "${HTTP_OUTPUT_DIR}/.env" "MCP_CACHE_TTL_MS" ""
  replace_or_append_env_var "${HTTP_OUTPUT_DIR}/.env" "MCP_CACHE_MAX_ENTRIES" ""
  replace_or_append_env_var "${HTTP_OUTPUT_DIR}/.env" "MCP_RATE_LIMIT_PER_MINUTE" ""
  replace_or_append_env_var "${HTTP_OUTPUT_DIR}/.env" "MCP_RETRY_MAX_RETRIES" ""
  replace_or_append_env_var "${HTTP_OUTPUT_DIR}/.env" "MCP_RETRY_BUDGET_PER_MINUTE" ""
  replace_or_append_env_var "${HTTP_OUTPUT_DIR}/.env" \
    "MCP_CIRCUIT_BREAKER_FAILURE_THRESHOLD" ""
  replace_or_append_env_var "${HTTP_OUTPUT_DIR}/.env" \
    "MCP_CIRCUIT_BREAKER_COOLDOWN_MS" ""
  start_streamable_http_server "$HTTP_OUTPUT_DIR"
  run_performance_suite_assertions "preset-cached"
  replace_or_append_env_var "${HTTP_OUTPUT_DIR}/.env" "MCP_CACHE_TTL_MS" "0"
  replace_or_append_env_var "${HTTP_OUTPUT_DIR}/.env" "MCP_RATE_LIMIT_PER_MINUTE" "0"
  start_streamable_http_server "$HTTP_OUTPUT_DIR"
  run_performance_suite_assertions "preset-uncached"
  replace_or_append_env_var "${HTTP_OUTPUT_DIR}/.env" "MCP_PERFORMANCE_PRESET" "off"
  replace_or_append_env_var "${HTTP_OUTPUT_DIR}/.env" "MCP_RETRY_MAX_RETRIES" "1"
  replace_or_append_env_var "${HTTP_OUTPUT_DIR}/.env" "MCP_RETRY_BUDGET_PER_MINUTE" "5"
  replace_or_append_env_var "${HTTP_OUTPUT_DIR}/.env" \
    "MCP_CIRCUIT_BREAKER_FAILURE_THRESHOLD" "0"
  replace_or_append_env_var "${HTTP_OUTPUT_DIR}/.env" \
    "MCP_CIRCUIT_BREAKER_COOLDOWN_MS" "30000"
  start_streamable_http_server "$HTTP_OUTPUT_DIR"
  run_resilience_suite_assertions "retry-recovers"
  replace_or_append_env_var "${HTTP_OUTPUT_DIR}/.env" "MCP_RETRY_MAX_RETRIES" "2"
  replace_or_append_env_var "${HTTP_OUTPUT_DIR}/.env" "MCP_RETRY_BUDGET_PER_MINUTE" "1"
  start_streamable_http_server "$HTTP_OUTPUT_DIR"
  run_resilience_suite_assertions "retry-budget-exhausted"
  replace_or_append_env_var "${HTTP_OUTPUT_DIR}/.env" "MCP_RETRY_MAX_RETRIES" "0"
  replace_or_append_env_var "${HTTP_OUTPUT_DIR}/.env" "MCP_RETRY_BUDGET_PER_MINUTE" "0"
  replace_or_append_env_var "${HTTP_OUTPUT_DIR}/.env" \
    "MCP_CIRCUIT_BREAKER_FAILURE_THRESHOLD" "2"
  replace_or_append_env_var "${HTTP_OUTPUT_DIR}/.env" \
    "MCP_CIRCUIT_BREAKER_COOLDOWN_MS" "2000"
  start_streamable_http_server "$HTTP_OUTPUT_DIR"
  run_resilience_suite_assertions "circuit-breaker-open" "testConversionTool" "2000"
  replace_or_append_env_var "${HTTP_OUTPUT_DIR}/.env" \
    "MCP_CIRCUIT_BREAKER_FAILURE_THRESHOLD" "1"
  replace_or_append_env_var "${HTTP_OUTPUT_DIR}/.env" \
    "MCP_CIRCUIT_BREAKER_COOLDOWN_MS" "1000"
  start_streamable_http_server "$HTTP_OUTPUT_DIR"
  run_resilience_suite_assertions \
    "circuit-breaker-recovery" "testConversionTool" "1000"

  echo "Generating and validating audit streamable-http server"
  generate_server \
    "$AUDIT_HTTP_OUTPUT_DIR" "streamable-http" "$AUDIT_OPENAPI_SPEC" \
    "generated-audit-http-e2e"
  build_generated_server "$AUDIT_HTTP_OUTPUT_DIR"
  replace_or_append_env_var "${AUDIT_HTTP_OUTPUT_DIR}/.env" \
    "TARGET_API_AUTH_HEADER" "Authorization: Bearer audit-secret"
  replace_or_append_env_var "${AUDIT_HTTP_OUTPUT_DIR}/.env" "MCP_AUDIT_MODE" "logs"
  replace_or_append_env_var "${AUDIT_HTTP_OUTPUT_DIR}/.env" \
    "MCP_AUDIT_REDACT_QUERY_PARAMS" "status"
  replace_or_append_env_var "${AUDIT_HTTP_OUTPUT_DIR}/.env" \
    "MCP_AUDIT_REDACT_REQUEST_BODY_PATHS" "credentials.token,profile.email,tokens.*"
  replace_or_append_env_var "${AUDIT_HTTP_OUTPUT_DIR}/.env" \
    "MCP_AUDIT_REDACT_RESPONSE_BODY_PATHS" \
    "echoed.credentials.token,echoed.profile.email,echoed.tokens.*"
  start_streamable_http_server "$AUDIT_HTTP_OUTPUT_DIR"
  run_audit_assertion \
    "$AUDIT_HTTP_OUTPUT_DIR" "postAuditBody" \
    '{"status":"queued","requestBody":{"credentials":{"token":"secret-token"},"profile":{"email":"user@example.com"},"tokens":["alpha","beta"],"note":"keep"}}' \
    --redacted-header Authorization \
    --redacted-query status \
    --redacted-request-path credentials.token \
    --redacted-request-path profile.email \
    --redacted-request-path tokens.0 \
    --redacted-request-path tokens.1 \
    --redacted-response-path echoed.credentials.token \
    --redacted-response-path echoed.profile.email \
    --redacted-response-path echoed.tokens.0 \
    --redacted-response-path echoed.tokens.1

  echo "Generating and validating stdio server without runtime validation"
  generate_server \
    "$NO_VALIDATION_OUTPUT_DIR" "stdio" "$BASIC_OPENAPI_SPEC" \
    "generated-no-validation-stdio-e2e" "none"
  build_generated_server "$NO_VALIDATION_OUTPUT_DIR"
  run_suite_assertions "validation-disabled" "stdio" \
    "$NO_VALIDATION_OUTPUT_DIR" "${NO_VALIDATION_OUTPUT_DIR}/.env"

  echo "Generating and validating grouped stdio server"
  generate_server \
    "$GROUPED_OUTPUT_DIR" "stdio" "$BASIC_OPENAPI_SPEC" \
    "generated-grouped-stdio-e2e" "input" "tag-prefix"
  build_generated_server "$GROUPED_OUTPUT_DIR"
  run_suite_assertions "grouped" "stdio" \
    "$GROUPED_OUTPUT_DIR" "${GROUPED_OUTPUT_DIR}/.env"

  echo "Generating and validating auth stdio server"
  generate_server \
    "$AUTH_STDIO_OUTPUT_DIR" "stdio" "$AUTH_OPENAPI_SPEC" "generated-auth-stdio-e2e"
  build_generated_server "$AUTH_STDIO_OUTPUT_DIR"
  prepare_auth_env_file "$AUTH_STDIO_OUTPUT_DIR"
  run_suite_assertions "auth" "stdio" \
    "$AUTH_STDIO_OUTPUT_DIR" "${AUTH_STDIO_OUTPUT_DIR}/.env"
  run_suite_assertions "auth-missing-bearer" "stdio" \
    "$AUTH_STDIO_OUTPUT_DIR" "$(create_missing_bearer_env_file "$AUTH_STDIO_OUTPUT_DIR")"

  echo "Generating and validating auth streamable-http server"
  generate_server \
    "$AUTH_HTTP_OUTPUT_DIR" "streamable-http" "$AUTH_OPENAPI_SPEC" \
    "generated-auth-http-e2e"
  build_generated_server "$AUTH_HTTP_OUTPUT_DIR"
  prepare_auth_env_file "$AUTH_HTTP_OUTPUT_DIR"
  replace_or_append_env_var "${AUTH_HTTP_OUTPUT_DIR}/.env" "MCP_AUDIT_MODE" "logs"
  start_streamable_http_server "$AUTH_HTTP_OUTPUT_DIR"
  run_suite_assertions "auth" "streamable-http" "$AUTH_HTTP_OUTPUT_DIR"
  run_audit_assertion \
    "$AUTH_HTTP_OUTPUT_DIR" "getCookieAuth" '{}' \
    --redacted-header Cookie \
    --redacted-cookie session_token

  echo "Generated-server E2E passed"
}

main "$@"
