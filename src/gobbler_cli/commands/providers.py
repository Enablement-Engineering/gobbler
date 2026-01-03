"""Provider management commands for listing and inspecting content providers."""

from __future__ import annotations

import json
from typing import Annotated

import typer

from gobbler_cli.output import (
    OutputFormat,
    console,
    print_error,
    print_info,
    print_table,
)

# Note: console is used for non-JSON output formatting

app = typer.Typer(help="Manage content conversion providers")


@app.command("list")
def list_providers(
    category: Annotated[
        str | None,
        typer.Option(
            "--category",
            "-c",
            help="Filter by category (transcription, document, webpage)",
        ),
    ] = None,
    output_format: Annotated[
        OutputFormat,
        typer.Option("--format", "-f", help="Output format"),
    ] = OutputFormat.MARKDOWN,
) -> None:
    """List available content providers.

    Shows all registered providers grouped by category, or filter by specific category.

    Examples:
        gobbler providers list
        gobbler providers list --category transcription
        gobbler providers list -c document --format json
    """
    # Defer heavy imports
    from gobbler_core.providers import ProviderRegistry  # noqa: PLC0415

    categories = [category] if category else ProviderRegistry.list_categories()

    if not categories:
        print_info("No providers registered")
        return

    # Validate category if specified
    if category and category not in ProviderRegistry.list_categories():
        valid_categories = ", ".join(ProviderRegistry.list_categories())
        print_error(f"Unknown category: {category}. Valid categories: {valid_categories}")
        raise typer.Exit(1)

    # Build data structure for output
    providers_data: list[dict[str, str]] = []
    for cat in sorted(categories):
        provider_names = ProviderRegistry.list_providers(cat)
        for name in sorted(provider_names):
            try:
                info = ProviderRegistry.get_provider_info(cat, name)
                description = info.get("doc", "No description").split("\n")[0].strip()
                # Truncate long descriptions
                max_description_length = 60
                if len(description) > max_description_length:
                    description = description[: max_description_length - 3] + "..."
                providers_data.append(
                    {
                        "category": cat,
                        "name": name,
                        "description": description,
                    }
                )
            except Exception:
                providers_data.append(
                    {
                        "category": cat,
                        "name": name,
                        "description": "Error loading provider info",
                    }
                )

    if not providers_data:
        print_info("No providers found")
        return

    if output_format == OutputFormat.JSON:
        typer.echo(json.dumps(providers_data, indent=2))
    else:
        # Table or Markdown output
        rows = [[p["category"], p["name"], p["description"]] for p in providers_data]
        title = f"Providers ({category})" if category else "All Providers"
        print_table(title, ["Category", "Name", "Description"], rows)


@app.command("info")
def info(
    category: Annotated[
        str,
        typer.Argument(help="Provider category (transcription, document, webpage)"),
    ],
    name: Annotated[
        str,
        typer.Argument(help="Provider name"),
    ],
    output_format: Annotated[
        OutputFormat,
        typer.Option("--format", "-f", help="Output format"),
    ] = OutputFormat.MARKDOWN,
) -> None:
    """Show detailed information about a provider.

    Examples:
        gobbler providers info transcription whisper-local
        gobbler providers info document docling --format json
    """
    # Defer heavy imports
    from gobbler_core.providers import ProviderNotFoundError, ProviderRegistry  # noqa: PLC0415

    try:
        provider_info = ProviderRegistry.get_provider_info(category, name)
    except ProviderNotFoundError as e:
        print_error(str(e))
        raise typer.Exit(1) from None

    if output_format == OutputFormat.JSON:
        typer.echo(json.dumps(provider_info, indent=2))
    else:
        # Markdown/Table output
        console.print(f"\n[bold]Provider: {name}[/bold]\n")
        console.print(f"  Category:    {provider_info['category']}")
        console.print(f"  Name:        {provider_info['name']}")
        console.print(f"  Class:       {provider_info['class']}")
        console.print(f"  Module:      {provider_info['module']}")
        console.print("\n[bold]Description:[/bold]\n")
        # Format docstring nicely
        doc = provider_info.get("doc", "No documentation available")
        for line in doc.split("\n"):
            console.print(f"  {line}")
        console.print()
