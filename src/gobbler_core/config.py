"""Configuration management for Gobbler."""

from __future__ import annotations

import logging
import threading
from pathlib import Path
from typing import Any, ClassVar

import yaml

logger = logging.getLogger(__name__)


class Config:
    """Configuration loader and manager."""

    DEFAULTS: ClassVar[dict[str, Any]] = {
        "proxy_services": {},
        "providers": {
            "transcription": {
                "default": "whisper-local",
                "whisper-local": {
                    "model": "small",
                },
            },
            "document": {
                "default": "docling",
                "docling": {
                    "ocr": True,
                },
            },
            "webpage": {
                "default": "crawl4ai",
                "crawl4ai": {
                    "timeout": 30,
                },
            },
            "youtube": {
                "default": "youtube-transcript-api",
                "youtube-transcript-api": {},
                "transcriptapi": {},
            },
        },
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
            "default_directory": None,
        },
        "services": {
            "crawl4ai": {
                "host": "localhost",
                "port": 11235,
                "api_token": "gobbler-local-token",  # nosec B105
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
            "auto_queue_threshold": 105,
            "default_queue": "default",
        },
        "models_path": "~/.gobbler/models",
        "monitoring": {
            "metrics_enabled": False,
            "metrics_port": 9090,
            "metrics_host": "0.0.0.0",  # noqa: S104  # nosec B104
            "log_format": "text",
            "log_level": "INFO",
            "health_check_interval": 60,
        },
    }

    def __init__(self, config_path: Path | None = None) -> None:
        """Initialize configuration.

        Args:
            config_path: Path to config file. If None, uses default location.
        """
        self.config_path = config_path or self._default_config_path()
        self._lock = threading.RLock()
        self.data = self._load_config()

    @staticmethod
    def _default_config_path() -> Path:
        """Get default configuration file path."""
        return Path.home() / ".config" / "gobbler" / "config.yml"

    def _load_config(self) -> dict[str, Any]:
        """Load configuration from file, falling back to defaults.

        Returns:
            Configuration dictionary.
        """
        config = self.DEFAULTS.copy()

        if self.config_path.exists():
            try:
                with self.config_path.open() as config_file:
                    user_config = yaml.safe_load(config_file)
                    if user_config:
                        config = self._deep_merge(config, user_config)
                        logger.info("Loaded configuration from %s", self.config_path)
            except Exception:
                logger.warning("Failed to load config from %s", self.config_path, exc_info=True)
                logger.info("Using default configuration")
        else:
            logger.info("No config file found at %s, using defaults", self.config_path)

        return config

    @staticmethod
    def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
        """Deep merge two dictionaries.

        Args:
            base: Base dictionary.
            override: Dictionary to merge over base.

        Returns:
            Merged dictionary.
        """
        result = base.copy()
        for key, value in override.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = Config._deep_merge(result[key], value)
            else:
                result[key] = value
        return result

    def get(self, key: str, default: Any = None) -> Any:
        """Get configuration value using dot notation.

        Args:
            key: Configuration key, such as ``whisper.model``.
            default: Default value if key is not found.

        Returns:
            Configuration value.
        """
        with self._lock:
            keys = key.split(".")
            value = self.data
            for key_part in keys:
                if isinstance(value, dict) and key_part in value:
                    value = value[key_part]
                else:
                    return default
            return value

    def get_service_url(self, service: str) -> str:
        """Get full service URL.

        Args:
            service: Service name, such as ``crawl4ai`` or ``docling``.

        Returns:
            Full HTTP URL for the service.
        """
        host = self.get(f"services.{service}.host", "localhost")
        port = self.get(f"services.{service}.port")
        return f"http://{host}:{port}"

    def get_provider_name(self, category: str) -> str:
        """Get the default provider name for a category.

        Args:
            category: Provider category.

        Returns:
            Provider name.
        """
        return self.get(f"providers.{category}.default", self._default_provider(category))

    def get_provider_config(self, category: str, provider_name: str | None = None) -> dict:
        """Get configuration for a specific provider.

        Args:
            category: Provider category.
            provider_name: Provider name, or None to use default.

        Returns:
            Provider configuration dictionary.
        """
        if provider_name is None:
            provider_name = self.get_provider_name(category)

        return self.get(f"providers.{category}.{provider_name}", {})

    @staticmethod
    def _default_provider(category: str) -> str:
        """Get the default provider name for a category.

        Args:
            category: Provider category.

        Returns:
            Default provider name.
        """
        defaults = {
            "transcription": "whisper-local",
            "document": "docling",
            "webpage": "crawl4ai",
            "youtube": "youtube-transcript-api",
        }
        return defaults.get(category, "")

    def get_proxy_service(self, service_name: str) -> dict | None:
        """Get proxy service configuration by name.

        Args:
            service_name: Name of the proxy service.

        Returns:
            Proxy service configuration dictionary, or None if not found.
        """
        return self.get(f"proxy_services.{service_name}")

    def get_provider_proxy(self, category: str, provider_name: str | None = None) -> dict | None:
        """Get proxy configuration for a provider.

        Args:
            category: Provider category.
            provider_name: Provider name, or None to use default.

        Returns:
            Proxy service configuration dictionary, or None if no proxy configured.
        """
        if provider_name is None:
            provider_name = self.get_provider_name(category)

        proxy_service_name = self.get(f"providers.{category}.{provider_name}.proxy")
        if proxy_service_name is None:
            return None

        return self.get_proxy_service(proxy_service_name)

    def get_provider_fallback(self, category: str, provider_name: str | None = None) -> dict | None:
        """Get fallback configuration for a provider.

        Args:
            category: Provider category.
            provider_name: Provider name, or None to use default.

        Returns:
            Fallback config dict with provider and condition keys, or None.
        """
        if provider_name is None:
            provider_name = self.get_provider_name(category)

        fallback = self.get(f"providers.{category}.{provider_name}.fallback")
        if fallback is None:
            return None

        if (
            isinstance(fallback, dict)
            and "provider" in fallback
            and "on" not in fallback
            and True in fallback
        ):
            fallback = {**fallback, "on": fallback[True]}

        if not isinstance(fallback, dict) or "provider" not in fallback or "on" not in fallback:
            return None

        return fallback

    def reload(self) -> None:
        """Reload configuration from file."""
        with self._lock:
            self.data = self._load_config()


_config: Config | None = None


def get_config() -> Config:
    """Get global configuration instance.

    Returns:
        Config instance.
    """
    global _config  # noqa: PLW0603
    if _config is None:
        _config = Config()
    return _config
