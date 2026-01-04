#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["httpx>=0.27.0"]
# ///
"""HTTP client for Gobbler browser relay.

Used by skills/scripts to communicate with the browser extension
via the relay server's /command endpoint.

Features smart detection to check if relay is already running.
"""

import asyncio
import socket

import httpx

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 4625


def get_relay_url(host: str = DEFAULT_HOST, port: int = DEFAULT_PORT) -> str:
    """Get the base URL for the relay server."""
    return f"http://{host}:{port}"


def is_port_in_use(port: int = DEFAULT_PORT, host: str = DEFAULT_HOST) -> bool:
    """Check if a port is in use (relay might be running).

    Args:
        port: Port to check
        host: Host to check

    Returns:
        True if port is in use, False otherwise
    """
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        try:
            s.settimeout(1)
            s.connect((host, port))
        except (ConnectionRefusedError, TimeoutError, OSError):
            return False
        else:
            return True


async def is_relay_running(
    host: str = DEFAULT_HOST, port: int = DEFAULT_PORT, timeout: float = 2.0
) -> bool:
    """Check if the relay server is running and healthy.

    Args:
        host: Relay host
        port: Relay port
        timeout: Request timeout in seconds

    Returns:
        True if relay is running and responding, False otherwise
    """
    http_ok = 200
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.get(f"{get_relay_url(host, port)}/health")
            return response.status_code == http_ok
    except (httpx.ConnectError, httpx.TimeoutException):
        return False


async def ensure_relay_running(
    host: str = DEFAULT_HOST, port: int = DEFAULT_PORT, timeout: float = 5.0
) -> bool:
    """Ensure the relay server is running, starting it if necessary.

    This function checks if the relay is healthy, and if not, starts
    the relay daemon and waits for it to become available.

    Args:
        host: Relay host
        port: Relay port
        timeout: How long to wait for relay to become healthy after starting

    Returns:
        True if relay is running and healthy

    Raises:
        RuntimeError: If relay failed to start within the timeout period
    """
    # Check if relay is already running
    if await is_relay_running(host, port):
        return True

    # Lazy import to avoid circular imports
    from gobbler_relay.relay import start_relay_daemon

    # Start the relay daemon
    start_relay_daemon(host, port)

    # Wait for relay to become healthy
    start_time = asyncio.get_event_loop().time()
    while (asyncio.get_event_loop().time() - start_time) < timeout:
        await asyncio.sleep(0.25)
        if await is_relay_running(host, port):
            return True

    msg = (
        f"Failed to start relay server within {timeout} seconds. Check if port {port} is available."
    )
    raise RuntimeError(msg)


async def get_connection_count(host: str = DEFAULT_HOST, port: int = DEFAULT_PORT) -> int:
    """Get the number of connected browser extensions.

    Args:
        host: Relay host
        port: Relay port

    Returns:
        Number of connected WebSocket clients

    Raises:
        RuntimeError: If relay is not running
    """
    async with httpx.AsyncClient(timeout=5) as client:
        try:
            response = await client.get(f"{get_relay_url(host, port)}/health")
            response.raise_for_status()
            data = response.json()
            return data.get("websocket_connections", 0)
        except httpx.ConnectError as err:
            msg = "Relay server is not running"
            raise RuntimeError(msg) from err


async def send_command(
    command: str,
    params: dict | None = None,
    timeout: float = 30.0,
    host: str = DEFAULT_HOST,
    port: int = DEFAULT_PORT,
) -> dict:
    """Send a command to the browser extension via the relay.

    Args:
        command: Command name (e.g., "navigate", "execute_script", "extract_page")
        params: Optional parameters for the command
        timeout: Timeout in seconds for command execution
        host: Relay host
        port: Relay port

    Returns:
        Response from the browser extension

    Raises:
        RuntimeError: If relay is not running or no extension connected
        httpx.HTTPStatusError: If command fails
    """
    url = f"{get_relay_url(host, port)}/command"

    # Use a longer client timeout than command timeout to allow for relay overhead
    client_timeout = timeout + 5

    async with httpx.AsyncClient(timeout=client_timeout) as client:
        try:
            response = await client.post(
                url,
                json={
                    "command": command,
                    "params": params or {},
                    "timeout": timeout,
                },
            )

            http_unavailable = 503
            if response.status_code == http_unavailable:
                # Service unavailable - likely no extension connected
                error_data = response.json()
                raise RuntimeError(error_data.get("error", "Service unavailable"))

            response.raise_for_status()
            return response.json()

        except httpx.ConnectError as err:
            msg = (
                f"Cannot connect to relay at {get_relay_url(host, port)}. "
                "Is the relay server running?"
            )
            raise RuntimeError(msg) from err


# Convenience functions for common commands


async def check_connection(host: str = DEFAULT_HOST, port: int = DEFAULT_PORT) -> dict:
    """Check relay and extension connection status."""
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            response = await client.get(f"{get_relay_url(host, port)}/health")
            response.raise_for_status()
            return response.json()
    except httpx.ConnectError:
        return {"status": "error", "message": "Relay not running"}


async def navigate(url: str, host: str = DEFAULT_HOST, port: int = DEFAULT_PORT) -> dict:
    """Navigate browser to URL."""
    return await send_command("navigate", {"url": url}, host=host, port=port)


async def extract_page(
    selector: str | None = None,
    tab_id: int | None = None,
    host: str = DEFAULT_HOST,
    port: int = DEFAULT_PORT,
) -> dict:
    """Extract current page as markdown.

    Args:
        selector: Optional CSS selector to extract specific content
        tab_id: Optional tab ID to extract from a specific tab
        host: Relay host
        port: Relay port

    Returns:
        Response from the browser extension with extracted content
    """
    params = {}
    if selector:
        params["selector"] = selector
    if tab_id is not None:
        params["tabId"] = tab_id
    return await send_command("extract_page", params, host=host, port=port)


async def execute_script(
    script: str,
    timeout: float = 30.0,
    host: str = DEFAULT_HOST,
    port: int = DEFAULT_PORT,
) -> dict:
    """Execute JavaScript in active tab."""
    return await send_command(
        "execute_script", {"script": script}, timeout=timeout, host=host, port=port
    )


async def list_tabs(
    filter_type: str | None = None,
    host: str = DEFAULT_HOST,
    port: int = DEFAULT_PORT,
) -> dict:
    """List tabs in Gobbler group."""
    params = {}
    if filter_type:
        params["filter"] = filter_type
    return await send_command("list_gobbler_tabs", params, host=host, port=port)


async def open_tabs(
    urls: list[str],
    host: str = DEFAULT_HOST,
    port: int = DEFAULT_PORT,
) -> dict:
    """Open multiple URLs in new browser tabs.

    Args:
        urls: List of URLs to open
        host: Relay host
        port: Relay port

    Returns:
        Response from the browser extension
    """
    return await send_command("open_tabs", {"urls": urls}, host=host, port=port)


async def execute_script_in_tab(
    tab_id: int,
    script: str,
    timeout: float = 30.0,
    host: str = DEFAULT_HOST,
    port: int = DEFAULT_PORT,
) -> dict:
    """Execute JavaScript in a specific tab."""
    return await send_command(
        "execute_script_in_tab",
        {"tabId": tab_id, "script": script},
        timeout=timeout,
        host=host,
        port=port,
    )


async def inject_api(
    tab_id: int,
    host: str = DEFAULT_HOST,
    port: int = DEFAULT_PORT,
) -> dict:
    """Manually inject page API into a specific tab.

    Args:
        tab_id: Tab ID to inject API into
        host: Relay host
        port: Relay port

    Returns:
        Response from the browser extension with injection result
    """
    return await send_command("inject_api", {"tabId": tab_id}, host=host, port=port)


async def get_injected_apis(
    host: str = DEFAULT_HOST,
    port: int = DEFAULT_PORT,
) -> dict:
    """Get information about injected APIs in Gobbler tabs.

    Args:
        host: Relay host
        port: Relay port

    Returns:
        Response with tabs and their API injection status
    """
    return await send_command("get_injected_apis", {}, host=host, port=port)
