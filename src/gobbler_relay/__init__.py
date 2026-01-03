"""Gobbler Browser Extension Relay.

This package provides HTTP and WebSocket relay functionality for
communication between Claude/skills and the Gobbler browser extension.

Usage:
    # Ensure relay is running (auto-starts daemon if needed)
    from gobbler_relay import ensure_relay_running
    await ensure_relay_running()

    # Send commands via HTTP client (recommended for skills)
    from gobbler_relay.client import send_command, execute_script, list_tabs
    result = await execute_script("document.title")
    tabs = await list_tabs(filter_type="notebooklm")

    # Direct WebSocket (for in-process use, e.g., tests)
    from gobbler_relay import start_relay_server, send_command_to_extension
    relay = await start_relay_server()
    result = await send_command_to_extension("navigate", {"url": "https://example.com"})

    # CLI commands:
    #   python -m gobbler_relay.relay              # Run interactively
    #   python -m gobbler_relay.relay --daemon     # Run as daemon
    #   python -m gobbler_relay.relay --status     # Check status
    #   python -m gobbler_relay.relay --stop       # Stop daemon
"""

from gobbler_relay.relay import (
    DEFAULT_HOST,
    DEFAULT_PORT,
    create_app,
    ensure_relay_running,
    is_relay_healthy,
    pending_commands,
    send_command_to_extension,
    start_relay_daemon,
    start_relay_server,
    stop_relay_daemon,
    websocket_connections,
)

__all__ = [
    "DEFAULT_HOST",
    "DEFAULT_PORT",
    "create_app",
    "ensure_relay_running",
    "is_relay_healthy",
    "pending_commands",
    "send_command_to_extension",
    "start_relay_daemon",
    "start_relay_server",
    "stop_relay_daemon",
    "websocket_connections",
]
