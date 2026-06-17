"""Web page conversion providers for URL to markdown conversion.

This package provides abstracted web scraping capabilities with multiple
backend implementations.

Available Providers:
    - crawl4ai: Crawl4AI Docker service (default)

Example:
    from gobbler_core.providers.webpage import (
        WebPageProvider,
        Crawl4AIProvider,
        get_default_provider,
    )

    # Use default provider from config
    provider = get_default_provider()
    result = await provider.fetch("https://example.com")

    # Or create specific provider
    provider = Crawl4AIProvider(service_url="http://localhost:11235")
    result = await provider.fetch("https://example.com", timeout=60)
"""

from typing import Any

from gobbler_core.providers.webpage.base import (
    WebPageProvider,
    WebPageResult,
)
from gobbler_core.providers.webpage.crawl4ai import Crawl4AIProvider

__all__ = [
    "Crawl4AIProvider",
    "WebPageProvider",
    "WebPageResult",
    "get_default_provider",
]


def get_default_provider(**kwargs: Any) -> WebPageProvider:
    """Get the default webpage provider based on configuration.

    Reads service URL, API token, and proxy from config file.
    Falls back to defaults if config unavailable.

    Args:
        **kwargs: Override configuration options (service_url, api_token, proxy_url)

    Returns:
        Configured WebPageProvider instance
    """
    from gobbler_core.providers.proxy import get_crawl4ai_proxy_url

    # Get config-based defaults
    service_url = kwargs.pop("service_url", None)
    api_token = kwargs.pop("api_token", None)
    proxy_url = kwargs.pop("proxy_url", None)
    use_proxy = kwargs.pop("use_proxy", True)

    if service_url is None or api_token is None:
        try:
            from gobbler_core.config import get_config

            config = get_config()
            if service_url is None:
                service_url = config.get_service_url("crawl4ai")
            if api_token is None:
                api_token = (
                    config.data.get("services", {})
                    .get("crawl4ai", {})
                    .get("api_token", "gobbler-local-token")
                )
        except Exception:
            service_url = service_url or "http://localhost:11235"
            api_token = api_token or "gobbler-local-token"

    # Get proxy from config if not overridden
    if proxy_url is None and use_proxy:
        proxy_url = get_crawl4ai_proxy_url()

    return Crawl4AIProvider(
        service_url=service_url,
        api_token=api_token,
        proxy_url=proxy_url,
    )
