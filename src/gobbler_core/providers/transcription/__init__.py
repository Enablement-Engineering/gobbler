"""Transcription providers for audio/video to text conversion.

This package provides abstracted transcription capabilities with multiple
backend implementations.

Available Providers:
    - whisper-local: Local faster-whisper transcription (default)
    - openai-whisper: OpenAI Whisper API (cloud-based, requires API key)

Example:
    from gobbler_core.providers.transcription import (
        TranscriptionProvider,
        WhisperLocalProvider,
        OpenAIWhisperProvider,
        get_default_provider,
    )

    # Use default provider from config
    provider = get_default_provider()
    result = await provider.transcribe(Path("audio.mp3"))

    # Or create specific provider
    provider = WhisperLocalProvider(model="small")
    result = await provider.transcribe(Path("audio.mp3"), language="en")

    # Use OpenAI Whisper API
    provider = OpenAIWhisperProvider()  # Uses OPENAI_API_KEY env var
    result = await provider.transcribe(Path("audio.mp3"), language="en")
"""

from gobbler_core.providers.transcription.base import (
    TranscriptionProvider,
    TranscriptionResult,
    TranscriptionSegment,
)
from gobbler_core.providers.transcription.openai_whisper import OpenAIWhisperProvider
from gobbler_core.providers.transcription.whisper import WhisperLocalProvider

__all__ = [
    "OpenAIWhisperProvider",
    "TranscriptionProvider",
    "TranscriptionResult",
    "TranscriptionSegment",
    "WhisperLocalProvider",
    "get_default_provider",
]


def get_default_provider(**kwargs) -> TranscriptionProvider:
    """Get the default transcription provider based on configuration.

    Args:
        **kwargs: Override configuration options

    Returns:
        Configured TranscriptionProvider instance
    """
    # Import here to avoid circular imports
    from gobbler_core.providers.registry import ProviderRegistry

    # Default to whisper-local if not configured
    # Config integration will be added when we update the config schema
    provider_name = kwargs.pop("provider", "whisper-local")

    return ProviderRegistry.create("transcription", provider_name, **kwargs)
