"""Daemon management commands."""

from __future__ import annotations

import asyncio
import subprocess
import sys
from pathlib import Path

import typer
from typing_extensions import Annotated

from gobbler_cli.output import (
    print_error,
    print_info,
    print_success,
    print_table,
    print_warning,
)

app = typer.Typer(help="Daemon management")


@app.command()
def start(
    port: Annotated[
        int,
        typer.Option("--port", "-p", help="Port to run daemon on"),
    ] = 4600,
    detach: Annotated[
        bool,
        typer.Option("--detach/--foreground", help="Run as background daemon"),
    ] = True,
) -> None:
    """
    Start the Gobbler daemon.

    Examples:
        gobbler daemon start
        gobbler daemon start --port 5000
        gobbler daemon start --foreground
    """
    asyncio.run(_start_daemon(port=port, detach=detach))


async def _start_daemon(port: int, detach: bool) -> None:
    """Start the daemon process."""
    try:
        # Check if daemon is already running
        if await _is_daemon_running():
            print_warning("Daemon is already running")
            print_info("Use 'gobbler daemon status' to check status")
            return

        # TODO: This will need integration with gobbler_daemon when implemented
        # For now, we'll use the relay server as a placeholder
        from gobbler_relay import start_relay_daemon

        if detach:
            print_info(f"Starting Gobbler daemon on port {port}...")
            pid = start_relay_daemon(port=port)
            print_success("Daemon started successfully")
            print_info(f"API available at http://localhost:{port}")
            print_info(f"Daemon PID: {pid}")
        else:
            print_info(f"Starting Gobbler daemon on port {port} (foreground mode)...")
            print_info("Press Ctrl+C to stop")
            from gobbler_relay import start_relay_server

            await start_relay_server(port=port)

    except KeyboardInterrupt:
        print_info("\nShutting down daemon...")
    except Exception as e:
        print_error(f"Failed to start daemon: {e}")
        raise typer.Exit(1)


@app.command()
def stop() -> None:
    """
    Stop the Gobbler daemon.

    Examples:
        gobbler daemon stop
    """
    asyncio.run(_stop_daemon())


async def _stop_daemon() -> None:
    """Stop the daemon process."""
    try:
        # Check if daemon is running
        if not await _is_daemon_running():
            print_info("Daemon is not running")
            return

        # TODO: This will need integration with gobbler_daemon when implemented
        from gobbler_relay import stop_relay_daemon

        print_info("Stopping Gobbler daemon...")
        success = stop_relay_daemon()
        if success:
            print_success("Daemon stopped successfully")
        else:
            print_warning("Failed to stop daemon (may not be running)")

    except Exception as e:
        print_error(f"Failed to stop daemon: {e}")
        raise typer.Exit(1)


@app.command()
def status() -> None:
    """
    Check daemon status.

    Examples:
        gobbler daemon status
    """
    asyncio.run(_daemon_status())


async def _daemon_status() -> None:
    """Check and display daemon status."""
    try:
        # Check if daemon is running
        running = await _is_daemon_running()

        if running:
            # Get daemon info
            info = await _get_daemon_info()

            print_success("Daemon is running")
            print_table(
                "Daemon Status",
                ["Property", "Value"],
                [
                    ["Status", "Running"],
                    ["Port", str(info.get("port", "Unknown"))],
                    ["PID", str(info.get("pid", "Unknown"))],
                    ["Uptime", info.get("uptime", "Unknown")],
                    ["API URL", f"http://localhost:{info.get('port', 4600)}"],
                ],
            )
        else:
            print_info("Daemon is not running")
            print_info("Start it with: gobbler daemon start")

    except Exception as e:
        print_error(f"Failed to check daemon status: {e}")
        raise typer.Exit(1)


@app.command()
def logs(
    follow: Annotated[
        bool,
        typer.Option("--follow", "-f", help="Follow log output"),
    ] = False,
    lines: Annotated[
        int,
        typer.Option("--lines", "-n", help="Number of lines to show"),
    ] = 50,
) -> None:
    """
    View daemon logs.

    Examples:
        gobbler daemon logs
        gobbler daemon logs --follow
        gobbler daemon logs --lines 100
    """
    try:
        # Get log file path
        log_file = _get_log_file_path()

        if not log_file.exists():
            print_warning(f"Log file not found: {log_file}")
            print_info("Daemon may not have been started yet")
            return

        if follow:
            # Follow logs using tail -f
            print_info(f"Following logs from {log_file}")
            print_info("Press Ctrl+C to stop")
            try:
                subprocess.run(["tail", "-f", str(log_file)], check=True)
            except KeyboardInterrupt:
                print_info("\nStopped following logs")
        else:
            # Show last N lines
            result = subprocess.run(
                ["tail", "-n", str(lines), str(log_file)],
                capture_output=True,
                text=True,
                check=True,
            )
            print(result.stdout)

    except subprocess.CalledProcessError as e:
        print_error(f"Failed to read logs: {e}")
        raise typer.Exit(1)
    except Exception as e:
        print_error(f"Failed to view logs: {e}")
        raise typer.Exit(1)


@app.command()
def restart(
    port: Annotated[
        int,
        typer.Option("--port", "-p", help="Port to run daemon on"),
    ] = 4600,
) -> None:
    """
    Restart the Gobbler daemon.

    Examples:
        gobbler daemon restart
        gobbler daemon restart --port 5000
    """
    asyncio.run(_restart_daemon(port=port))


async def _restart_daemon(port: int) -> None:
    """Restart the daemon process."""
    try:
        print_info("Restarting Gobbler daemon...")

        # Stop if running
        if await _is_daemon_running():
            await _stop_daemon()
            # Wait a moment for cleanup
            await asyncio.sleep(1)

        # Start again
        await _start_daemon(port=port, detach=True)

    except Exception as e:
        print_error(f"Failed to restart daemon: {e}")
        raise typer.Exit(1)


async def _is_daemon_running() -> bool:
    """
    Check if daemon is running.

    Returns:
        True if daemon is running, False otherwise
    """
    try:
        # TODO: Replace with actual daemon health check when implemented
        from gobbler_relay import is_relay_healthy

        return await is_relay_healthy()
    except Exception:
        return False


async def _get_daemon_info() -> dict[str, str]:
    """
    Get daemon information.

    Returns:
        Dictionary with daemon info
    """
    # TODO: Replace with actual daemon info endpoint when implemented
    # For now, return basic info
    try:
        import psutil

        # Find daemon process
        pid_file = Path.home() / ".config" / "gobbler" / "gobbler.pid"
        if pid_file.exists():
            pid = int(pid_file.read_text().strip())
            try:
                process = psutil.Process(pid)
                uptime_seconds = int(process.create_time())
                import time

                uptime = int(time.time() - uptime_seconds)
                hours = uptime // 3600
                minutes = (uptime % 3600) // 60

                return {
                    "port": "4600",  # TODO: Get from config
                    "pid": str(pid),
                    "uptime": f"{hours}h {minutes}m",
                }
            except psutil.NoSuchProcess:
                pass
    except Exception:
        pass

    return {
        "port": "4600",
        "pid": "Unknown",
        "uptime": "Unknown",
    }


def _get_log_file_path() -> Path:
    """
    Get the path to the daemon log file.

    Returns:
        Path to log file
    """
    # TODO: Get from config when implemented
    return Path.home() / ".config" / "gobbler" / "gobbler.log"
