#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "aiohttp>=3.9.0",
#     "beautifulsoup4>=4.12.0",
#     "httpx>=0.27.0",
#     "markdownify>=0.13.0",
# ]
# ///
"""
Gobbler Browser Extension Relay Server.

Provides HTTP and WebSocket endpoints for browser extension communication.
Can be run standalone with `uv run relay.py` or imported by MCP server.

Endpoints:
    GET  /ws       - WebSocket for browser extension
    POST /command  - Send command to extension (for skills/scripts)
    POST /extract  - Process page extraction from extension
    GET  /health   - Health check with connection count
"""

import asyncio
import json
import logging
import os
import re
import signal
import subprocess
import sys
import uuid
from pathlib import Path
from typing import TYPE_CHECKING, Optional

import httpx
from aiohttp import web
from bs4 import BeautifulSoup
from markdownify import markdownify as md

from gobbler_core.utils.frontmatter import count_words, create_webpage_frontmatter

if TYPE_CHECKING:
    from typing import Dict, Set

logger = logging.getLogger(__name__)

# Default configuration
DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 4625
PIDFILE_PATH = Path.home() / ".cache" / "gobbler" / "relay.pid"

# Auto-shutdown configuration
# Relay will shut down after this many seconds of inactivity (no HTTP requests)
AUTO_SHUTDOWN_TIMEOUT = 14400  # 4 hours

# Global WebSocket connections and command queue
websocket_connections: "Set[web.WebSocketResponse]" = set()
pending_commands: "Dict[str, Dict]" = {}  # command_id -> {event: asyncio.Event, response: dict}

# Activity tracking for auto-shutdown
last_activity_time: float = 0.0
auto_shutdown_task: Optional[asyncio.Task] = None


async def extract_handler(request: web.Request) -> web.Response:
    """
    Handle page extraction requests from browser extension.

    Expects JSON body with:
    {
        "url": "https://example.com",
        "title": "Page Title",
        "html": "<html>...</html>",
        "text": "page text content",
        "selector": "optional CSS selector"
    }

    Returns JSON with:
    {
        "markdown": "# Page Title\n\n...",
        "metadata": {...}
    }
    """
    try:
        data = await request.json()

        url = data.get("url", "")
        title = data.get("title", "Unknown Page")
        html = data.get("html", "")
        selector = data.get("selector")

        # Convert HTML to markdown preserving links
        soup = BeautifulSoup(html, "html.parser")

        # If selector provided, extract only that element
        if selector:
            element = soup.select_one(selector)
            if element:
                soup = BeautifulSoup(str(element), "html.parser")
            else:
                return web.json_response({"error": f"Selector '{selector}' not found"}, status=400)

        # Remove scripts, styles, and navigation elements
        for script in soup(["script", "style", "nav", "header", "footer"]):
            script.decompose()

        # Convert HTML to markdown using markdownify
        markdown_content = md(
            str(soup),
            heading_style="ATX",
            bullets="-",
            strip=["script", "style"],
            escape_asterisks=False,
            escape_underscores=False,
        )

        # Clean up excessive newlines
        markdown_content = re.sub(r"\n{3,}", "\n\n", markdown_content)
        markdown_content = "\n".join(line.strip() for line in markdown_content.split("\n"))
        markdown_content = markdown_content.strip()

        # Create frontmatter
        word_count = count_words(markdown_content)
        frontmatter = create_webpage_frontmatter(
            url=url,
            title=title,
            word_count=word_count,
            conversion_time_ms=0,
        )

        # Add source info to frontmatter
        lines = frontmatter.split("\n")
        frontmatter_lines = []
        for line in lines:
            frontmatter_lines.append(line)
            if line == "---" and len(frontmatter_lines) > 1:
                if selector:
                    frontmatter_lines.insert(-1, f"selector: {selector}")
                frontmatter_lines.insert(-1, "source: browser_extension")
                break
        frontmatter = "\n".join(frontmatter_lines)

        full_markdown = frontmatter + markdown_content

        metadata = {
            "url": url,
            "title": title,
            "word_count": word_count,
            "source": "browser_extension",
        }

        if selector:
            metadata["selector"] = selector

        logger.info(f"Extracted content from browser extension: {url}")

        return web.json_response({"markdown": full_markdown, "metadata": metadata})

    except Exception as e:
        logger.exception("Extension extraction error")
        return web.json_response({"error": str(e)}, status=500)


async def health_handler(request: web.Request) -> web.Response:
    """Health check endpoint."""
    return web.json_response({"status": "ok", "websocket_connections": len(websocket_connections)})


async def websocket_handler(request: web.Request) -> web.WebSocketResponse:
    """
    Handle WebSocket connections from browser extension.

    Enables bidirectional communication for sending commands to the extension
    and receiving responses.
    """
    ws = web.WebSocketResponse()
    await ws.prepare(request)

    websocket_connections.add(ws)
    logger.info(f"WebSocket connected. Total connections: {len(websocket_connections)}")

    try:
        async for msg in ws:
            if msg.type == web.WSMsgType.TEXT:
                try:
                    data = json.loads(msg.data)
                    message_type = data.get("type")

                    if message_type == "command_response":
                        # Handle response to a command we sent
                        command_id = data.get("command_id")
                        if command_id in pending_commands:
                            pending_commands[command_id]["response"] = data.get("result", {})
                            pending_commands[command_id]["event"].set()

                    elif message_type == "ping":
                        # Respond to ping with pong
                        await ws.send_json({"type": "pong"})

                    elif message_type == "register":
                        # Extension registered successfully
                        await ws.send_json({"type": "registered", "server_version": "0.1.0"})
                        logger.info("Extension registered via WebSocket")

                except json.JSONDecodeError:
                    logger.error(f"Invalid JSON received: {msg.data}")

            elif msg.type == web.WSMsgType.ERROR:
                logger.error(f"WebSocket error: {ws.exception()}")

    finally:
        websocket_connections.discard(ws)
        logger.info(f"WebSocket disconnected. Total connections: {len(websocket_connections)}")

    return ws


async def send_command_to_extension(
    command: str,
    params: Optional[dict] = None,
    timeout: float = 30.0,
) -> dict:
    """
    Send a command to the browser extension and wait for response.

    Args:
        command: Command name (e.g., "extract_page", "navigate", "execute_script")
        params: Optional parameters for the command
        timeout: Timeout in seconds to wait for response

    Returns:
        Response from the extension

    Raises:
        RuntimeError: If no extension is connected or command times out
    """
    if not websocket_connections:
        raise RuntimeError("No browser extension connected")

    # Generate unique command ID
    command_id = str(uuid.uuid4())

    # Create event to wait for response
    event = asyncio.Event()
    pending_commands[command_id] = {"event": event, "response": None}

    # Prepare command message
    message = {
        "type": "command",
        "command_id": command_id,
        "command": command,
        "params": params or {},
    }

    try:
        # Send to only ONE extension (the first/most recent one)
        # This prevents duplicate execution if multiple connections exist
        if websocket_connections:
            ws = next(iter(websocket_connections))
            await ws.send_json(message)
            logger.info(f"Sent command '{command}' to extension (id: {command_id})")

        # Wait for response with timeout
        try:
            await asyncio.wait_for(event.wait(), timeout=timeout)
            response = pending_commands[command_id]["response"]

            if response is None:
                raise RuntimeError("Extension response was empty")

            return response

        except asyncio.TimeoutError:
            raise RuntimeError(f"Command '{command}' timed out after {timeout} seconds")

    finally:
        # Cleanup
        pending_commands.pop(command_id, None)


async def command_handler(request: web.Request) -> web.Response:
    """
    Handle command requests from skills/scripts via HTTP.

    Expects JSON body with:
    {
        "command": "navigate",
        "params": {"url": "https://example.com"},
        "timeout": 30
    }

    Returns JSON with command result from extension.
    """
    try:
        data = await request.json()

        command = data.get("command")
        if not command:
            return web.json_response({"error": "Missing 'command' field"}, status=400)

        params = data.get("params", {})
        timeout = data.get("timeout", 30)

        result = await send_command_to_extension(
            command=command,
            params=params,
            timeout=timeout,
        )

        return web.json_response(result)

    except RuntimeError as e:
        # No extension connected or timeout
        return web.json_response({"error": str(e)}, status=503)
    except Exception as e:
        logger.exception("Command handler error")
        return web.json_response({"error": str(e)}, status=500)


def update_activity() -> None:
    """Update the last activity timestamp."""
    global last_activity_time
    import time

    last_activity_time = time.time()


def create_app(
    enable_auto_shutdown: bool = False, shutdown_event: Optional[asyncio.Event] = None
) -> web.Application:
    """Create and configure the HTTP server application.

    Args:
        enable_auto_shutdown: If True, track activity for auto-shutdown
        shutdown_event: Event to set when auto-shutdown triggers
    """
    # Increase max request size to 50MB for large pages
    app = web.Application(client_max_size=50 * 1024 * 1024)

    # Add CORS middleware to allow browser extension requests
    @web.middleware
    async def cors_middleware(
        request: web.Request, handler: web.RequestHandler
    ) -> web.StreamResponse:
        if request.method == "OPTIONS":
            response = web.Response()
        else:
            response = await handler(request)

        response.headers["Access-Control-Allow-Origin"] = "*"
        response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
        response.headers["Access-Control-Allow-Headers"] = "Content-Type"
        return response

    app.middlewares.append(cors_middleware)

    # Add activity tracking middleware for auto-shutdown
    if enable_auto_shutdown:

        @web.middleware
        async def activity_middleware(
            request: web.Request, handler: web.RequestHandler
        ) -> web.StreamResponse:
            # Track activity on command requests (not health checks or WebSocket)
            if request.path in ("/command", "/extract"):
                update_activity()
            return await handler(request)

        app.middlewares.append(activity_middleware)

    # Store shutdown event in app for access from handlers
    app["shutdown_event"] = shutdown_event

    # Add routes
    app.router.add_post("/extract", extract_handler)
    app.router.add_post("/command", command_handler)
    app.router.add_get("/health", health_handler)
    app.router.add_get("/ws", websocket_handler)

    return app


async def auto_shutdown_monitor(
    shutdown_event: asyncio.Event, timeout: int = AUTO_SHUTDOWN_TIMEOUT
) -> None:
    """
    Monitor activity and trigger shutdown after inactivity timeout.

    Args:
        shutdown_event: Event to set when shutdown should occur
        timeout: Inactivity timeout in seconds
    """
    import time

    logger.info(f"Auto-shutdown monitor started (timeout: {timeout}s)")
    update_activity()  # Initialize activity time

    while not shutdown_event.is_set():
        await asyncio.sleep(30)  # Check every 30 seconds

        if shutdown_event.is_set():
            break

        elapsed = time.time() - last_activity_time
        remaining = timeout - elapsed

        if remaining <= 0:
            logger.info(f"No activity for {timeout}s, initiating auto-shutdown...")
            shutdown_event.set()
            break
        elif remaining < 60:
            logger.debug(f"Auto-shutdown in {int(remaining)}s unless activity detected")


async def start_relay_server(host: str = "127.0.0.1", port: int = 4625) -> web.AppRunner:
    """
    Start the relay server for browser extension communication.

    Args:
        host: Host address to bind to (default: 127.0.0.1)
        port: Port to listen on (default: 4625)

    Returns:
        AppRunner instance for cleanup
    """
    app = create_app()
    runner = web.AppRunner(app)
    await runner.setup()

    site = web.TCPSite(runner, host, port)
    await site.start()

    logger.info(f"Gobbler relay server started on http://{host}:{port}")
    logger.info("Browser extension can now connect via WebSocket at /ws")
    logger.info("Skills can send commands via HTTP POST to /command")

    return runner


# =============================================================================
# Pidfile and Daemon Management
# =============================================================================


def get_pidfile_path() -> Path:
    """Get the path to the pidfile."""
    return PIDFILE_PATH


def write_pidfile(pid: int) -> None:
    """Write the current process ID to the pidfile."""
    pidfile = get_pidfile_path()
    pidfile.parent.mkdir(parents=True, exist_ok=True)
    pidfile.write_text(str(pid))
    logger.info(f"Wrote PID {pid} to {pidfile}")


def read_pidfile() -> Optional[int]:
    """Read the PID from the pidfile, if it exists."""
    pidfile = get_pidfile_path()
    if not pidfile.exists():
        return None
    try:
        return int(pidfile.read_text().strip())
    except (ValueError, OSError):
        return None


def remove_pidfile() -> None:
    """Remove the pidfile."""
    pidfile = get_pidfile_path()
    try:
        pidfile.unlink(missing_ok=True)
        logger.info(f"Removed pidfile {pidfile}")
    except OSError as e:
        logger.warning(f"Failed to remove pidfile: {e}")


def is_process_running(pid: int) -> bool:
    """Check if a process with the given PID is running."""
    try:
        os.kill(pid, 0)
        return True
    except (OSError, ProcessLookupError):
        return False


async def is_relay_healthy(
    host: str = DEFAULT_HOST, port: int = DEFAULT_PORT, timeout: float = 2.0
) -> bool:
    """
    Check if the relay server is running and responding to health checks.

    Args:
        host: Relay host
        port: Relay port
        timeout: Request timeout

    Returns:
        True if relay is healthy, False otherwise
    """
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.get(f"http://{host}:{port}/health")
            return response.status_code == 200
    except (httpx.ConnectError, httpx.TimeoutException, Exception):
        return False


def start_relay_daemon(host: str = DEFAULT_HOST, port: int = DEFAULT_PORT) -> int:
    """
    Start the relay server as a background daemon process.

    Args:
        host: Host to bind to
        port: Port to bind to

    Returns:
        PID of the daemon process

    Raises:
        RuntimeError: If daemon fails to start
    """
    # Find the relay module path
    relay_module = Path(__file__).resolve()

    # Start as background process
    # Use the same Python interpreter and run this module with --daemon flag
    cmd = [
        sys.executable,
        str(relay_module),
        "--daemon",
        "--host",
        host,
        "--port",
        str(port),
    ]

    # Start detached process
    # cmd is built from sys.executable and __file__ paths (not user input)
    process = subprocess.Popen(  # noqa: S603  # nosec B603
        cmd,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        stdin=subprocess.DEVNULL,
        start_new_session=True,  # Detach from parent process group
    )

    logger.info(f"Started relay daemon with PID {process.pid}")
    return process.pid


async def ensure_relay_running(
    host: str = DEFAULT_HOST,
    port: int = DEFAULT_PORT,
    start_if_missing: bool = True,
    wait_timeout: float = 5.0,
) -> bool:
    """
    Ensure the relay server is running, starting it if necessary.

    This is the main entry point for MCP servers and skills to ensure
    the relay is available before sending commands.

    Args:
        host: Relay host
        port: Relay port
        start_if_missing: If True, start the relay if not running
        wait_timeout: How long to wait for relay to become healthy after starting

    Returns:
        True if relay is running and healthy, False otherwise
    """
    # First, check if relay is already running and healthy
    if await is_relay_healthy(host, port):
        logger.debug("Relay is already running and healthy")
        return True

    # Check pidfile for existing process
    existing_pid = read_pidfile()
    if existing_pid and is_process_running(existing_pid):
        # Process exists but not responding - wait a bit and retry
        logger.info(f"Relay process {existing_pid} exists, waiting for it to become healthy...")
        for _ in range(int(wait_timeout)):
            await asyncio.sleep(1)
            if await is_relay_healthy(host, port):
                return True
        logger.warning(f"Relay process {existing_pid} not responding, may need restart")
        return False

    # No relay running
    if not start_if_missing:
        logger.info("Relay not running and start_if_missing=False")
        return False

    # Clean up stale pidfile if exists
    if existing_pid:
        remove_pidfile()

    # Start the daemon
    logger.info("Starting relay daemon...")
    try:
        start_relay_daemon(host, port)
    except Exception as e:
        logger.error(f"Failed to start relay daemon: {e}")
        return False

    # Wait for it to become healthy
    for i in range(int(wait_timeout * 2)):  # Check every 0.5 seconds
        await asyncio.sleep(0.5)
        if await is_relay_healthy(host, port):
            logger.info("Relay daemon started successfully")
            return True

    logger.error(f"Relay daemon did not become healthy within {wait_timeout} seconds")
    return False


def stop_relay_daemon() -> bool:
    """
    Stop the relay daemon if it's running.

    Returns:
        True if daemon was stopped, False if it wasn't running
    """
    pid = read_pidfile()
    if not pid:
        logger.info("No relay daemon running (no pidfile)")
        return False

    if not is_process_running(pid):
        logger.info(f"Relay daemon (PID {pid}) not running, cleaning up pidfile")
        remove_pidfile()
        return False

    try:
        os.kill(pid, signal.SIGTERM)
        logger.info(f"Sent SIGTERM to relay daemon (PID {pid})")

        # Wait for process to exit
        for _ in range(10):
            if not is_process_running(pid):
                remove_pidfile()
                logger.info("Relay daemon stopped successfully")
                return True
            asyncio.get_event_loop().run_until_complete(asyncio.sleep(0.5))

        # Force kill if still running
        os.kill(pid, signal.SIGKILL)
        remove_pidfile()
        logger.info(f"Force killed relay daemon (PID {pid})")
        return True

    except (OSError, ProcessLookupError) as e:
        logger.error(f"Failed to stop relay daemon: {e}")
        remove_pidfile()
        return False


# =============================================================================
# Main Entry Points
# =============================================================================


async def run_as_daemon(
    host: str = DEFAULT_HOST,
    port: int = DEFAULT_PORT,
    auto_shutdown: bool = True,
    shutdown_timeout: int = AUTO_SHUTDOWN_TIMEOUT,
) -> None:
    """
    Run the relay server as a daemon (called by --daemon flag).

    Writes pidfile, sets up signal handlers, and runs until terminated
    or auto-shutdown due to inactivity.

    Args:
        host: Host to bind to
        port: Port to bind to
        auto_shutdown: Enable auto-shutdown after inactivity
        shutdown_timeout: Inactivity timeout in seconds (default: 5 minutes)
    """
    # Write pidfile
    write_pidfile(os.getpid())

    # Set up signal handlers for graceful shutdown
    shutdown_event = asyncio.Event()

    def handle_signal(sig: int, frame) -> None:
        logger.info(f"Received signal {sig}, shutting down...")
        shutdown_event.set()

    signal.signal(signal.SIGTERM, handle_signal)
    signal.signal(signal.SIGINT, handle_signal)

    # Create app with auto-shutdown enabled
    app = create_app(enable_auto_shutdown=auto_shutdown, shutdown_event=shutdown_event)

    # Start the server
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, host, port)
    await site.start()

    logger.info(f"Gobbler relay daemon started on http://{host}:{port}")
    if auto_shutdown:
        logger.info(f"Auto-shutdown enabled (timeout: {shutdown_timeout}s of inactivity)")

    # Start auto-shutdown monitor if enabled
    monitor_task = None
    if auto_shutdown:
        monitor_task = asyncio.create_task(auto_shutdown_monitor(shutdown_event, shutdown_timeout))

    try:
        # Wait for shutdown signal (from signal handler or auto-shutdown)
        await shutdown_event.wait()
    finally:
        logger.info("Cleaning up...")
        if monitor_task:
            monitor_task.cancel()
            try:
                await monitor_task
            except asyncio.CancelledError:
                pass
        await runner.cleanup()
        remove_pidfile()
        logger.info("Relay daemon stopped")


async def main() -> None:
    """Run relay server standalone (interactive mode)."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    runner = await start_relay_server()
    try:
        print("Relay server running. Press Ctrl+C to stop.")
        await asyncio.Event().wait()  # Run forever
    except KeyboardInterrupt:
        print("\nShutting down...")
    finally:
        await runner.cleanup()


def cli_main() -> None:
    """Command-line entry point with argument parsing."""
    import argparse

    parser = argparse.ArgumentParser(description="Gobbler Browser Extension Relay Server")
    parser.add_argument("--daemon", action="store_true", help="Run as background daemon")
    parser.add_argument(
        "--host", default=DEFAULT_HOST, help=f"Host to bind to (default: {DEFAULT_HOST})"
    )
    parser.add_argument(
        "--port", type=int, default=DEFAULT_PORT, help=f"Port to bind to (default: {DEFAULT_PORT})"
    )
    parser.add_argument("--stop", action="store_true", help="Stop the running daemon")
    parser.add_argument("--status", action="store_true", help="Check daemon status")
    parser.add_argument(
        "--no-auto-shutdown",
        action="store_true",
        help="Disable auto-shutdown (daemon will run until explicitly stopped)",
    )
    parser.add_argument(
        "--shutdown-timeout",
        type=int,
        default=AUTO_SHUTDOWN_TIMEOUT,
        help=f"Auto-shutdown timeout in seconds (default: {AUTO_SHUTDOWN_TIMEOUT})",
    )

    args = parser.parse_args()

    # Configure logging
    log_level = logging.WARNING if args.daemon else logging.INFO
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    if args.status:
        pid = read_pidfile()
        if pid and is_process_running(pid):
            print(f"Relay daemon is running (PID {pid})")
            # Check if healthy
            healthy = asyncio.run(is_relay_healthy(args.host, args.port))
            if healthy:
                print(f"Relay is healthy at http://{args.host}:{args.port}")
            else:
                print("Relay process exists but not responding to health checks")
        else:
            print("Relay daemon is not running")
        return

    if args.stop:
        if stop_relay_daemon():
            print("Relay daemon stopped")
        else:
            print("Relay daemon was not running")
        return

    if args.daemon:
        # Run as daemon with auto-shutdown
        asyncio.run(
            run_as_daemon(
                host=args.host,
                port=args.port,
                auto_shutdown=not args.no_auto_shutdown,
                shutdown_timeout=args.shutdown_timeout,
            )
        )
    else:
        # Run interactively (no auto-shutdown)
        asyncio.run(main())


if __name__ == "__main__":
    cli_main()
