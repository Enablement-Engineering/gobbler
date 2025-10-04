"""Configuration file watcher for hot-reload functionality."""

import logging
import time
from pathlib import Path
from typing import Any, Callable, Dict, Optional

from watchdog.events import FileSystemEvent, FileSystemEventHandler
from watchdog.observers import Observer

logger = logging.getLogger(__name__)


class ConfigFileHandler(FileSystemEventHandler):
    """File system event handler for configuration file changes."""

    def __init__(
        self,
        config_path: Path,
        on_change_callback: Callable[[], None],
        debounce_seconds: float = 1.0,
    ) -> None:
        """
        Initialize config file handler.

        Args:
            config_path: Path to config file to watch
            on_change_callback: Callback to invoke when file changes
            debounce_seconds: Minimum time between reload triggers
        """
        self.config_path = config_path
        self.on_change_callback = on_change_callback
        self.debounce_seconds = debounce_seconds
        self.last_reload_time = 0.0

    def on_modified(self, event: FileSystemEvent) -> None:
        """
        Handle file modification events.

        Args:
            event: File system event
        """
        # Only react to our config file
        if event.is_directory:
            return

        event_path = Path(event.src_path).resolve()
        if event_path != self.config_path.resolve():
            return

        # Debounce: ignore if too soon after last reload
        current_time = time.time()
        if current_time - self.last_reload_time < self.debounce_seconds:
            logger.debug(
                f"Ignoring config change (debounce): {current_time - self.last_reload_time:.2f}s since last reload"
            )
            return

        logger.info(f"Config file changed: {self.config_path}")
        self.last_reload_time = current_time

        # Trigger reload
        try:
            self.on_change_callback()
        except Exception as e:
            logger.error(f"Error in config reload callback: {e}", exc_info=True)


class ConfigWatcher:
    """Watches configuration file and triggers hot-reload on changes."""

    # Validation rules for config values
    VALID_WHISPER_MODELS = ["tiny", "base", "small", "medium", "large"]
    TIMEOUT_MIN = 5
    TIMEOUT_MAX = 300
    PORT_MIN = 1
    PORT_MAX = 65535
    QUEUE_THRESHOLD_MIN = 0
    QUEUE_THRESHOLD_MAX = 3600

    def __init__(
        self,
        config_path: Path,
        reload_callback: Callable[[], None],
        debounce_seconds: float = 1.0,
    ) -> None:
        """
        Initialize config watcher.

        Args:
            config_path: Path to config file to watch
            reload_callback: Callback to invoke when config should reload
            debounce_seconds: Minimum time between reload triggers
        """
        self.config_path = config_path
        self.reload_callback = reload_callback
        self.debounce_seconds = debounce_seconds

        self.observer: Optional[Observer] = None
        self.handler: Optional[ConfigFileHandler] = None

    def start(self) -> None:
        """Start watching configuration file for changes."""
        if self.observer and self.observer.is_alive():
            logger.warning("Config watcher already running")
            return

        # Ensure config file exists
        if not self.config_path.exists():
            logger.warning(
                f"Config file does not exist: {self.config_path}. Watcher will not start."
            )
            return

        # Create handler and observer
        self.handler = ConfigFileHandler(
            config_path=self.config_path,
            on_change_callback=self.reload_callback,
            debounce_seconds=self.debounce_seconds,
        )

        self.observer = Observer()
        # Watch the directory containing the config file
        watch_dir = self.config_path.parent
        self.observer.schedule(self.handler, str(watch_dir), recursive=False)
        self.observer.start()

        logger.info(f"Config hot-reload enabled: watching {self.config_path}")

    def stop(self) -> None:
        """Stop watching configuration file."""
        if self.observer and self.observer.is_alive():
            self.observer.stop()
            self.observer.join(timeout=5.0)
            logger.info("Config hot-reload disabled")

    def is_running(self) -> bool:
        """
        Check if watcher is running.

        Returns:
            True if observer is alive, False otherwise
        """
        return self.observer is not None and self.observer.is_alive()

    @classmethod
    def validate_config(cls, config: Dict[str, Any]) -> list[str]:
        """
        Validate configuration values.

        Args:
            config: Configuration dictionary to validate

        Returns:
            List of validation error messages (empty if valid)
        """
        errors = []

        # Validate Whisper model
        whisper_model = config.get("whisper", {}).get("model")
        if whisper_model and whisper_model not in cls.VALID_WHISPER_MODELS:
            errors.append(
                f"Invalid whisper.model: '{whisper_model}'. "
                f"Must be one of {cls.VALID_WHISPER_MODELS}"
            )

        # Validate timeouts
        crawl_timeout = config.get("crawl4ai", {}).get("timeout")
        if crawl_timeout and not (cls.TIMEOUT_MIN <= crawl_timeout <= cls.TIMEOUT_MAX):
            errors.append(
                f"Invalid crawl4ai.timeout: {crawl_timeout}. "
                f"Must be between {cls.TIMEOUT_MIN} and {cls.TIMEOUT_MAX}"
            )

        crawl_max_timeout = config.get("crawl4ai", {}).get("max_timeout")
        if crawl_max_timeout and not (
            cls.TIMEOUT_MIN <= crawl_max_timeout <= cls.TIMEOUT_MAX
        ):
            errors.append(
                f"Invalid crawl4ai.max_timeout: {crawl_max_timeout}. "
                f"Must be between {cls.TIMEOUT_MIN} and {cls.TIMEOUT_MAX}"
            )

        # Validate ports
        for service_name in ["crawl4ai", "docling", "whisper"]:
            port = config.get("services", {}).get(service_name, {}).get("port")
            if port is not None and not (cls.PORT_MIN <= port <= cls.PORT_MAX):
                errors.append(
                    f"Invalid services.{service_name}.port: {port}. "
                    f"Must be between {cls.PORT_MIN} and {cls.PORT_MAX}"
                )

        redis_port = config.get("redis", {}).get("port")
        if redis_port is not None and not (cls.PORT_MIN <= redis_port <= cls.PORT_MAX):
            errors.append(
                f"Invalid redis.port: {redis_port}. "
                f"Must be between {cls.PORT_MIN} and {cls.PORT_MAX}"
            )

        # Validate queue threshold
        queue_threshold = config.get("queue", {}).get("auto_queue_threshold")
        if queue_threshold and not (
            cls.QUEUE_THRESHOLD_MIN <= queue_threshold <= cls.QUEUE_THRESHOLD_MAX
        ):
            errors.append(
                f"Invalid queue.auto_queue_threshold: {queue_threshold}. "
                f"Must be between {cls.QUEUE_THRESHOLD_MIN} and {cls.QUEUE_THRESHOLD_MAX}"
            )

        # Validate metrics port
        metrics_port = config.get("monitoring", {}).get("metrics_port")
        if metrics_port is not None and not (cls.PORT_MIN <= metrics_port <= cls.PORT_MAX):
            errors.append(
                f"Invalid monitoring.metrics_port: {metrics_port}. "
                f"Must be between {cls.PORT_MIN} and {cls.PORT_MAX}"
            )

        # Validate log format
        log_format = config.get("monitoring", {}).get("log_format")
        if log_format and log_format not in ["text", "json"]:
            errors.append(
                f"Invalid monitoring.log_format: '{log_format}'. Must be 'text' or 'json'"
            )

        # Validate log level
        log_level = config.get("monitoring", {}).get("log_level")
        valid_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        if log_level and log_level not in valid_levels:
            errors.append(
                f"Invalid monitoring.log_level: '{log_level}'. Must be one of {valid_levels}"
            )

        return errors
