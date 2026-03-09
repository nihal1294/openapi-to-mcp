from click.testing import CliRunner

from openapi_to_mcp.cli import cli


def test_root_help_lists_commands() -> None:
    runner = CliRunner()

    result = runner.invoke(cli, ["--help"])

    assert result.exit_code == 0
    assert "generate" in result.output
    assert "run" in result.output
    assert "test-server" in result.output


def test_generate_help_lists_required_options() -> None:
    runner = CliRunner()

    result = runner.invoke(cli, ["generate", "--help"])

    assert result.exit_code == 0
    assert "--openapi-json" in result.output
    assert "--output-dir" in result.output
    assert "--runtime-validation" in result.output


def test_run_help_lists_runtime_options() -> None:
    runner = CliRunner()

    result = runner.invoke(cli, ["run", "--help"])

    assert result.exit_code == 0
    assert "--runtime-validation" in result.output
    assert "--origin-allowlist" in result.output
    assert "--max-concurrency" in result.output
