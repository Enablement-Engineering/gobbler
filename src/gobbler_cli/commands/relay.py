"""Relay server management commands."""

from __future__ import annotations

import asyncio

import typer
from typing_extensions import Annotated

from gobbler_cli.output import print_error, print_info, print_success, print_warning

app = typer.Typer(help="Browser extension relay server management")


@app.command()
def start(
    host: Annotated[
        str,
        typer.Option("--host", "-h", help="Host to bind to"),
    ] = "127.0.0.1",
    port: Annotated[
        int,
        typer.Option("--port", "-p", help="Port to bind to"),
    ] = 4625,
    foreground: Annotated[
        bool,
        typer.Option("--foreground", "-f", help="Run in foreground (don't daemonize)"),
    ] = False,
) -> None:
    """Start the relay server."""
    asyncio.run(_start(host, port, foreground))


async def _start(host: str, port: int, foreground: bool) -> None:
    """Async implementation of start."""
    from gobbler_relay.relay import (
        ensure_relay_running,
        is_relay_healthy,
        main as relay_main,
    )

    # Check if already running
    if await is_relay_healthy(host, port):
        print_warning(f"Relay server is already running at http://{host}:{port}")
        return

    if foreground:
        print_info(f"Starting relay server in foreground at http://{host}:{port}")
        print_info("Press Ctrl+C to stop")
        try:
            await relay_main()
        except KeyboardInterrupt:
            print_info("Relay server stopped")
    else:
        # Start as daemon
        success = await ensure_relay_running(host=host, port=port, start_if_missing=True)
        if success:
            print_success(f"Relay server started at http://{host}:{port}")
            print_info("Browser extension can now connect via WebSocket")
        else:
            print_error("Failed to start relay server")
            raise typer.Exit(1)


@app.command()
def stop() -> None:
    """Stop the relay server daemon."""
    from gobbler_relay.relay import stop_relay_daemon

    if stop_relay_daemon():
        print_success("Relay server stopped")
    else:
        print_info("Relay server was not running")


@app.command()
def status() -> None:
    """Check relay server status."""
    asyncio.run(_status())


async def _status() -> None:
    """Async implementation of status."""
    from gobbler_relay.relay import (
        DEFAULT_HOST,
        DEFAULT_PORT,
        is_process_running,
        is_relay_healthy,
        read_pidfile,
    )

    pid = read_pidfile()

    if pid and is_process_running(pid):
        print_success(f"Relay daemon is running (PID {pid})")
    else:
        print_warning("Relay daemon is not running")
        if pid:
            print_info("Stale pidfile exists, may need cleanup")
        return

    # Check health
    healthy = await is_relay_healthy(DEFAULT_HOST, DEFAULT_PORT)
    if healthy:
        print_success(f"Relay is healthy at http://{DEFAULT_HOST}:{DEFAULT_PORT}")

        # Get connection count
        from gobbler_relay.client import get_connection_count

        try:
            connections = await get_connection_count()
            if connections > 0:
                print_success(f"{connections} browser extension(s) connected")
            else:
                print_info("No browser extensions connected")
        except Exception:  # noqa: S110  # nosec B110
            pass
    else:
        print_warning("Relay process exists but not responding to health checks")


@app.command()
def restart(
    host: Annotated[
        str,
        typer.Option("--host", "-h", help="Host to bind to"),
    ] = "127.0.0.1",
    port: Annotated[
        int,
        typer.Option("--port", "-p", help="Port to bind to"),
    ] = 4625,
) -> None:
    """Restart the relay server."""
    asyncio.run(_restart(host, port))


async def _restart(host: str, port: int) -> None:
    """Async implementation of restart."""
    from gobbler_relay.relay import ensure_relay_running, stop_relay_daemon

    # Stop if running
    stop_relay_daemon()

    # Wait a moment for cleanup
    await asyncio.sleep(1)

    # Start fresh
    success = await ensure_relay_running(host=host, port=port, start_if_missing=True)
    if success:
        print_success(f"Relay server restarted at http://{host}:{port}")
    else:
        print_error("Failed to restart relay server")
        raise typer.Exit(1)
