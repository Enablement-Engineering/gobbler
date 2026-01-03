"""Provider registry for managing and creating provider instances.

This module provides a central registry for all provider types in Gobbler.
Providers can be registered, discovered, and instantiated through configuration.

Example:
    # Register a provider
    ProviderRegistry.register("transcription", "whisper-local", WhisperLocalProvider)

    # Create from config
    provider = ProviderRegistry.create("transcription", "whisper-local", model="small")

    # List available providers
    providers = ProviderRegistry.list_providers("transcription")
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, ClassVar

if TYPE_CHECKING:
    from gobbler_core.providers.base import ContentProvider

logger = logging.getLogger(__name__)


class ProviderNotFoundError(Exception):
    """Raised when a requested provider is not found in the registry."""

    def __init__(self, category: str, name: str) -> None:
        """Initialize error.

        Args:
            category: Provider category (e.g., "transcription")
            name: Provider name (e.g., "whisper-local")
        """
        self.category = category
        self.name = name
        available = ProviderRegistry.list_providers(category)
        available_str = ", ".join(available) if available else "none"
        super().__init__(
            f"Provider '{name}' not found in category '{category}'. "
            f"Available providers: {available_str}"
        )


class ProviderRegistry:
    """Central registry for all provider types.

    This class maintains a mapping of provider categories (e.g., "transcription",
    "document", "webpage") to their available implementations.

    Providers are registered with a category and name, and can be instantiated
    with configuration options.
    """

    # Registry structure: {category: {name: provider_class}}
    _providers: ClassVar[dict[str, dict[str, type[ContentProvider]]]] = {}

    @classmethod
    def register(
        cls,
        category: str,
        name: str,
        provider_class: type[ContentProvider],
    ) -> None:
        """Register a provider implementation.

        Args:
            category: Provider category (e.g., "transcription", "document", "webpage")
            name: Provider name in kebab-case (e.g., "whisper-local", "docling")
            provider_class: The provider class to register

        Example:
            ProviderRegistry.register("transcription", "whisper-local", WhisperLocalProvider)
        """
        if category not in cls._providers:
            cls._providers[category] = {}

        if name in cls._providers[category]:
            logger.warning(
                "Overwriting existing provider '%s' in category '%s'",
                name,
                category,
            )

        cls._providers[category][name] = provider_class
        logger.debug("Registered provider '%s' in category '%s'", name, category)

    @classmethod
    def unregister(cls, category: str, name: str) -> bool:
        """Unregister a provider.

        Args:
            category: Provider category
            name: Provider name

        Returns:
            True if provider was unregistered, False if not found
        """
        if category in cls._providers and name in cls._providers[category]:
            del cls._providers[category][name]
            logger.debug("Unregistered provider '%s' from category '%s'", name, category)
            return True
        return False

    @classmethod
    def get(cls, category: str, name: str) -> type[ContentProvider]:
        """Get provider class by category and name.

        Args:
            category: Provider category
            name: Provider name

        Returns:
            The provider class

        Raises:
            ProviderNotFoundError: If provider not found
        """
        if category not in cls._providers or name not in cls._providers[category]:
            raise ProviderNotFoundError(category, name)

        return cls._providers[category][name]

    @classmethod
    def create(
        cls,
        category: str,
        name: str,
        **kwargs: Any,
    ) -> ContentProvider:
        """Create provider instance from registry.

        Args:
            category: Provider category
            name: Provider name
            **kwargs: Arguments to pass to provider constructor

        Returns:
            Configured provider instance

        Raises:
            ProviderNotFoundError: If provider not found
        """
        provider_class = cls.get(category, name)
        logger.debug(
            "Creating provider '%s' in category '%s' with kwargs: %s",
            name,
            category,
            list(kwargs.keys()),
        )
        return provider_class(**kwargs)

    @classmethod
    def list_providers(cls, category: str) -> list[str]:
        """List available providers for a category.

        Args:
            category: Provider category

        Returns:
            List of provider names (empty if category not found)
        """
        if category not in cls._providers:
            return []
        return list(cls._providers[category].keys())

    @classmethod
    def list_categories(cls) -> list[str]:
        """List all provider categories.

        Returns:
            List of category names
        """
        return list(cls._providers.keys())

    @classmethod
    def get_provider_info(cls, category: str, name: str) -> dict[str, Any]:
        """Get information about a registered provider.

        Args:
            category: Provider category
            name: Provider name

        Returns:
            Dictionary with provider information

        Raises:
            ProviderNotFoundError: If provider not found
        """
        provider_class = cls.get(category, name)
        return {
            "category": category,
            "name": name,
            "class": provider_class.__name__,
            "module": provider_class.__module__,
            "doc": provider_class.__doc__ or "No documentation available",
        }

    @classmethod
    def clear(cls) -> None:
        """Clear all registered providers.

        Primarily useful for testing.
        """
        cls._providers.clear()
        logger.debug("Cleared all registered providers")
