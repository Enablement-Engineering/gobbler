"""HTTP server for Prometheus metrics endpoint."""

import asyncio
import logging
import threading
from typing import Optional

from aiohttp import web

from .metrics import get_metrics

logger = logging.getLogger(__name__)


async def metrics_handler(request: web.Request) -> web.Response:
    """
    Handle /metrics endpoint for Prometheus scraping.

    Args:
        request: aiohttp request object

    Returns:
        Response with Prometheus metrics
    """
    try:
        metrics_data, content_type_full = get_metrics()
        # Extract just the content type without charset for aiohttp
        # Prometheus returns "text/plain; version=X.X.X; charset=utf-8"
        # aiohttp wants content_type without charset (charset is separate param)
        content_type = content_type_full.split(";")[0].strip()
        return web.Response(
            body=metrics_data,
            content_type=content_type,
            charset="utf-8"
        )
    except Exception as e:
        logger.error(f"Error generating metrics: {e}")
        return web.Response(
            text="Error generating metrics", status=500
        )


async def health_handler(request: web.Request) -> web.Response:
    """
    Handle /health endpoint for health checks.

    Args:
        request: aiohttp request object

    Returns:
        JSON response with health status
    """
    return web.json_response({"status": "healthy", "service": "gobbler-mcp"})


def create_metrics_app() -> web.Application:
    """
    Create aiohttp application for metrics server.

    Returns:
        Configured aiohttp Application
    """
    app = web.Application()
    app.router.add_get("/metrics", metrics_handler)
    app.router.add_get("/health", health_handler)
    return app


class MetricsServer:
    """Metrics HTTP server manager."""

    def __init__(self, host: str = "0.0.0.0", port: int = 9090):
        """
        Initialize metrics server.

        Args:
            host: Host to bind to
            port: Port to bind to
        """
        self.host = host
        self.port = port
        self.runner: Optional[web.AppRunner] = None
        self.site: Optional[web.TCPSite] = None
        self._thread: Optional[threading.Thread] = None
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._stop_event: Optional[threading.Event] = None

    async def _run_server(self) -> None:
        """Run the metrics server (internal async method)."""
        try:
            app = create_metrics_app()
            self.runner = web.AppRunner(app)
            await self.runner.setup()

            self.site = web.TCPSite(self.runner, self.host, self.port)
            await self.site.start()

            logger.info(f"Metrics server started on http://{self.host}:{self.port}")
            logger.info(f"  - Metrics: http://{self.host}:{self.port}/metrics")
            logger.info(f"  - Health:  http://{self.host}:{self.port}/health")

            # Wait for stop signal
            if self._stop_event:
                while not self._stop_event.is_set():
                    await asyncio.sleep(0.1)

        except Exception as e:
            logger.error(f"Metrics server error: {e}")
            raise

    def _run_in_thread(self) -> None:
        """Run server in background thread with its own event loop."""
        # Create new event loop for this thread
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)

        try:
            self._loop.run_until_complete(self._run_server())
        except Exception as e:
            logger.error(f"Metrics server thread error: {e}")
        finally:
            # Cleanup
            if self._loop and not self._loop.is_closed():
                self._loop.close()

    def start(self) -> None:
        """Start metrics server in background thread."""
        if self._thread and self._thread.is_alive():
            logger.warning("Metrics server already running")
            return

        self._stop_event = threading.Event()
        self._thread = threading.Thread(target=self._run_in_thread, daemon=True)
        self._thread.start()

        # Give server a moment to start
        import time

        time.sleep(0.5)

    async def stop(self) -> None:
        """Stop the metrics server."""
        if not self._thread or not self._thread.is_alive():
            return

        logger.info("Stopping metrics server...")

        # Signal thread to stop
        if self._stop_event:
            self._stop_event.set()

        # Cleanup aiohttp resources
        if self.site:
            await self.site.stop()

        if self.runner:
            await self.runner.cleanup()

        # Wait for thread to finish (with timeout)
        if self._thread:
            self._thread.join(timeout=2.0)

        logger.info("Metrics server stopped")

    def is_running(self) -> bool:
        """
        Check if metrics server is running.

        Returns:
            True if server is running
        """
        return self._thread is not None and self._thread.is_alive()


# Global server instance
_metrics_server: Optional[MetricsServer] = None


def get_metrics_server() -> MetricsServer:
    """
    Get global metrics server instance.

    Returns:
        MetricsServer instance
    """
    global _metrics_server
    if _metrics_server is None:
        from .config import get_config

        config = get_config()
        host = config.get("monitoring.metrics_host", "0.0.0.0")
        port = config.get("monitoring.metrics_port", 9090)
        _metrics_server = MetricsServer(host, port)
    return _metrics_server
