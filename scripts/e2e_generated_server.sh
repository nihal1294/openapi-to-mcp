#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

UV_CACHE_DIR="${UV_CACHE_DIR:-${REPO_ROOT}/.uv-cache}"
TMP_ROOT="${TMP_ROOT:-${RUNNER_TEMP:-/tmp}/openapi-to-mcp-e2e}"
OPENAPI_SPEC="${OPENAPI_SPEC:-${REPO_ROOT}/tests/resources/test_openapi.yaml}"
MOCK_API_HOST="${MOCK_API_HOST:-127.0.0.1}"
MOCK_API_PORT="${MOCK_API_PORT:-18080}"
HTTP_HOST="${HTTP_HOST:-127.0.0.1}"
HTTP_PORT="${HTTP_PORT:-18081}"
MCP_ENDPOINT="${MCP_ENDPOINT:-/mcp}"
TOOL_NAME="${TOOL_NAME:-testConversionTool}"
KEEP_TMP="${KEEP_TMP:-0}"
TARGET_API_BASE_URL="http://${MOCK_API_HOST}:${MOCK_API_PORT}"
STDIO_OUTPUT_DIR="${TMP_ROOT}/generated-stdio"
HTTP_OUTPUT_DIR="${TMP_ROOT}/generated-http"

PIDS=()

ensure_command() {
  local cmd="$1"
  if ! command -v "$cmd" >/dev/null 2>&1; then
    echo "Missing required command: $cmd" >&2
    exit 1
  fi
}

cleanup() {
  local exit_code="$?"
  trap - EXIT

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

prepare_env_file() {
  local output_dir="$1"

  if [[ -f "${output_dir}/.env.example" && ! -f "${output_dir}/.env" ]]; then
    cp "${output_dir}/.env.example" "${output_dir}/.env"
  fi

  replace_or_append_env_var "${output_dir}/.env" "TARGET_API_BASE_URL" "$TARGET_API_BASE_URL"
}

generate_server() {
  local output_dir="$1"
  local transport="$2"

  rm -rf "$output_dir"

  local args=(
    generate
    --openapi-json "$OPENAPI_SPEC"
    --output-dir "$output_dir"
    --mcp-server-name "generated-${transport}-e2e"
    --transport "$transport"
  )

  if [[ "$transport" == "streamable-http" ]]; then
    args+=(
      --host "$HTTP_HOST"
      --port "$HTTP_PORT"
      --mcp-endpoint "$MCP_ENDPOINT"
    )
  fi

  (
    cd "$REPO_ROOT"
    UV_CACHE_DIR="$UV_CACHE_DIR" uv run openapi-to-mcp "${args[@]}"
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

run_stdio_assertions() {
  local output_dir="$1"
  local env_file="${output_dir}/.env"
  local server_cmd="node ${output_dir}/build/index.js"

  (
    cd "$REPO_ROOT"
    UV_CACHE_DIR="$UV_CACHE_DIR" uv run python - "$server_cmd" "$env_file" "$TOOL_NAME" <<'PY'
import asyncio
import json
import sys

from openapi_to_mcp.adapters.testing.server_tester import execute_mcp_server
from openapi_to_mcp.common.utils import parse_env_source


def extract_result_payload(response: dict[str, object]) -> dict[str, object]:
    result = response.get("result")
    if isinstance(result, dict):
        return result
    return response


async def main() -> None:
    server_cmd = sys.argv[1]
    env_file = sys.argv[2]
    tool_name = sys.argv[3]
    env = parse_env_source(env_file)

    list_response = await execute_mcp_server(
        transport="stdio",
        method="list",
        req_id=1,
        server_cmd=server_cmd,
        env=env,
    )
    list_payload = extract_result_payload(list_response)
    tool_names = [tool["name"] for tool in list_payload["tools"]]
    if tool_name not in tool_names:
        raise AssertionError(f"Missing tool in stdio list response: {tool_names}")

    call_response = await execute_mcp_server(
        transport="stdio",
        method="call",
        req_id=2,
        server_cmd=server_cmd,
        env=env,
        params={
            "tool_name": tool_name,
            "tool_arguments": {"status": "available"},
        },
    )
    call_payload = extract_result_payload(call_response)
    text = call_payload["content"][0]["text"]
    if '"status": "available"' not in text:
        raise AssertionError(json.dumps(call_response, indent=2))


asyncio.run(main())
PY
  )
}

start_streamable_http_server() {
  local output_dir="$1"
  local log_file="${TMP_ROOT}/generated-http.log"

  (
    cd "$output_dir"
    npm start >"$log_file" 2>&1
  ) &
  PIDS+=("$!")

  wait_for_http_status "http://${HTTP_HOST}:${HTTP_PORT}${MCP_ENDPOINT}" 400
}

run_streamable_http_assertions() {
  (
    cd "$REPO_ROOT"
    UV_CACHE_DIR="$UV_CACHE_DIR" uv run python - \
      "http://${HTTP_HOST}:${HTTP_PORT}${MCP_ENDPOINT}" \
      "$TOOL_NAME" <<'PY'
import asyncio
import json
import sys

from openapi_to_mcp.adapters.testing.server_tester import execute_mcp_server


def extract_result_payload(response: dict[str, object]) -> dict[str, object]:
    result = response.get("result")
    if isinstance(result, dict):
        return result
    return response


async def main() -> None:
    endpoint_url = sys.argv[1]
    tool_name = sys.argv[2]

    list_response = await execute_mcp_server(
        transport="streamable-http",
        method="list",
        req_id=1,
        endpoint_url=endpoint_url,
    )
    list_payload = extract_result_payload(list_response)
    tool_names = [tool["name"] for tool in list_payload["tools"]]
    if tool_name not in tool_names:
        raise AssertionError(f"Missing tool in streamable-http list response: {tool_names}")

    call_response = await execute_mcp_server(
        transport="streamable-http",
        method="call",
        req_id=2,
        endpoint_url=endpoint_url,
        params={
            "tool_name": tool_name,
            "tool_arguments": {"status": "available"},
        },
    )
    call_payload = extract_result_payload(call_response)
    text = call_payload["content"][0]["text"]
    if '"status": "available"' not in text:
        raise AssertionError(json.dumps(call_response, indent=2))


asyncio.run(main())
PY
  )
}

trap 'exit 1' INT TERM
trap cleanup EXIT

main() {
  ensure_command uv
  ensure_command npm
  ensure_command node
  ensure_command curl

  mkdir -p "$TMP_ROOT"

  echo "Starting mock target API on ${TARGET_API_BASE_URL}"
  (
    cd "$REPO_ROOT"
    UV_CACHE_DIR="$UV_CACHE_DIR" uv run python scripts/mock_target_api.py \
      --host "$MOCK_API_HOST" \
      --port "$MOCK_API_PORT"
  ) >"${TMP_ROOT}/mock-target-api.log" 2>&1 &
  PIDS+=("$!")

  wait_for_http_status "http://${MOCK_API_HOST}:${MOCK_API_PORT}/health" 200

  echo "Generating and validating stdio server"
  generate_server "$STDIO_OUTPUT_DIR" "stdio"
  build_generated_server "$STDIO_OUTPUT_DIR"
  run_stdio_assertions "$STDIO_OUTPUT_DIR"

  echo "Generating and validating streamable-http server"
  generate_server "$HTTP_OUTPUT_DIR" "streamable-http"
  build_generated_server "$HTTP_OUTPUT_DIR"
  start_streamable_http_server "$HTTP_OUTPUT_DIR"
  run_streamable_http_assertions

  echo "Generated-server E2E passed"
}

main "$@"
