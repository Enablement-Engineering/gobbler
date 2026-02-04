"""Explain command for diagnosing Gobbler errors and issues."""

from __future__ import annotations

import json
from typing import Annotated

import typer

from gobbler_cli.knowledge import (
    ERROR_KNOWLEDGE_BASE,
    FIX_TEXT_TRUNCATE_LEN,
    MAX_SOLUTIONS_SHOWN,
    find_solutions,
)
from gobbler_cli.output import console

app = typer.Typer(help="Diagnose errors and get solutions")


@app.callback(invoke_without_command=True)
def explain(  # noqa: C901, PLR0912, PLR0915
    ctx: typer.Context,
    error_text: Annotated[
        str | None,
        typer.Argument(help="Error message or description to diagnose"),
    ] = None,
    json_output: Annotated[
        bool,
        typer.Option("--json", "-j", help="Output as JSON"),
    ] = False,
    list_all: Annotated[
        bool,
        typer.Option("--list", "-l", help="List all known error patterns"),
    ] = False,
) -> None:
    """Diagnose Gobbler errors and get solutions.

    Provide an error message or description, and get actionable solutions.

    Examples:
        gobbler explain "connection refused port 5001"
        gobbler explain "youtube rate limit"
        gobbler explain "ffmpeg not found"
        gobbler explain --list
    """
    if ctx.invoked_subcommand is not None:
        return

    if list_all:
        # List all known error patterns
        if json_output:
            all_errors = [
                {
                    "title": sol.title,
                    "keywords": sol.keywords,
                    "fix": sol.fix,
                }
                for sol in ERROR_KNOWLEDGE_BASE
            ]
            typer.echo(json.dumps(all_errors, indent=2))
        else:
            console.print()
            console.print("[bold]Known Error Patterns[/bold]")
            console.print("═" * 50)
            for sol in ERROR_KNOWLEDGE_BASE:
                console.print(f"\n[bold]{sol.title}[/bold]")
                console.print(f"  Keywords: {', '.join(sol.keywords[:4])}")
                console.print(
                    f"  Fix: [dim]{sol.fix[:FIX_TEXT_TRUNCATE_LEN]}...[/dim]"
                    if len(sol.fix) > FIX_TEXT_TRUNCATE_LEN
                    else f"  Fix: [dim]{sol.fix}[/dim]"
                )
            console.print()
        return

    if not error_text:
        console.print("[yellow]Provide an error message to diagnose.[/yellow]")
        console.print('Example: gobbler explain "connection refused port 5001"')
        console.print("Or use: gobbler explain --list")
        raise typer.Exit(1)

    solutions = find_solutions(error_text)

    if not solutions:
        if json_output:
            typer.echo(
                json.dumps(
                    {
                        "matches": [],
                        "suggestion": "Try 'gobbler explain --list' to see known errors",
                    }
                )
            )
        else:
            console.print(f"[yellow]No matching solutions found for:[/yellow] {error_text}")
            console.print()
            console.print("Suggestions:")
            console.print("  • Run [bold]gobbler status[/bold] to check service health")
            console.print("  • Run [bold]gobbler explain --list[/bold] to see known errors")
            console.print("  • Check logs: [dim]docker logs gobbler-docling --tail 50[/dim]")
        raise typer.Exit(1)

    if json_output:
        result = {
            "query": error_text,
            "matches": [
                {
                    "title": sol.title,
                    "description": sol.description,
                    "fix": sol.fix,
                    "verify": sol.verify,
                    "docs": sol.docs,
                }
                for sol in solutions[:3]
            ],
        }
        typer.echo(json.dumps(result, indent=2))
    else:
        console.print()
        console.print(f"[bold]Diagnosing:[/bold] {error_text}")
        console.print("═" * 50)

        for i, sol in enumerate(solutions[:3], 1):
            if i > 1:
                console.print()
                console.print("[dim]─" * 40 + "[/dim]")

            console.print()
            console.print(f"[bold red]#{i} {sol.title}[/bold red]")
            console.print()
            console.print(f"[bold]Issue:[/bold] {sol.description}")
            console.print()
            console.print("[bold green]Fix:[/bold green]")
            console.print(f"  {sol.fix}")

            if sol.verify:
                console.print()
                console.print("[bold blue]Verify:[/bold blue]")
                console.print(f"  {sol.verify}")

            if sol.docs:
                console.print()
                console.print(f"[dim]Docs: {sol.docs}[/dim]")

        if len(solutions) > MAX_SOLUTIONS_SHOWN:
            console.print()
            remaining = len(solutions) - MAX_SOLUTIONS_SHOWN
            console.print(f"[dim]... and {remaining} more possible matches[/dim]")

        console.print()
