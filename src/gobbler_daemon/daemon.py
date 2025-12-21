"""Main daemon class for Gobbler.

Manages daemon lifecycle, signal handling, PID file management,
and coordinates all services (event bus, health monitor, plugins, storage).
"""

import asyncio
import logging
import os
import signal
import sys
from pathlib import Path
from typing import Optional

from .config import DaemonConfig
from .events import EventBus, EventType, Event
from .health import HealthMonitor
from .plugins import PluginManager
from .storage import JobStorage

logger = logging.getLogger(__name__)


class GobblerDaemon:
    """
    Main daemon process for Gobbler.

    Manages all Gobbler services and provides lifecycle management
    (start/stop/status) with PID file tracking and signal handling.
    """

    def __init__(self, config: Optional[DaemonConfig] = None) -> None:
        """
        Initialize Gobbler daemon.

        Args:
            config: Configuration instance. If None, loads default config.
        """
        self.config = config or DaemonConfig()

        # Core components
        self.event_bus = EventBus()
        self.health_monitor = HealthMonitor(
            check_interval=self.config.get("monitoring.health_check_interval", 60),
            timeout=5.0,
            cache_ttl=30,
        )
        self.plugin_manager = PluginManager(
            plugins_directory=self.config.get("plugins.directory")
        )
        self.job_storage = JobStorage()

        # State
        self._running = False
        self._shutdown_event: Optional[asyncio.Event] = None
        self._tasks: list[asyncio.Task] = []

    async def start(self) -> None:
        """
        Start the daemon and all services.

        This starts the event bus, health monitor, plugin manager,
        and job storage. Sets up signal handlers for graceful shutdown.
        """
        if self._running:
            logger.warning("Daemon already running")
            return

        logger.info("Starting Gobbler daemon...")

        # Write PID file
        self._write_pidfile()

        # Set up signal handlers
        self._setup_signal_handlers()

        # Create shutdown event
        self._shutdown_event = asyncio.Event()

        try:
            # Start core services
            await self.event_bus.start()
            logger.info("Event bus started")

            await self.job_storage.start()
            logger.info("Job storage started")

            # Start plugin manager if enabled
            if self.config.get("plugins.enabled", True):
                await self.plugin_manager.start()
                logger.info("Plugin manager started")

            # Build service URLs for health monitoring
            service_urls = {}
            if self.config.is_service_enabled("crawl4ai"):
                service_urls["crawl4ai"] = self.config.get_service_url("crawl4ai")
            if self.config.is_service_enabled("docling"):
                service_urls["docling"] = self.config.get_service_url("docling")
            if self.config.is_service_enabled("redis"):
                service_urls["redis"] = self.config.get_service_url("redis")

            # Start health monitor
            await self.health_monitor.start(service_urls)
            logger.info("Health monitor started")

            # Enable config hot-reload if configured
            if self.config.get("monitoring.config_hot_reload", True):
                self.config.enable_hot_reload()
                logger.info("Config hot-reload enabled")

            self._running = True

            # Emit daemon started event
            await self.event_bus.publish(
                Event(
                    type=EventType.DAEMON_STARTED,
                    data={"pid": os.getpid()},
                    source="daemon",
                )
            )

            logger.info(
                f"Gobbler daemon started (PID: {os.getpid()}, "
                f"port: {self.config.get('daemon.port', 4600)})"
            )

        except Exception as e:
            logger.error(f"Failed to start daemon: {e}", exc_info=True)
            await self.stop()
            raise

    async def stop(self) -> None:
        """
        Stop the daemon and all services gracefully.

        Stops all services in reverse order, cancels tasks,
        and removes PID file.
        """
        if not self._running:
            logger.info("Daemon not running")
            return

        logger.info("Stopping Gobbler daemon...")

        # Emit daemon stopping event
        if self.event_bus._running:
            await self.event_bus.publish(
                Event(
                    type=EventType.DAEMON_STOPPING,
                    data={"pid": os.getpid()},
                    source="daemon",
                )
            )

        self._running = False

        try:
            # Cancel all running tasks
            for task in self._tasks:
                if not task.done():
                    task.cancel()
                    try:
                        await task
                    except asyncio.CancelledError:
                        pass

            self._tasks.clear()

            # Stop services in reverse order
            self.config.disable_hot_reload()
            logger.info("Config hot-reload disabled")

            await self.health_monitor.stop()
            logger.info("Health monitor stopped")

            await self.plugin_manager.stop()
            logger.info("Plugin manager stopped")

            await self.job_storage.stop()
            logger.info("Job storage stopped")

            # Emit daemon stopped event before stopping event bus
            await self.event_bus.publish(
                Event(
                    type=EventType.DAEMON_STOPPED,
                    data={"pid": os.getpid()},
                    source="daemon",
                )
            )

            # Give event bus time to distribute final events
            await asyncio.sleep(0.1)

            await self.event_bus.stop()
            logger.info("Event bus stopped")

        except Exception as e:
            logger.error(f"Error during daemon shutdown: {e}", exc_info=True)

        finally:
            # Remove PID file
            self._remove_pidfile()

            logger.info("Gobbler daemon stopped")

    async def run(self) -> None:
        """
        Run the daemon until shutdown signal received.

        This is the main entry point for running the daemon.
        It starts all services and waits for a shutdown signal.
        """
        await self.start()

        try:
            # Wait for shutdown signal
            if self._shutdown_event:
                await self._shutdown_event.wait()
        except KeyboardInterrupt:
            logger.info("Received keyboard interrupt")
        finally:
            await self.stop()

    def _setup_signal_handlers(self) -> None:
        """Set up signal handlers for graceful shutdown."""

        def handle_signal(sig: int) -> None:
            signame = signal.Signals(sig).name
            logger.info(f"Received signal {signame}, initiating shutdown...")
            if self._shutdown_event:
                self._shutdown_event.set()

        # Handle SIGTERM and SIGINT
        loop = asyncio.get_event_loop()

        for sig in (signal.SIGTERM, signal.SIGINT):
            loop.add_signal_handler(sig, lambda s=sig: handle_signal(s))

        logger.debug("Signal handlers configured")

    def _write_pidfile(self) -> None:
        """Write the current process ID to the PID file."""
        pid_file = Path(self.config.get("daemon.pid_file")).expanduser()
        pid_file.parent.mkdir(parents=True, exist_ok=True)

        pid = os.getpid()
        pid_file.write_text(str(pid))

        logger.info(f"Wrote PID {pid} to {pid_file}")

    def _remove_pidfile(self) -> None:
        """Remove the PID file."""
        pid_file = Path(self.config.get("daemon.pid_file")).expanduser()

        try:
            pid_file.unlink(missing_ok=True)
            logger.info(f"Removed PID file {pid_file}")
        except OSError as e:
            logger.warning(f"Failed to remove PID file: {e}")

    @staticmethod
    def get_pidfile_path(config: Optional[DaemonConfig] = None) -> Path:
        """
        Get the path to the PID file.

        Args:
            config: Configuration instance

        Returns:
            Path to PID file
        """
        if config is None:
            config = DaemonConfig()

        return Path(config.get("daemon.pid_file")).expanduser()

    @staticmethod
    def read_pidfile(config: Optional[DaemonConfig] = None) -> Optional[int]:
        """
        Read the PID from the PID file.

        Args:
            config: Configuration instance

        Returns:
            PID if file exists and is valid, None otherwise
        """
        pid_file = GobblerDaemon.get_pidfile_path(config)

        if not pid_file.exists():
            return None

        try:
            return int(pid_file.read_text().strip())
        except (ValueError, OSError):
            return None

    @staticmethod
    def is_running(config: Optional[DaemonConfig] = None) -> bool:
        """
        Check if daemon is running.

        Args:
            config: Configuration instance

        Returns:
            True if daemon is running
        """
        pid = GobblerDaemon.read_pidfile(config)

        if pid is None:
            return False

        # Check if process exists
        try:
            os.kill(pid, 0)
            return True
        except (OSError, ProcessLookupError):
            return False

    @staticmethod
    async def get_status(config: Optional[DaemonConfig] = None) -> dict:
        """
        Get daemon status.

        Args:
            config: Configuration instance

        Returns:
            Status dictionary with running state and PID
        """
        pid = GobblerDaemon.read_pidfile(config)
        running = GobblerDaemon.is_running(config)

        return {
            "running": running,
            "pid": pid if running else None,
        }


async def main() -> None:
    """Main entry point for running the daemon."""
    # Configure logging
    log_level = os.environ.get("LOG_LEVEL", "INFO")
    logging.basicConfig(
        level=getattr(logging, log_level),
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    # Create and run daemon
    daemon = GobblerDaemon()

    try:
        await daemon.run()
    except Exception as e:
        logger.error(f"Fatal error in daemon: {e}", exc_info=True)
        sys.exit(1)


def main_sync() -> None:
    """Synchronous entry point for running the daemon."""
    asyncio.run(main())


if __name__ == "__main__":
    main_sync()
