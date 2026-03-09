import rich_click as click

from openapi_to_mcp.commands import diff, doctor, generate, run, test_server
from openapi_to_mcp.common import configure_logger


def _configure_rich_click() -> None:
    click.rich_click.TEXT_MARKUP = "rich"
    click.rich_click.SHOW_ARGUMENTS = True
    click.rich_click.GROUP_ARGUMENTS_OPTIONS = True
    click.rich_click.OPTIONS_TABLE_HELP_SECTIONS = [
        "help",
        "metavar",
        "envvar",
        "default",
        "required",
    ]
    click.rich_click.STYLE_COMMAND = "bold yellow"
    click.rich_click.STYLE_OPTION = "bold cyan"
    click.rich_click.STYLE_SWITCH = "bold cyan"
    click.rich_click.STYLE_METAVAR = "bold white"
    click.rich_click.STYLE_OPTION_HELP = "white"
    click.rich_click.STYLE_HEADER_TEXT = "bold white"
    click.rich_click.STYLE_USAGE = "bold green"
    click.rich_click.STYLE_ERRORS_SUGGESTION = "bold red"


_configure_rich_click()


@click.group(context_settings={"help_option_names": ["-h", "--help"]})
def cli() -> None:
    """A CLI tool to diagnose, diff, generate, run, and test MCP servers from OpenAPI specs."""
    configure_logger()


cli.add_command(generate)
cli.add_command(run)
cli.add_command(test_server)
cli.add_command(doctor)
cli.add_command(diff)


if __name__ == "__main__":
    cli()
