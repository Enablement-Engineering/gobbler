"""Explain command for diagnosing Gobbler errors and issues."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Annotated

import typer

from gobbler_cli.output import console

app = typer.Typer(help="Diagnose errors and get solutions")


@dataclass
class ErrorSolution:
    """A documented error pattern with solution."""
    
    keywords: list[str]
    title: str
    description: str
    fix: str
    verify: str | None = None
    docs: str | None = None


# Knowledge base of common errors and solutions
ERROR_KNOWLEDGE_BASE: list[ErrorSolution] = [
    # Docling / Document conversion errors
    ErrorSolution(
        keywords=["connection refused", "5001", "docling", "document"],
        title="Docling service not running",
        description="The Docling Docker container is not running or not accessible on port 5001.",
        fix="cd ~/Projects/gobbler && docker compose up -d docling",
        verify="curl -s http://localhost:5001/health && echo ' OK'",
        docs="https://github.com/Enablement-Engineering/gobbler#document-conversion",
    ),
    ErrorSolution(
        keywords=["server disconnected", "memory", "oom", "killed"],
        title="Service crashed (likely out of memory)",
        description="The Docker service crashed, usually due to insufficient memory during OCR.",
        fix="Try with --no-ocr flag, or increase Docker memory in docker-compose.yml",
        verify="docker ps --filter 'name=gobbler' --format '{{.Names}}: {{.Status}}'",
    ),
    ErrorSolution(
        keywords=["ocr", "failed", "scanned"],
        title="OCR processing failed",
        description="OCR failed on a scanned document. This may be due to memory limits or corrupt files.",
        fix="gobbler document FILE --no-ocr (if digital PDF) or increase Docker memory",
        verify="docker logs gobbler-docling --tail 20",
    ),
    
    # Crawl4AI / Webpage errors  
    ErrorSolution(
        keywords=["connection refused", "11235", "crawl4ai", "webpage"],
        title="Crawl4AI service not running",
        description="The Crawl4AI Docker container is not running or not accessible on port 11235.",
        fix="cd ~/Projects/gobbler && docker compose up -d crawl4ai",
        verify="curl -s http://localhost:11235/health && echo ' OK'",
        docs="https://github.com/Enablement-Engineering/gobbler#web-page-conversion",
    ),
    ErrorSolution(
        keywords=["timeout", "webpage", "crawl"],
        title="Web page request timed out",
        description="The page took too long to load. May be slow server or complex JavaScript.",
        fix="Increase timeout: gobbler webpage URL --timeout 60",
        verify="curl -I URL (check if site is accessible)",
    ),
    ErrorSolution(
        keywords=["blocked", "forbidden", "403", "captcha"],
        title="Website blocking automated access",
        description="The website detected and blocked the automated request.",
        fix="Try using a proxy service in ~/.config/gobbler/config.yml or use the browser extension",
        docs="https://github.com/Enablement-Engineering/gobbler#browser-extension",
    ),
    
    # YouTube errors
    ErrorSolution(
        keywords=["ip blocked", "youtube", "rate limit", "too many"],
        title="YouTube rate limiting / IP blocked",
        description="YouTube is blocking requests from your IP due to too many requests.",
        fix="Configure a Webshare proxy in ~/.config/gobbler/config.yml or wait 10-15 minutes",
        verify="gobbler status --json | grep -A5 proxy",
    ),
    ErrorSolution(
        keywords=["no transcript", "captions", "subtitles", "disabled"],
        title="Video has no transcripts available",
        description="This YouTube video doesn't have captions/subtitles available.",
        fix="Check if the video has captions on YouTube. Try --language auto",
        verify="Open video on YouTube and check if CC button is available",
    ),
    ErrorSolution(
        keywords=["video unavailable", "private", "removed"],
        title="Video not accessible",
        description="The video is private, removed, or region-blocked.",
        fix="Check if the video is accessible in your browser",
    ),
    
    # Audio / Whisper errors
    ErrorSolution(
        keywords=["ffmpeg", "not found", "command not found"],
        title="ffmpeg not installed",
        description="ffmpeg is required for audio/video processing but is not installed.",
        fix="brew install ffmpeg (macOS) or apt install ffmpeg (Linux)",
        verify="ffmpeg -version",
    ),
    ErrorSolution(
        keywords=["whisper", "model", "download", "huggingface"],
        title="Whisper model download issue",
        description="Failed to download or load the Whisper model from HuggingFace.",
        fix="Check internet connection. Try: export HF_TOKEN=your_token",
        verify="ls ~/.cache/huggingface/hub/ | grep whisper",
    ),
    ErrorSolution(
        keywords=["no speech", "silent", "empty"],
        title="No speech detected in audio",
        description="Whisper couldn't detect any speech in the audio file.",
        fix="Check if the audio file actually contains speech. Try playing it locally.",
        verify="ffprobe FILE (check audio stream info)",
    ),
    
    # Docker errors
    ErrorSolution(
        keywords=["docker", "daemon", "not running", "cannot connect"],
        title="Docker not running",
        description="Docker Desktop is not running or not accessible.",
        fix="Start Docker Desktop: open -a Docker (macOS) or systemctl start docker (Linux)",
        verify="docker info",
    ),
    ErrorSolution(
        keywords=["docker", "permission", "denied", "socket"],
        title="Docker permission denied",
        description="Your user doesn't have permission to access Docker.",
        fix="sudo usermod -aG docker $USER && newgrp docker",
        verify="docker ps",
    ),
    
    # General errors
    ErrorSolution(
        keywords=["file not found", "no such file"],
        title="File not found",
        description="The specified file path doesn't exist.",
        fix="Check the file path and ensure it exists: ls -la FILE",
        verify="ls -la FILE",
    ),
    ErrorSolution(
        keywords=["permission denied", "access denied"],
        title="Permission denied",
        description="You don't have permission to access this file or resource.",
        fix="Check file permissions: ls -la FILE or run with appropriate permissions",
    ),
    ErrorSolution(
        keywords=["unsupported format", "invalid format"],
        title="Unsupported file format",
        description="The file format is not supported by Gobbler.",
        fix="Check supported formats: PDF, DOCX, PPTX, XLSX for documents; MP3, WAV, M4A, MP4 for audio",
        docs="https://github.com/Enablement-Engineering/gobbler#features",
    ),
]


def find_solutions(error_text: str) -> list[ErrorSolution]:
    """Find matching solutions for an error message.
    
    Args:
        error_text: The error message or description to diagnose
        
    Returns:
        List of matching ErrorSolution objects, sorted by relevance
    """
    error_lower = error_text.lower()
    matches: list[tuple[int, ErrorSolution]] = []
    
    for solution in ERROR_KNOWLEDGE_BASE:
        # Count keyword matches
        match_count = sum(1 for kw in solution.keywords if kw in error_lower)
        if match_count > 0:
            matches.append((match_count, solution))
    
    # Sort by match count (descending)
    matches.sort(key=lambda x: x[0], reverse=True)
    
    return [sol for _, sol in matches]


@app.callback(invoke_without_command=True)
def explain(
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
                console.print(f"  Fix: [dim]{sol.fix[:60]}...[/dim]" if len(sol.fix) > 60 else f"  Fix: [dim]{sol.fix}[/dim]")
            console.print()
        return
    
    if not error_text:
        console.print("[yellow]Provide an error message to diagnose.[/yellow]")
        console.print("Example: gobbler explain \"connection refused port 5001\"")
        console.print("Or use: gobbler explain --list")
        raise typer.Exit(1)
    
    solutions = find_solutions(error_text)
    
    if not solutions:
        if json_output:
            typer.echo(json.dumps({"matches": [], "suggestion": "Try 'gobbler explain --list' to see known errors"}))
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
            console.print(f"[bold green]Fix:[/bold green]")
            console.print(f"  {sol.fix}")
            
            if sol.verify:
                console.print()
                console.print(f"[bold blue]Verify:[/bold blue]")
                console.print(f"  {sol.verify}")
            
            if sol.docs:
                console.print()
                console.print(f"[dim]Docs: {sol.docs}[/dim]")
        
        if len(solutions) > 3:
            console.print()
            console.print(f"[dim]... and {len(solutions) - 3} more possible matches[/dim]")
        
        console.print()
