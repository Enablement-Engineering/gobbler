"""Configuration management for Gobbler Daemon.

Provides unified configuration loading from ~/.config/gobbler/config.yml
with hot-reload support using watchdog.
"""

import logging
import threading
from pathlib import Path
from typing import Any, Dict, Optional

import yaml
from watchdog.events import FileSystemEvent, FileSystemEventHandler
from watchdog.observers import Observer

logger = logging.getLogger(__name__)


class ConfigFileHandler(FileSystemEventHandler):
    """File system event handler for configuration file changes."""

    def __init__(
        self,
        config_path: Path,
        on_change_callback: callable,
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
        """Handle file modification events."""
        import time

        if event.is_directory:
            return

        event_path = Path(event.src_path).resolve()
        if event_path != self.config_path.resolve():
            return

        # Debounce: ignore if too soon after last reload
        current_time = time.time()
        if current_time - self.last_reload_time < self.debounce_seconds:
            logger.debug(
                f"Ignoring config change (debounce): "
                f"{current_time - self.last_reload_time:.2f}s since last reload"
            )
            return

        logger.info(f"Config file changed: {self.config_path}")
        self.last_reload_time = current_time

        # Trigger reload
        try:
            self.on_change_callback()
        except Exception as e:
            logger.error(f"Error in config reload callback: {e}", exc_info=True)


class DaemonConfig:
    """Configuration loader and manager for Gobbler Daemon."""

    # Default configuration
    DEFAULTS: Dict[str, Any] = {
        "daemon": {
            "host": "127.0.0.1",
            "port": 4600,
            "auto_start": True,
            "log_level": "INFO",
            "pid_file": "~/.cache/gobbler/daemon.pid",
            "log_file": "~/.cache/gobbler/daemon.log",
        },
        "api": {
            "enabled": True,
            "auth": {
                "enabled": False,
                "api_keys": [],
            },
        },
        "mcp": {
            "enabled": True,
            "transport": "stdio",
        },
        "converters": {
            "youtube": {"enabled": True, "providers": ["official", "transcriptapi"]},
            "audio": {"enabled": True, "model": "small"},
            "document": {"enabled": True, "ocr": True},
            "webpage": {"enabled": True, "timeout": 30},
        },
        "services": {
            "crawl4ai": {
                "enabled": True,
                "host": "localhost",
                "port": 11235,
                "api_token": "gobbler-local-token",
            },
            "docling": {
                "enabled": True,
                "host": "localhost",
                "port": 5001,
            },
            "redis": {
                "enabled": True,
                "host": "localhost",
                "port": 6380,
                "db": 0,
            },
        },
        "plugins": {
            "directory": "~/.config/gobbler/plugins",
            "enabled": True,
        },
        "monitoring": {
            "health_check_interval": 60,
            "config_hot_reload": True,
        },
    }

    def __init__(self, config_path: Optional[Path] = None) -> None:
        """
        Initialize configuration.

        Args:
            config_path: Path to config file. If None, uses default location.
        """
        self.config_path = config_path or self._default_config_path()
        self._lock = threading.RLock()
        self._observer: Optional[Observer] = None
        self._handler: Optional[ConfigFileHandler] = None
        self.data = self._load_config()

    @staticmethod
    def _default_config_path() -> Path:
        """Get default configuration file path."""
        return Path.home() / ".config" / "gobbler" / "config.yml"

    def _load_config(self) -> Dict[str, Any]:
        """
        Load configuration from file, falling back to defaults.

        Returns:
            Configuration dictionary
        """
        # Start with defaults
        config = self._deep_copy(self.DEFAULTS)

        # Try to load user config
        if self.config_path.exists():
            try:
                with open(self.config_path, "r") as f:
                    user_config = yaml.safe_load(f)
                    if user_config:
                        # Deep merge user config over defaults
                        config = self._deep_merge(config, user_config)
                        logger.info(f"Loaded configuration from {self.config_path}")
            except Exception as e:
                logger.warning(f"Failed to load config from {self.config_path}: {e}")
                logger.info("Using default configuration")
        else:
            logger.info(f"No config file found at {self.config_path}, using defaults")

        # Expand ~ in paths
        config = self._expand_paths(config)

        return config

    @staticmethod
    def _deep_copy(data: Dict[str, Any]) -> Dict[str, Any]:
        """Deep copy a dictionary."""
        import copy

        return copy.deepcopy(data)

    @staticmethod
    def _deep_merge(base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
        """
        Deep merge two dictionaries.

        Args:
            base: Base dictionary
            override: Dictionary to merge over base

        Returns:
            Merged dictionary
        """
        result = base.copy()
        for key, value in override.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = DaemonConfig._deep_merge(result[key], value)
            else:
                result[key] = value
        return result

    def _expand_paths(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """
        Expand ~ in path values recursively.

        Args:
            config: Configuration dictionary

        Returns:
            Configuration with expanded paths
        """
        result = {}
        for key, value in config.items():
            if isinstance(value, dict):
                result[key] = self._expand_paths(value)
            elif isinstance(value, str) and ("_file" in key or "_directory" in key or key == "models_path"):
                result[key] = str(Path(value).expanduser())
            else:
                result[key] = value
        return result

    def get(self, key: str, default: Any = None) -> Any:
        """
        Get configuration value using dot notation (thread-safe).

        Args:
            key: Configuration key (e.g., "daemon.port")
            default: Default value if key not found

        Returns:
            Configuration value
        """
        with self._lock:
            keys = key.split(".")
            value = self.data
            for k in keys:
                if isinstance(value, dict) and k in value:
                    value = value[k]
                else:
                    return default
            return value

    def get_service_url(self, service: str) -> str:
        """
        Get full service URL.

        Args:
            service: Service name (crawl4ai, docling, redis)

        Returns:
            Full URL for service
        """
        host = self.get(f"services.{service}.host", "localhost")
        port = self.get(f"services.{service}.port")

        if service == "redis":
            return f"redis://{host}:{port}"
        else:
            return f"http://{host}:{port}"

    def is_service_enabled(self, service: str) -> bool:
        """
        Check if a service is enabled.

        Args:
            service: Service name

        Returns:
            True if service is enabled
        """
        return self.get(f"services.{service}.enabled", False)

    def reload(self) -> None:
        """
        Reload configuration from file (thread-safe).

        Validates new config before applying. If validation fails,
        keeps current config and logs errors.
        """
        with self._lock:
            try:
                new_config = self._load_config()
            except Exception as e:
                logger.error(f"Failed to load config during reload: {e}")
                return

            # Detect changes
            changes = self._detect_changes(self.data, new_config)

            # Apply new config atomically
            self.data = new_config

            # Log reload success
            if changes:
                logger.info(
                    f"Configuration reloaded successfully. Changes:\n"
                    + "\n".join(f"  - {change}" for change in changes)
                )
            else:
                logger.info("Configuration reloaded (no changes detected)")

    def _detect_changes(
        self, old: Dict[str, Any], new: Dict[str, Any], prefix: str = ""
    ) -> list[str]:
        """
        Detect changes between old and new config.

        Args:
            old: Old configuration
            new: New configuration
            prefix: Key prefix for nested dicts

        Returns:
            List of change descriptions
        """
        changes = []

        # Check all keys in old config
        for key, old_value in old.items():
            full_key = f"{prefix}.{key}" if prefix else key

            if key not in new:
                changes.append(f"{full_key} removed")
            elif isinstance(old_value, dict) and isinstance(new[key], dict):
                # Recursively check nested dicts
                changes.extend(self._detect_changes(old_value, new[key], full_key))
            elif old_value != new[key]:
                changes.append(f"{full_key}: {old_value} → {new[key]}")

        # Check for new keys
        for key in new.keys():
            if key not in old:
                full_key = f"{prefix}.{key}" if prefix else key
                changes.append(f"{full_key} added: {new[key]}")

        return changes

    def enable_hot_reload(self, debounce_seconds: float = 1.0) -> None:
        """
        Enable configuration hot-reload.

        Starts watching config file for changes and automatically
        reloads when modifications are detected.

        Args:
            debounce_seconds: Minimum time between reload triggers
        """
        if self._observer and self._observer.is_alive():
            logger.warning("Config hot-reload already enabled")
            return

        if not self.config_path.exists():
            logger.warning(
                f"Config file does not exist: {self.config_path}. "
                "Hot-reload will not start."
            )
            return

        # Create handler and observer
        self._handler = ConfigFileHandler(
            config_path=self.config_path,
            on_change_callback=self.reload,
            debounce_seconds=debounce_seconds,
        )

        self._observer = Observer()
        # Watch the directory containing the config file
        watch_dir = self.config_path.parent
        self._observer.schedule(self._handler, str(watch_dir), recursive=False)
        self._observer.start()

        logger.info(f"Config hot-reload enabled: watching {self.config_path}")

    def disable_hot_reload(self) -> None:
        """Disable configuration hot-reload."""
        if self._observer and self._observer.is_alive():
            self._observer.stop()
            self._observer.join(timeout=5.0)
            self._observer = None
            self._handler = None
            logger.info("Config hot-reload disabled")

    def is_hot_reload_enabled(self) -> bool:
        """
        Check if hot-reload is enabled.

        Returns:
            True if observer is running
        """
        return self._observer is not None and self._observer.is_alive()
