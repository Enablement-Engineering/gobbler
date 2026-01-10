"""Unit tests for proxy configuration."""

import os
import threading
from unittest.mock import MagicMock, patch

from gobbler_core.providers.proxy import (
    ProxyConfig,
    get_crawl4ai_proxy_url,
    get_proxy_for_provider,
)


def create_mock_config(data: dict) -> MagicMock:
    """Create a mock Config instance for testing."""
    mock_config = MagicMock()
    mock_config._lock = threading.RLock()
    mock_config.data = data

    def get_side_effect(key: str, default=None):
        parts = key.split(".")
        result = data
        for part in parts:
            if isinstance(result, dict) and part in result:
                result = result[part]
            else:
                return default
        return result

    mock_config.get = MagicMock(side_effect=get_side_effect)
    return mock_config


class TestProxyConfig:
    """Test ProxyConfig factory."""

    def test_rotating_proxy_from_config(self):
        """Test creating a rotating proxy service from config."""
        config = {
            "type": "rotating",
            "username": "testuser",
            "password": "testpass",
            "name": "webshare",
        }

        proxy = ProxyConfig.from_config(config)

        assert proxy is not None
        assert proxy.name == "webshare"
        assert proxy.type == "rotating"
        assert proxy.url == "http://testuser-rotate:testpass@p.webshare.io:80"

    def test_static_proxy_from_config(self):
        """Test creating a static proxy service from config."""
        config = {
            "type": "static",
            "url": "http://proxy.example.com:8080",
            "name": "datacenter",
        }

        proxy = ProxyConfig.from_config(config)

        assert proxy is not None
        assert proxy.name == "datacenter"
        assert proxy.type == "static"
        assert proxy.url == "http://proxy.example.com:8080"

    def test_rotating_proxy_missing_credentials(self):
        """Test rotating proxy returns None when credentials are missing."""
        config = {
            "type": "rotating",
            "username": "",
            "password": "",
            "name": "webshare",
        }

        proxy = ProxyConfig.from_config(config)

        assert proxy is None

    def test_static_proxy_missing_url(self):
        """Test static proxy returns None when URL is missing."""
        config = {
            "type": "static",
            "url": "",
            "name": "datacenter",
        }

        proxy = ProxyConfig.from_config(config)

        assert proxy is None

    def test_env_var_substitution(self):
        """Test that ${ENV_VAR} syntax is resolved."""
        config = {
            "type": "rotating",
            "username": "${TEST_PROXY_USER}",
            "password": "${TEST_PROXY_PASS}",
            "name": "webshare",
        }
        env_vars = {"TEST_PROXY_USER": "envuser", "TEST_PROXY_PASS": "envpass"}

        proxy = ProxyConfig.from_config(config, env_vars=env_vars)

        assert proxy is not None
        assert proxy.url == "http://envuser-rotate:envpass@p.webshare.io:80"


class TestGetCrawl4aiProxyUrl:
    """Test get_crawl4ai_proxy_url function."""

    def test_returns_none_when_no_proxy_configured(self):
        """Test returns None when no proxy is configured."""
        with (
            patch.dict(os.environ, {}, clear=True),
            patch(
                "gobbler_mcp.config.get_config",
                side_effect=Exception("No config"),
            ),
        ):
            result = get_crawl4ai_proxy_url()

        assert result is None

    def test_returns_env_var_proxy(self):
        """Test returns proxy URL from CRAWL4AI_PROXY environment variable."""
        test_proxy = "http://user:pass@proxy.example.com:8080"

        with (
            patch.dict(os.environ, {"CRAWL4AI_PROXY": test_proxy}, clear=True),
            patch(
                "gobbler_mcp.config.get_config",
                side_effect=Exception("No config"),
            ),
        ):
            result = get_crawl4ai_proxy_url()

        assert result == test_proxy

    def test_config_takes_precedence_over_env_var(self):
        """Test that config file proxy takes precedence over env var."""
        mock_config = create_mock_config(
            {
                "proxy_services": {
                    "webshare": {
                        "type": "rotating",
                        "username": "configuser",
                        "password": "configpass",
                    }
                },
                "providers": {"webpage": {"crawl4ai": {"proxy": "webshare"}}},
            }
        )

        with (
            patch.dict(
                os.environ,
                {"CRAWL4AI_PROXY": "http://env-proxy.com:8080"},
                clear=True,
            ),
            patch("gobbler_mcp.config.get_config", return_value=mock_config),
        ):
            result = get_crawl4ai_proxy_url()

        # Should use config, not env var
        assert result == "http://configuser-rotate:configpass@p.webshare.io:80"

    def test_falls_back_to_env_when_config_proxy_not_set(self):
        """Test falls back to env var when config has no proxy."""
        mock_config = create_mock_config(
            {
                "proxy_services": {},
                "providers": {"webpage": {"crawl4ai": {}}},
            }
        )
        test_proxy = "http://fallback-proxy.com:8080"

        with (
            patch.dict(os.environ, {"CRAWL4AI_PROXY": test_proxy}, clear=True),
            patch("gobbler_mcp.config.get_config", return_value=mock_config),
        ):
            result = get_crawl4ai_proxy_url()

        assert result == test_proxy


class TestGetProxyForProvider:
    """Test get_proxy_for_provider function."""

    def test_returns_proxy_for_configured_provider(self):
        """Test returns proxy when provider has proxy configured."""
        mock_config = create_mock_config(
            {
                "proxy_services": {
                    "webshare": {
                        "type": "rotating",
                        "username": "user",
                        "password": "pass",
                    }
                },
                "providers": {"webpage": {"crawl4ai": {"proxy": "webshare"}}},
            }
        )

        proxy = get_proxy_for_provider(mock_config, "webpage", "crawl4ai")

        assert proxy is not None
        assert proxy.name == "webshare"
        assert proxy.type == "rotating"

    def test_returns_none_when_no_proxy_configured(self):
        """Test returns None when provider has no proxy configured."""
        mock_config = create_mock_config(
            {
                "proxy_services": {},
                "providers": {"webpage": {"crawl4ai": {}}},
            }
        )

        proxy = get_proxy_for_provider(mock_config, "webpage", "crawl4ai")

        assert proxy is None

    def test_returns_none_when_proxy_service_not_found(self):
        """Test returns None when referenced proxy service doesn't exist."""
        mock_config = create_mock_config(
            {
                "proxy_services": {},
                "providers": {"webpage": {"crawl4ai": {"proxy": "nonexistent"}}},
            }
        )

        proxy = get_proxy_for_provider(mock_config, "webpage", "crawl4ai")

        assert proxy is None
