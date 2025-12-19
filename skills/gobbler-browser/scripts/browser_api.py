#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "httpx",
#     "click",
# ]
# ///
"""
Gobbler Browser API CLI

Control the browser via the Gobbler browser extension.
Enables navigation, JavaScript execution, content extraction, and tab management.

Usage:
    uv run scripts/browser_api.py check
    uv run scripts/browser_api.py navigate "https://example.com"
    uv run scripts/browser_api.py extract [--selector SELECTOR] [--output FILE]
    uv run scripts/browser_api.py execute "document.title"
    uv run scripts/browser_api.py tabs [--filter FILTER]
"""

import json
import os
import subprocess
import sys
import time
from pathlib import Path

import click
import httpx

# Allow override via environment variable for flexibility
GOBBLER_URL = os.environ.get("GOBBLER_RELAY_URL", "http://localhost:4625")
TIMEOUT = 60.0

# Path to relay module (relative to gobbler project root)
RELAY_MODULE = Path(__file__).parent.parent.parent.parent / "src" / "gobbler_relay" / "relay.py"


def ensure_relay_running() -> bool:
    """Ensure the relay daemon is running, starting it if necessary.

    Returns:
        True if relay is running and healthy, False otherwise.
    """
    # First check if relay is already healthy
    try:
        with httpx.Client(timeout=2) as client:
            response = client.get(f"{GOBBLER_URL}/health")
            if response.status_code == 200:
                return True
    except (httpx.ConnectError, httpx.TimeoutException):
        pass

    # Relay not running, try to start it
    if not RELAY_MODULE.exists():
        click.echo(f"Error: Relay module not found at {RELAY_MODULE}", err=True)
        return False

    click.echo("Starting Gobbler relay daemon...")
    try:
        # Start the relay as a daemon using 'uv run' since relay.py has inline dependencies
        subprocess.Popen(
            ["uv", "run", str(RELAY_MODULE), "--daemon"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            stdin=subprocess.DEVNULL,
            start_new_session=True,
        )
    except Exception as e:
        click.echo(f"Failed to start relay daemon: {e}", err=True)
        return False

    # Wait for relay to become healthy
    for _ in range(10):  # Wait up to 5 seconds
        time.sleep(0.5)
        try:
            with httpx.Client(timeout=2) as client:
                response = client.get(f"{GOBBLER_URL}/health")
                if response.status_code == 200:
                    click.echo("Relay daemon started successfully")
                    return True
        except (httpx.ConnectError, httpx.TimeoutException):
            continue

    click.echo("Relay daemon did not become healthy in time", err=True)
    return False


def send_command(command: str, params: dict | None = None, timeout: float = TIMEOUT) -> dict:
    """Send command to browser extension via relay server.

    Automatically ensures the relay daemon is running before sending.
    """
    # Ensure relay is running before attempting to send
    if not ensure_relay_running():
        raise click.ClickException("Failed to start Gobbler relay daemon")

    with httpx.Client(timeout=timeout + 5) as client:
        response = client.post(
            f"{GOBBLER_URL}/command",
            json={"command": command, "params": params or {}, "timeout": timeout},
        )
        if response.status_code == 503:
            error_data = response.json()
            raise click.ClickException(error_data.get("error", "No browser extension connected"))
        response.raise_for_status()
        return response.json()


def check_health() -> dict:
    """Check relay server health."""
    with httpx.Client(timeout=5) as client:
        response = client.get(f"{GOBBLER_URL}/health")
        response.raise_for_status()
        return response.json()




@click.group()
def cli():
    """Gobbler Browser API - Control browser via extension."""
    pass


@cli.command()
def check():
    """Check if browser extension is connected, starting relay if needed."""
    try:
        # Ensure relay is running first
        if not ensure_relay_running():
            sys.exit(1)

        result = check_health()
        connections = result.get("websocket_connections", 0)
        if connections > 0:
            click.echo(f"Browser extension is connected ({connections} connection(s))")
        else:
            click.echo("Relay server running, but no browser extension connected", err=True)
            click.echo("", err=True)
            click.echo("To fix:", err=True)
            click.echo("  1. Install extension from browser-extension/ (load unpacked in Chrome)", err=True)
            click.echo("  2. Check extension popup shows 'Connected'", err=True)
            click.echo("  3. Add tabs to 'Gobbler' tab group for Claude access", err=True)
            sys.exit(1)
    except httpx.ConnectError:
        click.echo(f"Error: Cannot connect to Gobbler relay at {GOBBLER_URL}", err=True)
        click.echo("", err=True)
        click.echo("The relay server must be running. To start it:", err=True)
        click.echo("  uv run src/gobbler_relay/relay.py --daemon", err=True)
        click.echo("", err=True)
        click.echo("To check status:", err=True)
        click.echo("  uv run src/gobbler_relay/relay.py --status", err=True)
        sys.exit(1)
    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


@cli.command()
@click.argument("url")
@click.option("--wait/--no-wait", default=True, help="Wait for page to load")
def navigate(url: str, wait: bool):
    """Navigate browser to a URL."""
    try:
        result = send_command("navigate", {"url": url, "waitForLoad": wait}, timeout=60.0)
        if result.get("success"):
            click.echo(f"Successfully navigated to: {url}")
        else:
            click.echo(f"Failed to navigate: {result.get('error', 'Unknown error')}", err=True)
            sys.exit(1)
    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


@cli.command()
@click.option("--selector", "-s", default=None, help="CSS selector to extract specific content")
@click.option("--output", "-o", default=None, help="Output file path")
def extract(selector: str | None, output: str | None):
    """Extract current page content as markdown."""
    try:
        params = {}
        if selector:
            params["selector"] = selector
        result = send_command("extract_page", params)

        if result.get("success"):
            markdown = result.get("markdown", "")
            if output:
                with open(output, "w") as f:
                    f.write(markdown)
                click.echo(f"Content saved to {output}")
            else:
                click.echo(markdown)
        else:
            click.echo(f"Failed to extract: {result.get('error', 'Unknown error')}", err=True)
            sys.exit(1)
    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


@cli.command()
@click.argument("script")
@click.option("--timeout", "-t", default=30, help="Script timeout in seconds")
@click.option("--tab-id", default=None, type=int, help="Execute in specific tab")
def execute(script: str, timeout: int, tab_id: int | None):
    """Execute JavaScript in browser."""
    try:
        if tab_id:
            result = send_command(
                "execute_script_in_tab",
                {"tabId": tab_id, "script": script},
                timeout=float(timeout),
            )
        else:
            result = send_command("execute_script", {"script": script}, timeout=float(timeout))

        if result.get("success"):
            script_result = result.get("result")
            # Try to pretty-print JSON results
            if script_result is not None:
                if isinstance(script_result, (dict, list)):
                    click.echo(json.dumps(script_result, indent=2))
                else:
                    click.echo(str(script_result))
            else:
                click.echo("Script executed successfully (no return value)")
        else:
            click.echo(f"Script failed: {result.get('error', 'Unknown error')}", err=True)
            sys.exit(1)
    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


@cli.command()
@click.option("--filter", "-f", "tab_filter", default=None, help="Filter tabs (e.g., 'notebooklm')")
def tabs(tab_filter: str | None):
    """List browser tabs in Gobbler group."""
    try:
        params = {}
        if tab_filter:
            params["filter"] = tab_filter
        result = send_command("list_gobbler_tabs", params)

        if result.get("success"):
            tabs_list = result.get("tabs", [])
            if not tabs_list:
                click.echo("No tabs in Gobbler group")
                return

            click.echo(f"Found {len(tabs_list)} tab(s) in Gobbler group:\n")
            for tab in tabs_list:
                active = " (active)" if tab.get("isActive") else ""
                click.echo(f"  [{tab['tabId']}] {tab['title']}{active}")
                click.echo(f"       {tab['url']}")
        else:
            click.echo(f"Failed to list tabs: {result.get('error', 'Unknown error')}", err=True)
            sys.exit(1)
    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


if __name__ == "__main__":
    cli()
