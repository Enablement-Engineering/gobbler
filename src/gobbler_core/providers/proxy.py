"""Unified proxy service abstraction for content providers.

This module provides a unified way to configure and use proxy services across
all providers in Gobbler. It supports both rotating proxies (like Webshare)
and static proxies (single URL).

Configuration in config.yml:
    proxy_services:
      webshare:
        type: rotating
        username: ${WEBSHARE_USER}
        password: ${WEBSHARE_PASS}

      datacenter:
        type: static
        url: ${PROXY_URL}

    providers:
      youtube:
        default: youtube-transcript-api
        youtube-transcript-api:
          proxy: webshare  # Reference to proxy_services entry

Environment variables:
    - WEBSHARE_USER: Webshare proxy username
    - WEBSHARE_PASS: Webshare proxy password
    - YOUTUBE_PROXY: Generic proxy URL (http://user:pass@host:port)
"""

from __future__ import annotations

import logging
import os
import re
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Literal

if TYPE_CHECKING:
    from gobbler_mcp.config import Config

logger = logging.getLogger(__name__)

# Webshare rotating proxy URL template
WEBSHARE_URL_TEMPLATE = "http://{username}-rotate:{password}@p.webshare.io:80"

# Pattern to match ${ENV_VAR} syntax
ENV_VAR_PATTERN = re.compile(r"\$\{([^}]+)\}")


@dataclass
class ProxyService:
    """A configured proxy service.

    Attributes:
        name: Service name (e.g., "webshare", "datacenter")
        type: Proxy type - "rotating" for services like Webshare,
              "static" for single URL proxies
        url: The resolved proxy URL (constructed for rotating, direct for static).
             None if the proxy couldn't be configured (missing credentials).
    """

    name: str
    type: Literal["rotating", "static"]
    url: str | None


def _resolve_env_vars(value: str, env_vars: dict[str, str] | None = None) -> str:
    """Resolve ${ENV_VAR} syntax in a string value.

    Args:
        value: String potentially containing ${ENV_VAR} references
        env_vars: Optional dictionary of environment variables.
                  Falls back to os.environ if not provided.

    Returns:
        String with environment variables resolved.
        Unresolved variables are left as empty strings.
    """
    if not isinstance(value, str):
        return value

    def replacer(match: re.Match[str]) -> str:
        var_name = match.group(1)
        if env_vars is not None and var_name in env_vars:
            return env_vars[var_name]
        return os.environ.get(var_name, "")

    return ENV_VAR_PATTERN.sub(replacer, value)


class ProxyConfig:
    """Factory for creating ProxyService instances from configuration."""

    @classmethod
    def from_config(
        cls,
        config_dict: dict[str, Any],
        env_vars: dict[str, str] | None = None,
    ) -> ProxyService | None:
        """Create a ProxyService from a configuration dictionary.

        Args:
            config_dict: Proxy service configuration with keys:
                - type: "rotating" or "static"
                - For rotating: username, password
                - For static: url
            env_vars: Optional dictionary of environment variables for
                      resolving ${ENV_VAR} syntax. Defaults to os.environ.

        Returns:
            Configured ProxyService, or None if configuration is invalid
            or missing required values.

        Examples:
            >>> config = {"type": "rotating", "username": "${WEBSHARE_USER}",
            ...           "password": "${WEBSHARE_PASS}"}
            >>> proxy = ProxyConfig.from_config(config, {"WEBSHARE_USER": "user",
            ...                                          "WEBSHARE_PASS": "pass"})
            >>> proxy.url
            'http://user-rotate:pass@p.webshare.io:80'
        """
        if not config_dict:
            return None

        proxy_type = config_dict.get("type")
        name = config_dict.get("name", "unknown")

        if proxy_type == "rotating":
            return cls._create_rotating_proxy(config_dict, env_vars, name)
        if proxy_type == "static":
            return cls._create_static_proxy(config_dict, env_vars, name)
        logger.warning("Unknown proxy type: %s", proxy_type)
        return None

    @classmethod
    def _create_rotating_proxy(
        cls,
        config_dict: dict[str, Any],
        env_vars: dict[str, str] | None,
        name: str,
    ) -> ProxyService | None:
        """Create a rotating proxy service (e.g., Webshare).

        Args:
            config_dict: Configuration with username and password
            env_vars: Environment variables for resolution
            name: Service name

        Returns:
            ProxyService with constructed URL, or None if credentials missing
        """
        username_raw = config_dict.get("username", "")
        password_raw = config_dict.get("password", "")

        username = _resolve_env_vars(username_raw, env_vars)
        password = _resolve_env_vars(password_raw, env_vars)

        if not username or not password:
            logger.debug(
                "Rotating proxy '%s' missing credentials (username=%s, password=%s)",
                name,
                bool(username),
                bool(password),
            )
            return None

        url = WEBSHARE_URL_TEMPLATE.format(username=username, password=password)
        logger.debug("Configured rotating proxy '%s'", name)

        return ProxyService(name=name, type="rotating", url=url)

    @classmethod
    def _create_static_proxy(
        cls,
        config_dict: dict[str, Any],
        env_vars: dict[str, str] | None,
        name: str,
    ) -> ProxyService | None:
        """Create a static proxy service (single URL).

        Args:
            config_dict: Configuration with url field
            env_vars: Environment variables for resolution
            name: Service name

        Returns:
            ProxyService with resolved URL, or None if URL missing
        """
        url_raw = config_dict.get("url", "")
        url = _resolve_env_vars(url_raw, env_vars)

        if not url:
            logger.debug("Static proxy '%s' missing URL", name)
            return None

        # Log proxy without credentials for security
        safe_url = url.split("@")[-1] if "@" in url else url
        logger.debug("Configured static proxy '%s': %s", name, safe_url)

        return ProxyService(name=name, type="static", url=url)


def get_proxy_for_provider(
    config: Config,
    category: str,
    provider_name: str,
) -> ProxyService | None:
    """Get the configured proxy for a specific provider.

    Reads the proxy service name from the provider configuration and
    looks up that service in the proxy_services configuration.

    Args:
        config: Gobbler configuration instance
        category: Provider category (e.g., "youtube", "webpage")
        provider_name: Provider name (e.g., "youtube-transcript-api", "crawl4ai")

    Returns:
        Configured ProxyService, or None if no proxy configured

    Example:
        >>> config = get_config()
        >>> proxy = get_proxy_for_provider(config, "youtube", "youtube-transcript-api")
        >>> if proxy:
        ...     print(f"Using proxy: {proxy.name}")
    """
    # Get the proxy service name from provider config
    proxy_service_name = config.get(f"providers.{category}.{provider_name}.proxy")

    if not proxy_service_name:
        logger.debug("No proxy configured for %s.%s", category, provider_name)
        return None

    # Look up the proxy service configuration
    proxy_config = config.get(f"proxy_services.{proxy_service_name}")

    if not proxy_config:
        logger.warning(
            "Proxy service '%s' referenced by %s.%s not found in proxy_services",
            proxy_service_name,
            category,
            provider_name,
        )
        return None

    # Add name to config for service identification
    if isinstance(proxy_config, dict):
        proxy_config = {**proxy_config, "name": proxy_service_name}

    return ProxyConfig.from_config(proxy_config)


def get_youtube_proxy_config() -> Any:
    """Get proxy configuration for YouTube transcript providers.

    This function provides backwards compatibility with the existing
    youtube-transcript-api proxy configuration. It checks:
    1. Config file for proxy_services referenced by youtube provider
    2. Environment variables (WEBSHARE_USER, WEBSHARE_PASS, YOUTUBE_PROXY)

    Returns:
        WebshareProxyConfig, GenericProxyConfig, or None

    Example:
        >>> proxy_config = get_youtube_proxy_config()
        >>> if proxy_config:
        ...     api = YouTubeTranscriptApi(proxy_config=proxy_config)
    """
    # Import here to avoid circular imports and make youtube_transcript_api optional
    from youtube_transcript_api.proxies import (  # noqa: PLC0415
        GenericProxyConfig,
        WebshareProxyConfig,
    )

    # Try to get from config file first
    try:
        from gobbler_mcp.config import get_config  # noqa: PLC0415

        config = get_config()
        provider_name = config.get("providers.youtube.default", "youtube-transcript-api")
        proxy = get_proxy_for_provider(config, "youtube", provider_name)

        if proxy and proxy.url:
            if proxy.type == "rotating":
                # Extract credentials from constructed URL for WebshareProxyConfig
                # URL format: http://{user}-rotate:{pass}@p.webshare.io:80
                # WebshareProxyConfig wants the raw username/password
                proxy_config = config.get(f"proxy_services.{proxy.name}", {})
                username = _resolve_env_vars(proxy_config.get("username", ""))
                password = _resolve_env_vars(proxy_config.get("password", ""))

                if username and password:
                    logger.info("Using Webshare proxy from config for YouTube")
                    return WebshareProxyConfig(
                        proxy_username=username,
                        proxy_password=password,
                    )
            else:
                # Static proxy - use GenericProxyConfig
                logger.info("Using static proxy from config for YouTube")
                return GenericProxyConfig(
                    http_url=proxy.url,
                    https_url=proxy.url,
                )
    except Exception:
        logger.debug("Could not load proxy from config file, falling back to env vars")

    # Fall back to environment variables for backwards compatibility
    webshare_user = os.environ.get("WEBSHARE_USER")
    webshare_pass = os.environ.get("WEBSHARE_PASS")
    proxy_url = os.environ.get("YOUTUBE_PROXY")

    if webshare_user and webshare_pass:
        logger.info("Using Webshare proxy from environment for YouTube")
        return WebshareProxyConfig(
            proxy_username=webshare_user,
            proxy_password=webshare_pass,
        )

    if proxy_url:
        safe_url = proxy_url.split("@")[-1] if "@" in proxy_url else proxy_url
        logger.info("Using static proxy from environment for YouTube: %s", safe_url)
        return GenericProxyConfig(
            http_url=proxy_url,
            https_url=proxy_url,
        )

    logger.debug("No YouTube proxy configured")
    return None
