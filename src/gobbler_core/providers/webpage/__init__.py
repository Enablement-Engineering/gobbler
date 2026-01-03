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


def get_default_provider(**kwargs) -> WebPageProvider:
    """Get the default webpage provider based on configuration.

    Args:
        **kwargs: Override configuration options

    Returns:
        Configured WebPageProvider instance
    """
    from gobbler_core.providers.registry import ProviderRegistry

    provider_name = kwargs.pop("provider", "crawl4ai")
    return ProviderRegistry.create("webpage", provider_name, **kwargs)
