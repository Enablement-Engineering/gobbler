"""Configuration management for Gobbler MCP server."""

import logging
import threading
from pathlib import Path
from typing import Any, Dict, Optional

import yaml

logger = logging.getLogger(__name__)


class Config:
    """Configuration loader and manager."""

    # Default configuration
    DEFAULTS: Dict[str, Any] = {
        "whisper": {
            "model": "small",
            "language": "auto",
        },
        "docling": {
            "ocr": True,
            "vlm": False,
        },
        "crawl4ai": {
            "timeout": 30,
            "max_timeout": 120,
        },
        "output": {
            "default_format": "frontmatter",
            "timestamp_format": "iso8601",
        },
        "services": {
            "crawl4ai": {
                "host": "localhost",
                "port": 11235,
                "api_token": "gobbler-local-token",
            },
            "docling": {
                "host": "localhost",
                "port": 5001,
            },
        },
        "redis": {
            "host": "localhost",
            "port": 6380,
            "db": 0,
        },
        "queue": {
            "auto_queue_threshold": 105,  # seconds (1:45)
            "default_queue": "default",
        },
        "models_path": "~/.gobbler/models",
        "monitoring": {
            "metrics_enabled": False,  # Enable Prometheus metrics collection
            "metrics_port": 9090,  # Port for metrics HTTP endpoint
            "metrics_host": "0.0.0.0",  # Host to bind metrics server
            "log_format": "text",  # 'text' or 'json' (use text for MCP stdio)
            "log_level": "INFO",  # DEBUG, INFO, WARNING, ERROR, CRITICAL
            "health_check_interval": 60,  # Seconds between service health checks
            "config_hot_reload": True,  # Enable config file hot-reload
        },
    }

    def __init__(self, config_path: Optional[Path] = None) -> None:
        """
        Initialize configuration.

        Args:
            config_path: Path to config file. If None, uses default location.
        """
        self.config_path = config_path or self._default_config_path()
        self._lock = threading.RLock()  # Reentrant lock for thread-safety
        self._watcher: Optional[Any] = None  # ConfigWatcher instance
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
        config = self.DEFAULTS.copy()

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

        return config

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
                result[key] = Config._deep_merge(result[key], value)
            else:
                result[key] = value
        return result

    def get(self, key: str, default: Any = None) -> Any:
        """
        Get configuration value using dot notation (thread-safe).

        Args:
            key: Configuration key (e.g., "whisper.model")
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
            service: Service name (crawl4ai, docling, whisper)

        Returns:
            Full HTTP URL for service
        """
        host = self.get(f"services.{service}.host", "localhost")
        port = self.get(f"services.{service}.port")
        return f"http://{host}:{port}"

    def reload(self) -> None:
        """
        Reload configuration from file (thread-safe).

        Validates new config before applying. If validation fails,
        keeps current config and logs errors.
        """
        with self._lock:
            # Load new config
            try:
                new_config = self._load_config()
            except Exception as e:
                logger.error(f"Failed to load config during reload: {e}")
                return

            # Validate new config
            from .config_watcher import ConfigWatcher

            validation_errors = ConfigWatcher.validate_config(new_config)
            if validation_errors:
                logger.error(
                    f"Config validation failed. Keeping current config. Errors:\n"
                    + "\n".join(f"  - {err}" for err in validation_errors)
                )
                return

            # Detect changes
            changes = self._detect_changes(self.data, new_config)

            # Apply new config atomically
            old_config = self.data
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
        if self._watcher and self._watcher.is_running():
            logger.warning("Config hot-reload already enabled")
            return

        from .config_watcher import ConfigWatcher

        self._watcher = ConfigWatcher(
            config_path=self.config_path,
            reload_callback=self.reload,
            debounce_seconds=debounce_seconds,
        )

        self._watcher.start()

    def disable_hot_reload(self) -> None:
        """Disable configuration hot-reload."""
        if self._watcher:
            self._watcher.stop()
            self._watcher = None


# Global config instance
_config: Optional[Config] = None


def get_config() -> Config:
    """
    Get global configuration instance.

    Returns:
        Config instance
    """
    global _config
    if _config is None:
        _config = Config()
    return _config
