"""Doctor command for agent-friendly Gobbler diagnostics."""

from __future__ import annotations

import json
import platform
import shutil
import subprocess
import sys
from typing import Annotated, Any

import typer

from gobbler_cli import __version__
from gobbler_cli.output import console
from gobbler_core.config import Config, get_config
from gobbler_core.utils.redaction import redact_value

app = typer.Typer(help="Run agent-friendly diagnostics")

SERVICE_TIMEOUT_SECONDS = 1.0


def _run_command(args: list[str], timeout: float = 2.0) -> tuple[bool, str | None]:
    """Run a short local diagnostic command and return success plus output/error."""
    try:
        result = subprocess.run(
            args,
            capture_output=True,
            check=False,
            text=True,
            timeout=timeout,
        )
    except FileNotFoundError:
        return False, "not found"
    except subprocess.TimeoutExpired:
        return False, "timeout"
    except Exception as exc:
        return False, str(exc)

    output = (result.stdout or result.stderr).strip()
    if result.returncode == 0:
        return True, output.splitlines()[0] if output else None
    return False, output.splitlines()[0] if output else f"exit {result.returncode}"


def _tool_status(executable: str, version_args: list[str]) -> dict[str, Any]:
    """Return availability details for a local executable."""
    path = shutil.which(executable)
    status: dict[str, Any] = {
        "available": path is not None,
        "path": path,
    }
    if path is None:
        status["error"] = "not found on PATH"
        return status

    ok, output = _run_command(version_args)
    if ok:
        status["version"] = output
    elif output:
        status["version_error"] = output
    return status


def get_ffmpeg_status() -> dict[str, Any]:
    """Return ffmpeg availability details."""
    return _tool_status("ffmpeg", ["ffmpeg", "-version"])


def get_docker_status() -> dict[str, Any]:
    """Return Docker CLI and daemon availability details."""
    status = _tool_status("docker", ["docker", "--version"])
    if not status["available"]:
        status["daemon_available"] = False
        return status

    daemon_ok, daemon_output = _run_command(["docker", "info", "--format", "{{.ServerVersion}}"])
    status["daemon_available"] = daemon_ok
    if daemon_ok:
        status["daemon_version"] = daemon_output
    elif daemon_output:
        status["daemon_error"] = daemon_output
    return status


def _check_service_health(
    url: str,
    timeout: float = SERVICE_TIMEOUT_SECONDS,
) -> tuple[bool, str | None]:
    """Check a local HTTP service health endpoint without external network calls."""
    import httpx

    health_url = f"{url.rstrip('/')}/health"
    try:
        with httpx.Client(timeout=timeout) as client:
            response = client.get(health_url)
    except httpx.ConnectError:
        return False, "connection refused"
    except httpx.TimeoutException:
        return False, "timeout"
    except Exception as exc:
        return False, str(exc)

    if response.status_code == 200:  # noqa: PLR2004
        return True, None
    return False, f"HTTP {response.status_code}"


def _service_url(config: Config, service: str, default_port: int) -> str:
    """Build a service URL from config with sane defaults."""
    host = config.get(f"services.{service}.host", "localhost")
    port = config.get(f"services.{service}.port", default_port)
    return f"http://{host}:{port}"


def _collect_services(config: Config, ffmpeg: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
    """Collect conversion service readiness and suggested next actions."""
    next_actions: list[str] = []

    youtube_provider = config.get("providers.youtube.default", "youtube-transcript-api")
    audio_provider = config.get("providers.transcription.default", "whisper-local")
    audio_model = config.get(
        "providers.transcription.whisper-local.model",
        config.get("whisper.model", "small"),
    )

    services: dict[str, Any] = {
        "youtube": {
            "status": "ready",
            "provider": youtube_provider,
            "requires": [],
            "note": "No local service required.",
        },
        "audio": {
            "status": "ready" if ffmpeg["available"] else "unavailable",
            "provider": audio_provider,
            "model": audio_model,
            "requires": ["ffmpeg"],
        },
    }

    if not ffmpeg["available"]:
        services["audio"]["error"] = "ffmpeg not found on PATH"
        services["audio"]["fix"] = "Install ffmpeg and retry audio conversion."
        next_actions.append("Install ffmpeg before using `gobbler audio`.")

    docling_url = _service_url(config, "docling", 5001)
    doc_healthy, doc_error = _check_service_health(docling_url)
    services["document"] = {
        "status": "ready" if doc_healthy else "unavailable",
        "provider": "docling",
        "url": docling_url,
        "requires": ["docker", "docling service"],
    }
    if not doc_healthy:
        services["document"].update(
            {
                "error": doc_error,
                "fix": "Run `docker compose up -d docling` or `make start-docker`.",
            }
        )
        next_actions.append("Start Docling before using `gobbler document`.")

    crawl4ai_url = _service_url(config, "crawl4ai", 11235)
    web_healthy, web_error = _check_service_health(crawl4ai_url)
    services["webpage"] = {
        "status": "ready" if web_healthy else "unavailable",
        "provider": "crawl4ai",
        "url": crawl4ai_url,
        "requires": ["docker", "crawl4ai service"],
    }
    if not web_healthy:
        services["webpage"].update(
            {
                "error": web_error,
                "fix": "Run `docker compose up -d crawl4ai` or `make start-docker`.",
            }
        )
        next_actions.append("Start Crawl4AI before using `gobbler webpage`.")

    return services, next_actions


def collect_doctor_report() -> dict[str, Any]:
    """Collect a JSON-serializable diagnostic report for agents and scripts."""
    config = get_config()
    ffmpeg = get_ffmpeg_status()
    docker = get_docker_status()
    services, next_actions = _collect_services(config, ffmpeg)

    if docker["available"] and not docker.get("daemon_available"):
        next_actions.append("Start the Docker daemon before using document or webpage conversion.")
    elif not docker["available"]:
        next_actions.append("Install Docker before using document or webpage conversion.")

    unavailable = [name for name, data in services.items() if data["status"] != "ready"]
    status = "ready" if not unavailable else "degraded"
    if services["youtube"]["status"] != "ready" and services["audio"]["status"] != "ready":
        status = "error"

    if not next_actions:
        next_actions.append(
            "Gobbler is ready. Run a conversion command such as `gobbler youtube URL`.",
        )

    report = {
        "status": status,
        "can_use": status in {"ready", "degraded"},
        "version": __version__,
        "python": {
            "executable": sys.executable,
            "version": platform.python_version(),
        },
        "tools": {
            "ffmpeg": ffmpeg,
            "docker": docker,
        },
        "config": {
            "path": str(config.config_path),
            "exists": config.config_path.exists(),
            "values": redact_value(config.data),
        },
        "services": services,
        "next_actions": list(dict.fromkeys(next_actions)),
    }
    return redact_value(report)


def _print_human(report: dict[str, Any]) -> None:
    """Print a concise human-readable doctor report."""
    console.print()
    console.print("[bold]Gobbler Doctor[/bold]")
    console.print("═" * 50)
    console.print(f"Status: [bold]{report['status']}[/bold]")
    console.print(f"Version: {report['version']}")
    console.print(f"Python: {report['python']['version']}")
    console.print()

    for name, service in report["services"].items():
        marker = "[green]✓[/green]" if service["status"] == "ready" else "[yellow]![/yellow]"
        console.print(f"{marker} {name}: {service['status']}")

    console.print()
    console.print("Next actions:")
    for action in report["next_actions"]:
        console.print(f"- {action}")
    console.print()


@app.callback(invoke_without_command=True)
def doctor(
    ctx: typer.Context,
    json_output: Annotated[
        bool,
        typer.Option("--json", "-j", help="Output machine-readable JSON"),
    ] = False,
) -> None:
    """Run local diagnostics and recommend what to do next."""
    if ctx.invoked_subcommand is not None:
        return

    report = collect_doctor_report()
    if json_output:
        typer.echo(json.dumps(report, indent=2))
    else:
        _print_human(report)

    if report["status"] == "error":
        raise typer.Exit(1)
