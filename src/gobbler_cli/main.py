"""Main entry point for the Gobbler CLI."""

from __future__ import annotations

import typer
from typing_extensions import Annotated

from gobbler_cli import __version__

# Create the main app
app = typer.Typer(
    name="gobbler",
    help="Convert content (YouTube, audio, documents, web pages) to markdown",
    add_completion=True,
    no_args_is_help=True,
)


def version_callback(value: bool) -> None:
    """Print version and exit."""
    if value:
        typer.echo(f"gobbler version {__version__}")
        raise typer.Exit()


@app.callback()
def main(
    version: Annotated[
        bool,
        typer.Option("--version", "-v", help="Show version and exit", callback=version_callback),
    ] = False,
) -> None:
    """Gobbler CLI - Universal content conversion to markdown."""
    pass


@app.command()
def completion(
    shell: Annotated[
        str,
        typer.Argument(
            help="Shell to generate completion for (bash, zsh, fish, or powershell)"
        ),
    ] = "bash",
) -> None:
    """
    Generate shell completion script.

    Examples:
        # Bash
        gobbler completion bash > ~/.local/share/bash-completion/completions/gobbler

        # Zsh
        gobbler completion zsh > ~/.zsh/completion/_gobbler

        # Fish
        gobbler completion fish > ~/.config/fish/completions/gobbler.fish
    """
    from typer.main import get_command

    click_app = get_command(app)

    if shell == "bash":
        completion_script = click_app.get_completion_script("bash", "gobbler")
    elif shell == "zsh":
        completion_script = click_app.get_completion_script("zsh", "gobbler")
    elif shell == "fish":
        completion_script = click_app.get_completion_script("fish", "gobbler")
    elif shell == "powershell":
        completion_script = click_app.get_completion_script("powershell", "gobbler")
    else:
        typer.echo(f"Unsupported shell: {shell}", err=True)
        raise typer.Exit(1)

    typer.echo(completion_script)


def cli() -> None:
    """Entry point for the CLI."""
    # Import command modules here to register them
    from gobbler_cli.commands import batch, convert, daemon, jobs

    # Add command groups
    app.add_typer(convert.app, name="convert", help="Convert individual content items")
    app.add_typer(batch.app, name="batch", help="Batch processing operations")
    app.add_typer(daemon.app, name="daemon", help="Daemon management")
    app.add_typer(jobs.app, name="jobs", help="Job management")

    # Also register convert commands at the top level for convenience
    # This allows both "gobbler youtube URL" and "gobbler convert youtube URL"
    app.command("youtube", help="Convert YouTube video to markdown")(convert.youtube)
    app.command("audio", help="Transcribe audio file to markdown")(convert.audio)
    app.command("document", help="Convert document to markdown")(convert.document)
    app.command("webpage", help="Convert web page to markdown")(convert.webpage)

    # Run the app
    app()


if __name__ == "__main__":
    cli()
