"""Output formatting utilities for the Gobbler CLI."""

from __future__ import annotations

import json
import sys
from enum import Enum
from pathlib import Path
from typing import Any

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
    output_path: Path | None = None,
    output_format: OutputFormat = OutputFormat.MARKDOWN,  # noqa: ARG001
) -> None:
    """Write content to file or stdout.

    Args:
        content: The content to write
        output_path: Optional file path to write to (stdout if None)
        output_format: Output format (only used for display, not file writing)
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
    output_path: Path | None = None,
) -> None:
    """Write JSON data to file or stdout.

    Args:
        data: Dictionary to serialize as JSON
        output_path: Optional file path to write to (stdout if None)
    """
    json_str = json.dumps(data, indent=2, ensure_ascii=False)
    write_output(json_str, output_path, OutputFormat.JSON)


def format_json_success(
    markdown: str,
    metadata: dict[str, Any],
    source: str | None = None,
) -> dict[str, Any]:
    """Format a successful conversion result as JSON.

    Args:
        markdown: The converted markdown content
        metadata: Metadata from the converter
        source: Optional source identifier (URL, file path, etc.)

    Returns:
        Standardized JSON response dict
    """
    response: dict[str, Any] = {
        "success": True,
        "markdown": markdown,
        "metadata": metadata,
    }
    if source:
        response["metadata"]["source"] = source
    return response


def format_json_error(
    error: str,
    error_code: str = "CONVERSION_ERROR",
    source: str | None = None,
) -> dict[str, Any]:
    """Format an error result as JSON.

    Args:
        error: Error message
        error_code: Error code identifier
        source: Optional source identifier

    Returns:
        Standardized JSON error response dict
    """
    response: dict[str, Any] = {
        "success": False,
        "error": error,
        "error_code": error_code,
    }
    if source:
        response["source"] = source
    return response


def write_json_result(
    result: dict[str, Any],
    output_path: Path | None = None,
) -> None:
    """Write a JSON result to file or stdout without decoration.

    Unlike write_output, this doesn't add any status messages.
    Suitable for piping to other tools.

    Args:
        result: Dictionary to serialize as JSON
        output_path: Optional file path to write to (stdout if None)
    """
    json_str = json.dumps(result, indent=2, ensure_ascii=False)
    if output_path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json_str, encoding="utf-8")
    else:
        sys.stdout.write(json_str)
        sys.stdout.write("\n")


def print_error(message: str) -> None:
    """Print an error message to stderr."""
    error_console.print(f"[red]Error:[/red] {message}")


def print_success(message: str) -> None:
    """Print a success message."""
    console.print(f"[green]✓[/green] {message}")


def print_info(message: str) -> None:
    """Print an info message."""
    console.print(f"[blue]i[/blue] {message}")


def print_warning(message: str) -> None:
    """Print a warning message."""
    console.print(f"[yellow]⚠[/yellow] {message}")


def create_table(
    title: str,
    columns: list[str],
    rows: list[list[str]],
) -> Table:
    """Create a rich table for display.

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
    """Print a formatted table.

    Args:
        title: Table title
        columns: Column headers
        rows: List of row data
    """
    table = create_table(title, columns, rows)
    console.print(table)
