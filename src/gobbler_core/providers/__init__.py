"""Transcript and content providers for Gobbler.

This package provides the abstraction layer for all content conversion
in Gobbler. Providers can be swapped via configuration to use different
backends for transcription, document conversion, and web scraping.

Provider Categories:
    - transcription: Audio/video transcription (whisper-local, etc.)
    - document: Document conversion (docling, etc.)
    - webpage: Web page scraping (crawl4ai, etc.)
    - youtube: YouTube transcript extraction (existing, separate interface)

Example:
    from gobbler_core.providers import ProviderRegistry
    from gobbler_core.providers.transcription import WhisperLocalProvider

    # List available providers
    ProviderRegistry.list_providers("transcription")

    # Create provider from registry
    provider = ProviderRegistry.create("transcription", "whisper-local", model="small")
"""

# Base classes and interfaces
# Import provider modules to trigger registration
# These imports register providers with ProviderRegistry
from . import (
    document,
    transcription,
    webpage,
)
from .base import ContentProvider, ProviderResult

# Fallback provider wrapper
from .fallback import (
    FallbackCondition,
    FallbackDocumentProvider,
    FallbackProvider,
    FallbackTranscriptionProvider,
    FallbackWebPageProvider,
    create_fallback_provider,
    matches_condition,
)

# Proxy service abstraction
from .proxy import (
    ProxyConfig,
    ProxyService,
    get_proxy_for_provider,
    get_youtube_proxy_config,
)

# Provider registry
from .registry import ProviderNotFoundError, ProviderRegistry

# YouTube transcript providers (kept separate for backwards compatibility)
from .youtube import (
    AutoFallbackProvider,
    TranscriptAPIProvider,
    TranscriptProvider,
    YouTubeTranscriptAPIProvider,
    create_provider,
    create_provider_from_config,
    create_proxy_config,
)

__all__ = [
    "AutoFallbackProvider",
    "ContentProvider",
    "FallbackCondition",
    "FallbackDocumentProvider",
    "FallbackProvider",
    "FallbackTranscriptionProvider",
    "FallbackWebPageProvider",
    "ProviderNotFoundError",
    "ProviderRegistry",
    "ProviderResult",
    "ProxyConfig",
    "ProxyService",
    "TranscriptAPIProvider",
    "TranscriptProvider",
    "YouTubeTranscriptAPIProvider",
    "create_fallback_provider",
    "create_provider",
    "create_provider_from_config",
    "create_proxy_config",
    "get_proxy_for_provider",
    "get_youtube_proxy_config",
    "matches_condition",
]
