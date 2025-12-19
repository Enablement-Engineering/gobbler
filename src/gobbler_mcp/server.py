"""Main MCP server implementation using FastMCP.

This module handles server lifecycle and tool registration.
Tool implementations are in the tools/ subpackage.
"""

import logging
from contextlib import asynccontextmanager

from fastmcp import FastMCP

from .config import get_config
from .logging_config import setup_logging
from .metrics_server import get_metrics_server
from .utils.health import ServiceHealth

# Import tool modules for registration
from .tools import conversion, batch, browser, queue, crawl

# Configure logging using structured logging setup
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler()],
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastMCP):  # type: ignore
    """
    Application lifespan manager.

    Handles initialization and cleanup of resources.
    """
    # Startup
    logger.info("Starting Gobbler MCP server...")
    config = get_config()
    logger.info(f"Configuration loaded from {config.config_path}")

    # Setup structured logging based on config
    log_format = config.get("monitoring.log_format", "text")
    log_level = config.get("monitoring.log_level", "INFO")
    setup_logging(level=log_level, format=log_format)
    logger.info(f"Logging configured: format={log_format}, level={log_level}")

    # Start metrics server if enabled
    metrics_enabled = config.get("monitoring.metrics_enabled", False)
    metrics_server = None
    if metrics_enabled:
        try:
            metrics_server = get_metrics_server()
            metrics_server.start()
            logger.info("Metrics collection enabled")
        except Exception as e:
            logger.warning(f"Failed to start metrics server: {e}")
            logger.warning("Continuing without metrics...")

    # Enable config hot-reload if configured
    hot_reload_enabled = config.get("monitoring.config_hot_reload", True)
    if hot_reload_enabled:
        try:
            config.enable_hot_reload()
        except Exception as e:
            logger.warning(f"Failed to enable config hot-reload: {e}")
            logger.warning("Continuing without hot-reload...")

    # Check service health at startup (don't fail if unavailable)
    # Note: Whisper runs locally via faster-whisper library, not as a service
    async with ServiceHealth() as health:
        service_urls = {
            "Crawl4AI": config.get_service_url("crawl4ai"),
            "Docling": config.get_service_url("docling"),
        }
        health_status = await health.check_all_services(service_urls)

        available = [name for name, status in health_status.items() if status]
        unavailable = [name for name, status in health_status.items() if not status]

        if available:
            logger.info(f"Available services: {', '.join(available)}")
        if unavailable:
            logger.warning(
                f"Unavailable services: {', '.join(unavailable)}. "
                "Some tools will not work until services are started."
            )

    # Ensure relay server is running for browser extension
    # Uses connect-or-start pattern: if relay is already running (from another
    # Claude Code instance), we just connect to it. Otherwise, we start it as a daemon.
    relay_enabled = config.get("http_server.enabled", True)
    if relay_enabled:
        try:
            from gobbler_relay import ensure_relay_running, DEFAULT_HOST, DEFAULT_PORT

            relay_host = config.get("http_server.host", DEFAULT_HOST)
            relay_port = config.get("http_server.port", DEFAULT_PORT)

            relay_ready = await ensure_relay_running(
                host=relay_host,
                port=relay_port,
                start_if_missing=True,
                wait_timeout=5.0,
            )

            if relay_ready:
                logger.info(f"Relay server ready at http://{relay_host}:{relay_port}")
            else:
                logger.warning("Relay server not available. Browser extension tools may not work.")
        except Exception as e:
            logger.warning(f"Failed to ensure relay server: {e}")
            logger.warning("Browser extension tools may not work...")

    logger.info("Gobbler MCP server started successfully")

    yield

    # Shutdown
    logger.info("Shutting down Gobbler MCP server...")

    # Note: Relay daemon continues running for other Claude Code instances
    # It will be stopped when the last user explicitly calls --stop or the system shuts down

    # Disable config hot-reload
    config.disable_hot_reload()

    # Stop metrics server if running
    if metrics_server and metrics_server.is_running():
        await metrics_server.stop()


# Initialize FastMCP server
mcp = FastMCP("gobbler-mcp", lifespan=lifespan)

# Register tools from modules
conversion.register_tools(mcp)
batch.register_tools(mcp)
browser.register_tools(mcp)
queue.register_tools(mcp)
crawl.register_tools(mcp)
