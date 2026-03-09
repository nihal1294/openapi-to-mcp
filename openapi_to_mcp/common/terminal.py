"""Rich terminal helpers for user-facing CLI output."""

from __future__ import annotations

from typing import Any

from rich.console import Console
from rich.json import JSON
from rich.panel import Panel

_STDOUT = Console()
_STDERR = Console(stderr=True)


def print_json_panel(title: str, payload: dict[str, Any]) -> None:
    """Render JSON output in a readable panel."""
    _STDOUT.print(
        Panel(
            JSON.from_data(payload),
            border_style="cyan",
            title=title,
            title_align="left",
        )
    )


def print_section(title: str) -> None:
    """Render a short section heading."""
    _STDOUT.print(f"[bold cyan]{title}[/bold cyan]")


def _print_summary_panel(title: str, lines: list[str], *, border_style: str) -> None:
    """Render a summary panel with the requested border style."""
    _STDOUT.print(
        Panel.fit(
            "\n".join(lines),
            border_style=border_style,
            title=title,
            title_align="left",
        )
    )


def print_success_panel(title: str, lines: list[str]) -> None:
    """Render a success summary panel."""
    _print_summary_panel(title, lines, border_style="green")


def print_warning_panel(title: str, lines: list[str]) -> None:
    """Render a warning summary panel."""
    _print_summary_panel(title, lines, border_style="yellow")


def print_error_panel(title: str, lines: list[str]) -> None:
    """Render an error summary panel."""
    _print_summary_panel(title, lines, border_style="red")


def print_error(message: str) -> None:
    """Render a concise user-facing error."""
    _STDERR.print(f"[bold red]Error:[/bold red] {message}")
