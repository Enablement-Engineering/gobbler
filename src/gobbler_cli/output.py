"""Output formatting utilities for the Gobbler CLI."""

from __future__ import annotations

import json
import sys
from enum import Enum
from pathlib import Path
from typing import Any, Optional

from rich.console import Console
from rich.table import Table

console = Console()
error_console = Console(stderr=True)


class OutputFormat(str, Enum):
    """Supported output formats."""

    MARKDOWN = "markdown"
    JSON = "json"
    TABLE = "table"


def write_output(
    content: str,
    output_path: Optional[Path] = None,
    format: OutputFormat = OutputFormat.MARKDOWN,
) -> None:
    """
    Write content to file or stdout.

    Args:
        content: The content to write
        output_path: Optional file path to write to (stdout if None)
        format: Output format (only used for display, not file writing)
    """
    if output_path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(content, encoding="utf-8")
        console.print(f"[green]✓[/green] Written to {output_path}")
    else:
        # Write to stdout
        sys.stdout.write(content)
        if not content.endswith("\n"):
            sys.stdout.write("\n")


def write_json(
    data: dict[str, Any],
    output_path: Optional[Path] = None,
) -> None:
    """
    Write JSON data to file or stdout.

    Args:
        data: Dictionary to serialize as JSON
        output_path: Optional file path to write to (stdout if None)
    """
    json_str = json.dumps(data, indent=2, ensure_ascii=False)
    write_output(json_str, output_path, OutputFormat.JSON)


def print_error(message: str) -> None:
    """Print an error message to stderr."""
    error_console.print(f"[red]Error:[/red] {message}")


def print_success(message: str) -> None:
    """Print a success message."""
    console.print(f"[green]✓[/green] {message}")


def print_info(message: str) -> None:
    """Print an info message."""
    console.print(f"[blue]ℹ[/blue] {message}")


def print_warning(message: str) -> None:
    """Print a warning message."""
    console.print(f"[yellow]⚠[/yellow] {message}")


def create_table(
    title: str,
    columns: list[str],
    rows: list[list[str]],
) -> Table:
    """
    Create a rich table for display.

    Args:
        title: Table title
        columns: Column headers
        rows: List of row data

    Returns:
        A rich Table object
    """
    table = Table(title=title, show_header=True, header_style="bold magenta")

    for column in columns:
        table.add_column(column)

    for row in rows:
        table.add_row(*row)

    return table


def print_table(
    title: str,
    columns: list[str],
    rows: list[list[str]],
) -> None:
    """
    Print a formatted table.

    Args:
        title: Table title
        columns: Column headers
        rows: List of row data
    """
    table = create_table(title, columns, rows)
    console.print(table)
