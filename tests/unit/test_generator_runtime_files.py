from pathlib import Path
from unittest.mock import MagicMock

import jinja2

from openapi_to_mcp.adapters.generator import Generator
from tests.utils import setup_path_mocks


def test_generator_generate_files_success(mocker: MagicMock) -> None:
    output_dir = "fake/output"
    context = {"server_name": "test-server", "tools": [], "transport": "stdio"}
    path_mocks = setup_path_mocks(mocker, output_dir)

    def path_side_effect(arg: str) -> MagicMock:
        if arg == output_dir:
            return path_mocks["output_path"]
        if arg == __file__ or "generator.py" in str(arg):
            return path_mocks["file_path"]
        return MagicMock(spec=Path)

    path_mocks["path_class"].side_effect = path_side_effect
    mock_parent_parent = MagicMock(spec=Path, name="mock_parent_parent")
    path_mocks["file_path"].parent.parent = mock_parent_parent
    mock_parent_parent.__truediv__.return_value = path_mocks["template_dir"]

    gen = Generator(output_dir=output_dir, context=context)
    mock_env = MagicMock(spec=jinja2.Environment)
    mocker.patch.object(
        gen, "_setup_environment", side_effect=lambda: setattr(gen, "env", mock_env)
    )
    mocker.patch.object(gen, "_ensure_output_directories")
    mock_render = mocker.patch.object(gen, "_render_and_write")
    mock_render_if_missing = mocker.patch.object(gen, "_render_if_missing")

    output_files = _output_files()
    path_mocks["output_path"].__truediv__.side_effect = lambda arg: output_files.get(
        arg, MagicMock(spec=Path)
    )
    output_files["src"].__truediv__.side_effect = lambda arg: output_files.get(
        f"src/{arg}", MagicMock(spec=Path)
    )
    output_files["src/runtime"].__truediv__.side_effect = lambda arg: output_files.get(
        f"src/runtime/{arg}", MagicMock(spec=Path)
    )
    output_files["src/custom"].__truediv__.side_effect = lambda arg: output_files.get(
        f"src/custom/{arg}", MagicMock(spec=Path)
    )

    gen.generate_files()

    expected_calls = [
        ("package.json.j2", output_files["package.json"]),
        ("tsconfig.json.j2", output_files["tsconfig.json"]),
        ("src/server.ts.j2", output_files["src/server.ts"]),
        ("README.md.j2", output_files["README.md"]),
        (".env.example.j2", output_files[".env.example"]),
        ("src/index.ts.j2", output_files["src/index.ts"]),
        ("src/runtime/audit.ts.j2", output_files["src/runtime/audit.ts"]),
        (
            "src/runtime/request_context.ts.j2",
            output_files["src/runtime/request_context.ts"],
        ),
        ("src/runtime/auth.ts.j2", output_files["src/runtime/auth.ts"]),
        ("src/runtime/cache.ts.j2", output_files["src/runtime/cache.ts"]),
        (
            "src/runtime/circuit_breaker.ts.j2",
            output_files["src/runtime/circuit_breaker.ts"],
        ),
        ("src/runtime/config.ts.j2", output_files["src/runtime/config.ts"]),
        ("src/runtime/errors.ts.j2", output_files["src/runtime/errors.ts"]),
        ("src/runtime/executor.ts.j2", output_files["src/runtime/executor.ts"]),
        (
            "src/runtime/executor_support.ts.j2",
            output_files["src/runtime/executor_support.ts"],
        ),
        ("src/runtime/generated.ts.j2", output_files["src/runtime/generated.ts"]),
        (
            "src/runtime/http_transport.ts.j2",
            output_files["src/runtime/http_transport.ts"],
        ),
        ("src/runtime/limiter.ts.j2", output_files["src/runtime/limiter.ts"]),
        (
            "src/runtime/observability.ts.j2",
            output_files["src/runtime/observability.ts"],
        ),
        (
            "src/runtime/performance_preset.ts.j2",
            output_files["src/runtime/performance_preset.ts"],
        ),
        ("src/runtime/rate_limit.ts.j2", output_files["src/runtime/rate_limit.ts"]),
        ("src/runtime/resilience.ts.j2", output_files["src/runtime/resilience.ts"]),
        ("src/runtime/retry.ts.j2", output_files["src/runtime/retry.ts"]),
        ("src/runtime/request.ts.j2", output_files["src/runtime/request.ts"]),
        ("src/runtime/redaction.ts.j2", output_files["src/runtime/redaction.ts"]),
        ("src/runtime/response.ts.j2", output_files["src/runtime/response.ts"]),
        (
            "src/runtime/serialization.ts.j2",
            output_files["src/runtime/serialization.ts"],
        ),
        ("src/runtime/tool_access.ts.j2", output_files["src/runtime/tool_access.ts"]),
        ("src/runtime/validation.ts.j2", output_files["src/runtime/validation.ts"]),
        ("src/transport_stdio.ts.j2", output_files["src/transport.ts"]),
    ]
    assert mock_render.call_count == len(expected_calls)
    mock_render.assert_has_calls(
        [mocker.call(name, path) for name, path in expected_calls]
    )
    mock_render_if_missing.assert_called_once_with(
        "src/custom/tools.ts.j2", output_files["src/custom/tools.ts"]
    )


def _output_files() -> dict[str, MagicMock]:
    return {
        "src": MagicMock(spec=Path, name="src"),
        "src/runtime": MagicMock(spec=Path, name="runtime_dir"),
        "src/custom": MagicMock(spec=Path, name="custom_dir"),
        "package.json": MagicMock(spec=Path, name="package_json"),
        "tsconfig.json": MagicMock(spec=Path, name="tsconfig"),
        "README.md": MagicMock(spec=Path, name="readme"),
        ".env.example": MagicMock(spec=Path, name="env_example"),
        "src/index.ts": MagicMock(spec=Path, name="index_ts"),
        "src/server.ts": MagicMock(spec=Path, name="server_ts"),
        "src/custom/tools.ts": MagicMock(spec=Path, name="custom_tools"),
        "src/runtime/audit.ts": MagicMock(spec=Path, name="runtime_audit"),
        "src/runtime/request_context.ts": MagicMock(
            spec=Path, name="runtime_request_context"
        ),
        "src/runtime/auth.ts": MagicMock(spec=Path, name="runtime_auth"),
        "src/runtime/cache.ts": MagicMock(spec=Path, name="runtime_cache"),
        "src/runtime/circuit_breaker.ts": MagicMock(
            spec=Path, name="runtime_circuit_breaker"
        ),
        "src/runtime/config.ts": MagicMock(spec=Path, name="runtime_config"),
        "src/runtime/errors.ts": MagicMock(spec=Path, name="runtime_errors"),
        "src/runtime/executor.ts": MagicMock(spec=Path, name="runtime_executor"),
        "src/runtime/executor_support.ts": MagicMock(
            spec=Path, name="runtime_executor_support"
        ),
        "src/runtime/generated.ts": MagicMock(spec=Path, name="runtime_generated"),
        "src/runtime/http_transport.ts": MagicMock(
            spec=Path, name="runtime_http_transport"
        ),
        "src/runtime/limiter.ts": MagicMock(spec=Path, name="runtime_limiter"),
        "src/runtime/observability.ts": MagicMock(spec=Path, name="observability"),
        "src/runtime/performance_preset.ts": MagicMock(
            spec=Path, name="performance_preset"
        ),
        "src/runtime/rate_limit.ts": MagicMock(spec=Path, name="runtime_rate_limit"),
        "src/runtime/resilience.ts": MagicMock(spec=Path, name="runtime_resilience"),
        "src/runtime/retry.ts": MagicMock(spec=Path, name="runtime_retry"),
        "src/runtime/request.ts": MagicMock(spec=Path, name="runtime_request"),
        "src/runtime/redaction.ts": MagicMock(spec=Path, name="runtime_redaction"),
        "src/runtime/response.ts": MagicMock(spec=Path, name="runtime_response"),
        "src/runtime/serialization.ts": MagicMock(spec=Path, name="serialization"),
        "src/runtime/tool_access.ts": MagicMock(spec=Path, name="tool_access"),
        "src/runtime/validation.ts": MagicMock(spec=Path, name="validation"),
        "src/transport.ts": MagicMock(spec=Path, name="transport"),
    }
