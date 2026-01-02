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
        typer.Argument(help="Shell to generate completion for (bash, zsh, fish, or powershell)"),
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
    import click
    from typer.main import get_command

    click_app = get_command(app)

    # Use click-shell-completion for generating completion scripts
    try:
        if shell == "bash":
            from click.shell_completion import BashComplete

            complete = BashComplete(click_app, {}, "gobbler", "_GOBBLER_COMPLETE")
            completion_script = complete.source()
        elif shell == "zsh":
            from click.shell_completion import ZshComplete

            complete = ZshComplete(click_app, {}, "gobbler", "_GOBBLER_COMPLETE")
            completion_script = complete.source()
        elif shell == "fish":
            from click.shell_completion import FishComplete

            complete = FishComplete(click_app, {}, "gobbler", "_GOBBLER_COMPLETE")
            completion_script = complete.source()
        elif shell == "powershell":
            typer.echo(
                "PowerShell completion not supported in this version. Use --install-completion instead.",
                err=True,
            )
            raise typer.Exit(1)
        else:
            typer.echo(f"Unsupported shell: {shell}", err=True)
            raise typer.Exit(1)

        typer.echo(completion_script)
    except Exception as e:
        typer.echo(f"Error generating completion script: {e}", err=True)
        typer.echo("Try using 'gobbler --install-completion' instead.", err=True)
        raise typer.Exit(1)


def cli() -> None:
    """Entry point for the CLI."""
    # Import command modules here to register them
    from gobbler_cli.commands import (
        batch,
        browser,
        claude,
        convert,
        daemon,
        jobs,
        notebooklm,
        relay,
    )

    # Add command groups
    app.add_typer(convert.app, name="convert", help="Convert individual content items")
    app.add_typer(batch.app, name="batch", help="Batch processing operations")
    app.add_typer(daemon.app, name="daemon", help="Daemon management")
    app.add_typer(jobs.app, name="jobs", help="Job management")
    app.add_typer(browser.app, name="browser", help="Browser extension automation")
    app.add_typer(notebooklm.app, name="notebooklm", help="NotebookLM integration")
    app.add_typer(claude.app, name="claude", help="Claude.ai integration")
    app.add_typer(relay.app, name="relay", help="Browser relay server management")

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
