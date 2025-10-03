"""Configuration management for Gobbler MCP server."""

import logging
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
            "whisper": {
                "host": "localhost",
                "port": 9000,
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
    }

    def __init__(self, config_path: Optional[Path] = None) -> None:
        """
        Initialize configuration.

        Args:
            config_path: Path to config file. If None, uses default location.
        """
        self.config_path = config_path or self._default_config_path()
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
        Get configuration value using dot notation.

        Args:
            key: Configuration key (e.g., "whisper.model")
            default: Default value if key not found

        Returns:
            Configuration value
        """
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
