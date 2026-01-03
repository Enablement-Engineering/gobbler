"""Transcript and content providers for Gobbler."""

# Base classes and interfaces
from .base import ContentProvider, ProviderResult

# YouTube transcript providers
from .youtube import (
    AutoFallbackProvider,
    TranscriptAPIProvider,
    TranscriptProvider,
    YouTubeTranscriptAPIProvider,
    create_provider,
    create_proxy_config,
)

__all__ = [
    "AutoFallbackProvider",
    "ContentProvider",
    "ProviderResult",
    "TranscriptAPIProvider",
    "TranscriptProvider",
    "YouTubeTranscriptAPIProvider",
    "create_provider",
    "create_proxy_config",
]
