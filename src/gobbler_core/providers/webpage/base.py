"""Base classes for web page conversion providers.

This module defines the abstract interface for web scraping
providers in Gobbler.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass
class WebPageResult:
    """Result from a web page conversion provider.

    Attributes:
        markdown: Converted markdown content
        title: Page title
        url: Original URL
        metadata: Additional provider-specific metadata
        links: Extracted links (optional)
        images: Extracted image URLs (optional)
    """

    markdown: str
    title: str
    url: str
    metadata: dict[str, Any] = field(default_factory=dict)
    links: list[str] | None = None
    images: list[str] | None = None

    @property
    def word_count(self) -> int:
        """Get approximate word count of converted content."""
        return len(self.markdown.split())


class WebPageProvider(ABC):
    """Abstract base class for web page conversion providers.

    All web scraping providers must implement this interface to ensure
    consistent behavior across different backends (e.g., Crawl4AI,
    Playwright, Firecrawl, etc.).

    Example:
        class MyWebPageProvider(WebPageProvider):
            @property
            def name(self) -> str:
                return "my-provider"

            async def fetch(
                self,
                url: str,
                timeout: int = 30,
                **options,
            ) -> WebPageResult:
                # Implementation here
                pass
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Provider name for identification and logging.

        Returns:
            Unique provider identifier in kebab-case (e.g., "crawl4ai")
        """

    @abstractmethod
    async def fetch(
        self,
        url: str,
        timeout: int = 30,
        **options: Any,
    ) -> WebPageResult:
        """Fetch and convert web page to markdown.

        Args:
            url: Web page URL to fetch
            timeout: Request timeout in seconds
            **options: Provider-specific options (e.g., wait_for, include_images)

        Returns:
            WebPageResult with markdown content and metadata

        Raises:
            ValueError: If URL is invalid
            RuntimeError: If fetching or conversion fails
            TimeoutError: If request times out
        """

    def __repr__(self) -> str:
        """Return string representation of provider."""
        return f"{self.__class__.__name__}(name={self.name!r})"
