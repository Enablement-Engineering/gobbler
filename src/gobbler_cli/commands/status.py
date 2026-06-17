"""Status command for checking Gobbler service health and readiness."""

from __future__ import annotations

import json
from typing import Annotated, Any

import typer

from gobbler_cli.knowledge import HTTP_OK
from gobbler_cli.output import add_json_contract, console
from gobbler_core.providers.webpage.crawl4ai import check_crawl4ai_conversion_probe
from gobbler_core.utils.redaction import redact_value

app = typer.Typer(help="Check Gobbler status and service health")

WEBPAGE_PROBE_TIMEOUT_SECONDS = 8.0


def check_service_health(url: str, timeout: float = 5.0) -> tuple[bool, str | None]:
    """Check if a service is healthy by hitting its health endpoint.

    Args:
        url: Base URL of the service
        timeout: Request timeout in seconds

    Returns:
        Tuple of (is_healthy, error_message)
    """
    import httpx

    health_url = f"{url.rstrip('/')}/health"
    try:
        with httpx.Client(timeout=timeout) as client:
            response = client.get(health_url)
            if response.status_code == HTTP_OK:
                return True, None
            return False, f"HTTP {response.status_code}"
    except httpx.ConnectError:
        return False, "connection refused"
    except httpx.TimeoutException:
        return False, "timeout"
    except Exception as e:
        return False, str(e)


def _crawl4ai_api_token(config_data: dict[str, Any]) -> str:
    """Return the configured Crawl4AI API token or the local default."""
    token = (
        config_data.get("services", {}).get("crawl4ai", {}).get("api_token", "gobbler-local-token")
    )
    return str(token)


def _skipped_webpage_probe(reason: str) -> dict[str, Any]:
    """Return a skipped webpage conversion probe payload."""
    return {
        "status": "skipped",
        "ok": False,
        "provider": "crawl4ai",
        "stage": "crawl_probe",
        "reason": reason,
    }


def _webpage_conversion_probe(crawl4ai_url: str, config_data: dict[str, Any]) -> dict[str, Any]:
    """Run the Crawl4AI conversion readiness probe with configured proxy support."""
    from gobbler_core.providers.proxy import get_crawl4ai_proxy_url

    return check_crawl4ai_conversion_probe(
        crawl4ai_url,
        api_token=_crawl4ai_api_token(config_data),
        proxy_url=get_crawl4ai_proxy_url(),
        timeout=WEBPAGE_PROBE_TIMEOUT_SECONDS,
    )


def get_service_status() -> dict[str, Any]:
    """Get status of all Gobbler services.

    Returns:
        Dictionary with status of each service category
    """
    from gobbler_core.config import get_config

    config = get_config()

    services: dict[str, Any] = {}
    overall_status = "ready"

    # YouTube - always available (no external service needed)
    youtube_provider = config.get("providers.youtube.default", "youtube-transcript-api")
    services["youtube"] = {
        "status": "ready",
        "provider": youtube_provider,
        "note": "No external service required",
    }

    # Audio - whisper-local is always available
    audio_provider = config.get("providers.transcription.default", "whisper-local")
    audio_model = config.get(
        "providers.transcription.whisper-local.model", config.get("whisper.model", "small")
    )
    services["audio"] = {
        "status": "ready",
        "provider": audio_provider,
        "model": audio_model,
        "note": "Local Whisper model",
    }

    # Document - requires Docling Docker service
    docling_host = config.get("services.docling.host", "localhost")
    docling_port = config.get("services.docling.port", 5001)
    docling_url = f"http://{docling_host}:{docling_port}"

    doc_healthy, doc_error = check_service_health(docling_url)
    if doc_healthy:
        services["document"] = {
            "status": "ready",
            "provider": "docling",
            "url": docling_url,
        }
    else:
        services["document"] = {
            "status": "unavailable",
            "provider": "docling",
            "url": docling_url,
            "error": doc_error,
            "fix": "docker compose up -d docling",
        }
        overall_status = "degraded"

    # Webpage - requires Crawl4AI Docker service
    crawl4ai_host = config.get("services.crawl4ai.host", "localhost")
    crawl4ai_port = config.get("services.crawl4ai.port", 11235)
    crawl4ai_url = f"http://{crawl4ai_host}:{crawl4ai_port}"

    web_healthy, web_error = check_service_health(crawl4ai_url)
    web_service_health = {
        "status": "ready" if web_healthy else "unavailable",
        "ok": web_healthy,
        "endpoint": "/health",
        "error": web_error,
    }
    if not web_healthy:
        services["webpage"] = {
            "status": "unavailable",
            "provider": "crawl4ai",
            "url": crawl4ai_url,
            "service_health": web_service_health,
            "conversion_probe": _skipped_webpage_probe("service_health_unavailable"),
            "provider_readiness": "unavailable",
            "error": web_error,
            "fix": "docker compose up -d crawl4ai",
        }
        overall_status = "degraded"
    else:
        web_probe = _webpage_conversion_probe(crawl4ai_url, config.data)
        web_probe_ready = bool(web_probe.get("ok"))
        web_status = "ready" if web_probe_ready else "degraded"
        services["webpage"] = {
            "status": web_status,
            "provider": "crawl4ai",
            "url": crawl4ai_url,
            "service_health": web_service_health,
            "conversion_probe": web_probe,
            "provider_readiness": web_status,
        }
        if not web_probe_ready:
            services["webpage"].update(
                {
                    "error": web_probe.get("error", "Crawl4AI /crawl probe failed"),
                    "fix": (
                        "Check Crawl4AI container logs and proxy configuration; "
                        "/health is passing but /crawl is not ready."
                    ),
                }
            )
            overall_status = "degraded"

    # Check proxy configuration
    proxy_config: dict[str, Any] = {"configured": False}
    proxy_services = config.get("proxy_services", {})
    if proxy_services:
        # Find first configured proxy
        for name, proxy in proxy_services.items():
            if proxy and proxy.get("type"):
                proxy_config = {
                    "configured": True,
                    "name": name,
                    "type": proxy.get("type"),
                }
                break

    # Get config path
    config_path = str(config.config_path)

    return add_json_contract(
        {
            "status": overall_status,
            "services": services,
            "config_path": config_path,
            "proxy": proxy_config,
        }
    )


@app.callback(invoke_without_command=True)
def status(  # noqa: C901, PLR0912
    ctx: typer.Context,
    json_output: Annotated[
        bool,
        typer.Option("--json", "-j", help="Output as JSON"),
    ] = False,
    verbose: Annotated[
        bool,
        typer.Option("--verbose", "-v", help="Show detailed information"),
    ] = False,
) -> None:
    """Check Gobbler service status and readiness.

    Shows the health status of all Gobbler services including:
    - YouTube transcript API (always available)
    - Audio transcription (local Whisper)
    - Document conversion (Docling Docker service)
    - Web page conversion (Crawl4AI Docker service)

    Examples:
        gobbler status
        gobbler status --json
        gobbler status -v
    """
    if ctx.invoked_subcommand is not None:
        return

    status_data = redact_value(get_service_status())

    if json_output:
        typer.echo(json.dumps(status_data, indent=2))
        return

    # Human-readable output
    console.print()
    console.print("[bold]Gobbler Status[/bold]")
    console.print("═" * 50)

    # Status indicator
    overall = status_data["status"]
    if overall == "ready":
        console.print(f"[green]●[/green] Overall: [green]{overall}[/green]")
    else:
        console.print(f"[yellow]●[/yellow] Overall: [yellow]{overall}[/yellow]")

    console.print()

    # Service status
    for name, info in status_data["services"].items():
        svc_status = info["status"]
        provider = info.get("provider", "unknown")

        if svc_status == "ready":
            status_icon = "[green]✓[/green]"
            status_text = "[green]ready[/green]"
        else:
            status_icon = "[red]✗[/red]"
            status_text = f"[red]{svc_status}[/red]"

        # Build detail string
        details = [f"[dim]{provider}[/dim]"]
        if info.get("model"):
            details.append(f"model: {info['model']}")
        if info.get("url"):
            details.append(f"@ {info['url']}")

        detail_str = ", ".join(details)
        console.print(f"  {status_icon} {name.capitalize():12} {status_text} ({detail_str})")

        # Show error and fix suggestion if unavailable
        if svc_status != "ready" and verbose:
            if info.get("error"):
                console.print(f"       [dim]Error: {info['error']}[/dim]")
            if info.get("fix"):
                console.print(f"       [dim]Fix: {info['fix']}[/dim]")
        if name == "webpage" and verbose and info.get("conversion_probe"):
            probe = info["conversion_probe"]
            console.print(f"       [dim]/crawl probe: {probe.get('status')}[/dim]")

    console.print()

    # Config info
    console.print(f"[dim]Config:[/dim] {status_data['config_path']}")

    # Proxy info
    proxy = status_data["proxy"]
    if proxy["configured"]:
        console.print(f"[dim]Proxy:[/dim]  {proxy['name']} ({proxy['type']})")
    else:
        console.print("[dim]Proxy:[/dim]  [dim]not configured[/dim]")

    console.print()

    # Exit with error code if degraded
    if overall != "ready":
        raise typer.Exit(1)
