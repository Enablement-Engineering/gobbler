"""Transcript and content providers for Gobbler."""

# Base classes and interfaces
from .base import ContentProvider, ProviderResult

# YouTube transcript providers
from .youtube import (
    TranscriptProvider,
    YouTubeTranscriptAPIProvider,
    TranscriptAPIProvider,
    AutoFallbackProvider,
    create_proxy_config,
    create_provider,
)

__all__ = [
    # Base classes
    "ContentProvider",
    "ProviderResult",
    # YouTube providers
    "TranscriptProvider",
    "YouTubeTranscriptAPIProvider",
    "TranscriptAPIProvider",
    "AutoFallbackProvider",
    "create_proxy_config",
    "create_provider",
]
