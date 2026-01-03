"""Base classes and interfaces for content providers.

This module defines the abstract base class and standard result type for all
content providers in Gobbler. Providers can be implemented for different
sources (YouTube, webpages, documents, etc.) and follow a consistent interface.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any


@dataclass
class ProviderResult:
    """Standard result from any provider.

    Attributes:
        success: Whether the provider successfully fetched content
        content: The fetched content (transcript text, markdown, etc.)
        metadata: Additional metadata about the content
        error: Error message if success is False
    """

    success: bool
    content: str
    metadata: dict[str, Any]
    error: str | None = None


class ContentProvider(ABC):
    """Base class for all content providers.

    Content providers are responsible for fetching content from various sources
    and returning it in a standardized format. Each provider should implement
    the abstract methods defined here.

    Example:
        class MyProvider(ContentProvider):
            @property
            def name(self) -> str:
                return "my-provider"

            async def fetch(self, source: str, **options) -> ProviderResult:
                # Implementation here
                return ProviderResult(
                    success=True,
                    content="fetched content",
                    metadata={"source": source}
                )

            def supports(self, source: str) -> bool:
                return source.startswith("https://mysite.com")
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Provider name for logging/identification.

        Returns:
            A unique identifier for this provider (e.g., "youtube-transcript-api")
        """

    @abstractmethod
    async def fetch(self, source: str, **options) -> ProviderResult:
        """Fetch content from the source.

        Args:
            source: URL, file path, or identifier to fetch content from
            **options: Provider-specific options (e.g., language, format)

        Returns:
            ProviderResult with content and metadata

        Raises:
            Should return ProviderResult with success=False and error message
            rather than raising exceptions.
        """

    @abstractmethod
    def supports(self, source: str) -> bool:
        """Check if this provider supports the given source.

        Args:
            source: URL, file path, or identifier to check

        Returns:
            True if this provider can handle the source
        """
