"""Configuration management commands."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated

import typer
import yaml

from gobbler_cli.output import print_error, print_success

app = typer.Typer(help="View and manage Gobbler configuration")


@app.command("get")
def get_config(
    key: Annotated[
        str | None,
        typer.Argument(help="Config key using dot notation (e.g., 'output.default_directory')"),
    ] = None,
    output_format: Annotated[
        str,
        typer.Option("--format", "-f", help="Output format: text, json, yaml"),
    ] = "text",
) -> None:
    """Get configuration value(s).

    If no key is provided, shows all configuration.

    Examples:
        gobbler config get output.default_directory
        gobbler config get whisper.model
        gobbler config get providers.youtube.default
        gobbler config get  # Show all config
        gobbler config get --format json  # All config as JSON
    """
    from gobbler_mcp.config import get_config

    config = get_config()

    if key is None:
        # Show all config
        value = config.data
    else:
        # Use a sentinel to distinguish between "key not found" and "value is None"
        sentinel = object()
        value = config.get(key, sentinel)
        if value is sentinel:
            print_error(f"Configuration key '{key}' not found")
            raise typer.Exit(1)

    # Format output
    if output_format == "json":
        typer.echo(json.dumps(value, indent=2, default=str))
    elif output_format == "yaml":
        typer.echo(yaml.dump(value, default_flow_style=False))
    else:
        # Text format - simple for single values, structured for dicts
        if isinstance(value, dict):
            typer.echo(yaml.dump(value, default_flow_style=False))
        else:
            typer.echo(value)


@app.command("path")
def config_path() -> None:
    """Show the configuration file path.

    Examples:
        gobbler config path
    """
    from gobbler_mcp.config import get_config

    config = get_config()
    typer.echo(config.config_path)

    if config.config_path.exists():
        print_success("Config file exists")
    else:
        typer.echo("Config file does not exist (using defaults)")


@app.command("show")
def show_config(
    output_format: Annotated[
        str,
        typer.Option("--format", "-f", help="Output format: yaml, json"),
    ] = "yaml",
) -> None:
    """Show all configuration (alias for 'gobbler config get').

    Examples:
        gobbler config show
        gobbler config show --format json
    """
    from gobbler_mcp.config import get_config

    config = get_config()

    if output_format == "json":
        typer.echo(json.dumps(config.data, indent=2, default=str))
    else:
        typer.echo(yaml.dump(config.data, default_flow_style=False))


@app.command("init")
def init_config(
    force: Annotated[
        bool,
        typer.Option("--force", "-f", help="Overwrite existing config file"),
    ] = False,
) -> None:
    """Create a default configuration file.

    Creates ~/.config/gobbler/config.yml with example settings.

    Examples:
        gobbler config init
        gobbler config init --force  # Overwrite existing
    """
    config_dir = Path.home() / ".config" / "gobbler"
    config_path = config_dir / "config.yml"

    if config_path.exists() and not force:
        print_error(f"Config file already exists at {config_path}")
        typer.echo("Use --force to overwrite")
        raise typer.Exit(1)

    # Create directory if needed
    config_dir.mkdir(parents=True, exist_ok=True)

    # Read example config from package
    example_config = (
        Path(__file__).parent.parent.parent.parent.parent / "config" / "config.example.yml"
    )

    if example_config.exists():
        config_content = example_config.read_text()
    else:
        # Fallback minimal config
        config_content = """\
# Gobbler Configuration
# See https://github.com/your-repo/gobbler for full options

output:
  default_format: frontmatter
  timestamp_format: iso8601
  # default_directory: ~/Documents/Gobbler  # Uncomment to set default save location

whisper:
  model: small
  language: auto
"""

    config_path.write_text(config_content)
    print_success(f"Created config file at {config_path}")
