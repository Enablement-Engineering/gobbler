"""Browser control commands via the Gobbler browser extension."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Annotated

import typer

from gobbler_cli.output import (
    OutputFormat,
    console,
    print_error,
    print_info,
    print_success,
    print_table,
    print_warning,
    write_output,
)

app = typer.Typer(help="Browser control via Gobbler extension")

# Global state for --no-auto-start option
_auto_start_enabled = True


def set_auto_start(enabled: bool) -> None:
    """Set whether relay auto-start is enabled."""
    global _auto_start_enabled
    _auto_start_enabled = enabled


@app.callback()
def browser_callback(
    no_auto_start: Annotated[
        bool,
        typer.Option(
            "--no-auto-start",
            help="Disable automatic relay server startup (for debugging)",
        ),
    ] = False,
) -> None:
    """Browser control via Gobbler extension."""
    set_auto_start(not no_auto_start)


def read_urls_from_file(filepath: Path) -> list[str]:
    """Read URLs from a file, one per line. Skips empty lines and comments."""
    urls = []
    with open(filepath) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#"):
                urls.append(line)
    return urls


async def _check_relay_and_extension() -> tuple[bool, bool, str]:
    """Check if relay is running and extension is connected.

    Returns:
        Tuple of (success, relay_was_auto_started, message)
    """
    from gobbler_relay.client import check_connection, ensure_relay_running, is_relay_running

    relay_auto_started = False

    # Try to ensure relay is running (auto-start if enabled)
    if _auto_start_enabled:
        try:
            # Check if already running before we try to ensure
            was_running = await is_relay_running()
            await ensure_relay_running()
            if not was_running:
                relay_auto_started = True
        except RuntimeError as e:
            return False, False, f"Failed to start relay: {e}"
    # Auto-start disabled, just check if running
    elif not await is_relay_running():
        return False, False, "Relay server is not running. Start it with: gobbler relay start"

    status = await check_connection()
    if status.get("status") == "error":
        return False, relay_auto_started, status.get("message", "Unknown error")

    connections = status.get("websocket_connections", 0)
    if connections == 0:
        return (
            False,
            relay_auto_started,
            "No browser extension connected. Install and connect the Gobbler extension.",
        )

    return True, relay_auto_started, f"{connections} extension(s) connected"


@app.command()
def status(
    no_auto_start: Annotated[
        bool,
        typer.Option(
            "--no-auto-start",
            help="Don't auto-start the relay (just check status)",
        ),
    ] = True,  # Default to True for status command - just show status
) -> None:
    """Check browser extension connection status."""
    # For status command, default to not auto-starting (just show current state)
    set_auto_start(not no_auto_start)
    asyncio.run(_status())


async def _status() -> None:
    """Async implementation of status check."""
    from gobbler_relay.client import check_connection, ensure_relay_running, is_relay_running

    relay_auto_started = False

    # Check/start relay
    if _auto_start_enabled:
        try:
            was_running = await is_relay_running()
            await ensure_relay_running()
            if not was_running:
                relay_auto_started = True
                print_success("Relay server started automatically")
            else:
                print_success("Relay server is running")
        except RuntimeError as e:
            print_error(f"Failed to start relay: {e}")
            raise typer.Exit(1)
    else:
        relay_running = await is_relay_running()
        if relay_running:
            print_success("Relay server is running")
        else:
            print_error("Relay server is not running")
            print_info("Start it with: gobbler relay start")
            raise typer.Exit(1)

    # Check extension connection
    status_data = await check_connection()
    connections = status_data.get("websocket_connections", 0)

    if connections > 0:
        print_success(f"{connections} browser extension(s) connected")
    else:
        print_warning("No browser extension connected")
        print_info("Install the Gobbler extension and add tabs to the 'Gobbler' tab group")


@app.command("list")
def list_tabs(
    filter_type: Annotated[
        str | None,
        typer.Option("--filter", "-f", help="Filter tabs (e.g., 'notebooklm')"),
    ] = None,
    json_output: Annotated[
        bool,
        typer.Option("--json", "-j", help="Output as JSON"),
    ] = False,
) -> None:
    """List tabs in the Gobbler tab group."""
    asyncio.run(_list_tabs(filter_type, json_output))


async def _list_tabs(filter_type: str | None, json_output: bool) -> None:
    """Async implementation of list tabs."""
    from gobbler_relay.client import list_tabs

    ok, auto_started, msg = await _check_relay_and_extension()
    if auto_started:
        print_info("Relay server started automatically")
    if not ok:
        print_error(msg)
        raise typer.Exit(1)

    try:
        result = await list_tabs(filter_type=filter_type)

        if not result.get("success"):
            print_error(result.get("error", "Failed to list tabs"))
            raise typer.Exit(1)

        tabs = result.get("tabs", [])

        if json_output:
            console.print_json(json.dumps(tabs))
            return

        if not tabs:
            print_info("No tabs found in Gobbler group")
            if filter_type:
                print_info(f"(filtered by: {filter_type})")
            return

        rows = []
        for tab in tabs:
            tab_id = str(tab.get("tabId", "?"))
            title = tab.get("title", "Unknown")[:50]
            url = tab.get("url", "")[:60]
            rows.append([tab_id, title, url])

        print_table(
            title=f"Gobbler Tabs{f' (filter: {filter_type})' if filter_type else ''}",
            columns=["Tab ID", "Title", "URL"],
            rows=rows,
        )

    except RuntimeError as e:
        print_error(str(e))
        raise typer.Exit(1)


@app.command()
def navigate(
    url: Annotated[str, typer.Argument(help="URL to navigate to")],
) -> None:
    """Navigate the active tab to a URL."""
    asyncio.run(_navigate(url))


async def _navigate(url: str) -> None:
    """Async implementation of navigate."""
    from gobbler_relay.client import navigate

    ok, auto_started, msg = await _check_relay_and_extension()
    if auto_started:
        print_info("Relay server started automatically")
    if not ok:
        print_error(msg)
        raise typer.Exit(1)

    try:
        result = await navigate(url)

        if result.get("success"):
            print_success(f"Navigated to: {url}")
        else:
            print_error(result.get("error", "Navigation failed"))
            raise typer.Exit(1)

    except RuntimeError as e:
        print_error(str(e))
        raise typer.Exit(1)


@app.command()
def extract(
    selector: Annotated[
        str | None,
        typer.Option("--selector", "-s", help="CSS selector to extract specific content"),
    ] = None,
    output: Annotated[
        Path | None,
        typer.Option("--output", "-o", help="Output file path"),
    ] = None,
    tab_id: Annotated[
        int | None,
        typer.Option("--tab", "-t", help="Specific tab ID (active tab if not specified)"),
    ] = None,
    json_output: Annotated[
        bool,
        typer.Option("--json", "-j", help="Output as JSON with metadata"),
    ] = False,
) -> None:
    """Extract a page as markdown."""
    asyncio.run(_extract(selector, output, tab_id, json_output))


async def _extract(
    selector: str | None,
    output: Path | None,
    tab_id: int | None,
    json_output: bool = False,
) -> None:
    """Async implementation of extract."""
    from gobbler_relay.client import extract_page

    ok, auto_started, msg = await _check_relay_and_extension()
    if auto_started and not json_output:
        print_info("Relay server started automatically")
    if not ok:
        if json_output:
            json_result = {
                "success": False,
                "error": msg,
                "error_code": "RELAY_CONNECTION_ERROR",
            }
            console.print_json(json.dumps(json_result))
        else:
            print_error(msg)
        raise typer.Exit(1)

    try:
        result = await extract_page(selector=selector, tab_id=tab_id)

        if not result.get("success"):
            error_msg = result.get("error", "Extraction failed")
            if json_output:
                json_result = {
                    "success": False,
                    "error": error_msg,
                    "error_code": "EXTRACTION_ERROR",
                }
                console.print_json(json.dumps(json_result))
            else:
                print_error(error_msg)
            raise typer.Exit(1)

        markdown = result.get("markdown", "")
        metadata = {
            "url": result.get("url", ""),
            "title": result.get("title", ""),
            "tab_id": result.get("tabId"),
        }

        if json_output:
            json_result = {
                "success": True,
                "markdown": markdown,
                "metadata": metadata,
            }
            if output:
                output.parent.mkdir(parents=True, exist_ok=True)
                output.write_text(json.dumps(json_result, indent=2), encoding="utf-8")
            else:
                console.print_json(json.dumps(json_result))
        else:
            write_output(markdown, output, OutputFormat.MARKDOWN)
            if output:
                print_success("Page extracted successfully")

    except RuntimeError as e:
        if json_output:
            json_result = {
                "success": False,
                "error": str(e),
                "error_code": "RUNTIME_ERROR",
            }
            console.print_json(json.dumps(json_result))
        else:
            print_error(str(e))
        raise typer.Exit(1)


@app.command("exec")
def execute(
    script: Annotated[str, typer.Argument(help="JavaScript code to execute")],
    tab_id: Annotated[
        int | None,
        typer.Option("--tab", "-t", help="Specific tab ID (active tab if not specified)"),
    ] = None,
    timeout: Annotated[
        int,
        typer.Option("--timeout", help="Timeout in seconds"),
    ] = 30,
    json_output: Annotated[
        bool,
        typer.Option("--json", "-j", help="Output result as JSON"),
    ] = False,
) -> None:
    """Execute JavaScript in the browser."""
    asyncio.run(_execute(script, tab_id, timeout, json_output))


async def _execute(script: str, tab_id: int | None, timeout: int, json_output: bool) -> None:
    """Async implementation of execute."""
    from gobbler_relay.client import execute_script, execute_script_in_tab

    ok, auto_started, msg = await _check_relay_and_extension()
    if auto_started:
        print_info("Relay server started automatically")
    if not ok:
        print_error(msg)
        raise typer.Exit(1)

    try:
        if tab_id:
            result = await execute_script_in_tab(
                tab_id=tab_id, script=script, timeout=float(timeout)
            )
        else:
            result = await execute_script(script=script, timeout=float(timeout))

        if not result.get("success"):
            print_error(result.get("error", "Script execution failed"))
            raise typer.Exit(1)

        script_result = result.get("result")

        if json_output:
            console.print_json(json.dumps(script_result))
        elif script_result is not None:
            if isinstance(script_result, (dict, list)):
                console.print_json(json.dumps(script_result))
            else:
                console.print(str(script_result))

    except RuntimeError as e:
        print_error(str(e))
        raise typer.Exit(1)


@app.command("open")
def open_tabs(
    urls: Annotated[
        list[str] | None,
        typer.Argument(help="URLs to open in the Gobbler tab group"),
    ] = None,
    file: Annotated[
        Path | None,
        typer.Option("--file", "-f", help="Read URLs from file (one per line)"),
    ] = None,
    json_output: Annotated[
        bool,
        typer.Option("--json", "-j", help="Output as JSON"),
    ] = False,
) -> None:
    """Open URLs in new tabs within the Gobbler tab group.

    Examples:
        gobbler browser open https://example.com https://google.com
        gobbler browser open -f urls.txt
        cat urls.txt | gobbler browser open -f -
    """
    asyncio.run(_open_tabs(urls or [], file, json_output))


async def _open_tabs(urls: list[str], file: Path | None, json_output: bool) -> None:
    """Async implementation of open tabs."""
    from gobbler_relay.client import open_tabs

    # Collect URLs from arguments and file
    all_urls = list(urls)

    if file:
        if str(file) == "-":
            # Read from stdin
            import sys

            for line in sys.stdin:
                line = line.strip()
                if line and not line.startswith("#"):
                    all_urls.append(line)
        else:
            all_urls.extend(read_urls_from_file(file))

    if not all_urls:
        print_error("No URLs provided. Use positional arguments or --file")
        raise typer.Exit(1)

    ok, auto_started, msg = await _check_relay_and_extension()
    if auto_started:
        print_info("Relay server started automatically")
    if not ok:
        print_error(msg)
        raise typer.Exit(1)

    try:
        print_info(f"Opening {len(all_urls)} URL(s) in Gobbler tab group...")
        result = await open_tabs(all_urls)

        if not result.get("success"):
            print_error(result.get("error", "Failed to open tabs"))
            raise typer.Exit(1)

        opened = result.get("tabs", [])

        if json_output:
            console.print_json(json.dumps(result))
            return

        print_success(f"Opened {len(opened)} tab(s)")

        if opened:
            rows = []
            for tab in opened:
                tab_id = str(tab.get("tabId", "?"))
                url = tab.get("url", "")[:70]
                rows.append([tab_id, url])

            print_table(
                title="Opened Tabs",
                columns=["Tab ID", "URL"],
                rows=rows,
            )

    except RuntimeError as e:
        print_error(str(e))
        raise typer.Exit(1)
