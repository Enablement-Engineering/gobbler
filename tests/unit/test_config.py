"""Unit tests for configuration management."""

import pytest
from pathlib import Path
from unittest.mock import patch, mock_open, MagicMock

from gobbler_mcp.config import Config, get_config


class TestConfigLoading:
    """Test configuration loading and defaults."""

    def test_config_defaults_exist(self):
        """Test that default configuration values are defined."""
        assert "whisper" in Config.DEFAULTS
        assert "services" in Config.DEFAULTS
        assert "redis" in Config.DEFAULTS
        assert Config.DEFAULTS["whisper"]["model"] == "small"

    @patch("gobbler_mcp.config.Path")
    def test_config_loads_defaults_when_no_file(self, mock_path_class):
        """Test that defaults are used when config file doesn't exist."""
        mock_path = MagicMock()
        mock_path.exists.return_value = False
        mock_path_class.home.return_value = Path("/home/user")

        config = Config(config_path=mock_path)

        assert config.data["whisper"]["model"] == "small"
        assert config.data["services"]["crawl4ai"]["port"] == 11235

    @patch("gobbler_mcp.config.Path")
    @patch("builtins.open", new_callable=mock_open, read_data="whisper:\n  model: large\n")
    def test_config_merges_user_config(self, mock_file, mock_path_class):
        """Test that user config is merged over defaults."""
        mock_path = MagicMock()
        mock_path.exists.return_value = True
        mock_path_class.home.return_value = Path("/home/user")

        config = Config(config_path=mock_path)

        # User override should be applied
        assert config.data["whisper"]["model"] == "large"
        # Other defaults should remain
        assert config.data["whisper"]["language"] == "auto"


class TestConfigGet:
    """Test configuration value retrieval."""

    def test_get_simple_key(self):
        """Test getting simple top-level key."""
        config = Config.__new__(Config)
        config.data = {"test_key": "test_value"}

        assert config.get("test_key") == "test_value"

    def test_get_nested_key(self):
        """Test getting nested key with dot notation."""
        config = Config.__new__(Config)
        config.data = {"level1": {"level2": {"level3": "value"}}}

        assert config.get("level1.level2.level3") == "value"

    def test_get_missing_key_returns_default(self):
        """Test that missing keys return default value."""
        config = Config.__new__(Config)
        config.data = {}

        assert config.get("missing.key", "default") == "default"

    def test_get_partial_path_returns_default(self):
        """Test that partial paths return default."""
        config = Config.__new__(Config)
        config.data = {"level1": "value"}

        assert config.get("level1.level2.level3", "default") == "default"


class TestServiceUrl:
    """Test service URL generation."""

    def test_get_service_url(self):
        """Test generating service URLs."""
        config = Config.__new__(Config)
        config.data = {
            "services": {
                "crawl4ai": {
                    "host": "localhost",
                    "port": 11235
                }
            }
        }

        url = config.get_service_url("crawl4ai")
        assert url == "http://localhost:11235"

    def test_get_service_url_custom_host(self):
        """Test service URL with custom host."""
        config = Config.__new__(Config)
        config.data = {
            "services": {
                "crawl4ai": {
                    "host": "example.com",
                    "port": 8080
                }
            }
        }

        url = config.get_service_url("crawl4ai")
        assert url == "http://example.com:8080"


class TestDeepMerge:
    """Test deep merging of configuration dictionaries."""

    def test_deep_merge_simple(self):
        """Test simple deep merge."""
        base = {"a": 1, "b": 2}
        override = {"b": 3, "c": 4}

        result = Config._deep_merge(base, override)

        assert result == {"a": 1, "b": 3, "c": 4}

    def test_deep_merge_nested(self):
        """Test deep merge with nested dictionaries."""
        base = {"level1": {"a": 1, "b": 2}}
        override = {"level1": {"b": 3, "c": 4}}

        result = Config._deep_merge(base, override)

        assert result == {"level1": {"a": 1, "b": 3, "c": 4}}

    def test_deep_merge_preserves_base(self):
        """Test that deep merge doesn't mutate base dict."""
        base = {"level1": {"a": 1}}
        override = {"level1": {"b": 2}}

        result = Config._deep_merge(base, override)

        # Base should not be modified
        assert base == {"level1": {"a": 1}}
        # Result should have both
        assert result == {"level1": {"a": 1, "b": 2}}


class TestGlobalConfig:
    """Test global configuration instance."""

    @patch("gobbler_mcp.config.Config")
    def test_get_config_singleton(self, mock_config_class):
        """Test that get_config returns singleton instance."""
        # Reset global config
        import gobbler_mcp.config as config_module
        config_module._config = None

        mock_instance = MagicMock()
        mock_config_class.return_value = mock_instance

        # First call should create instance
        result1 = get_config()
        # Second call should return same instance
        result2 = get_config()

        assert result1 == result2
        assert mock_config_class.call_count == 1  # Only initialized once
