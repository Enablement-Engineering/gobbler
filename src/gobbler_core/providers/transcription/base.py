"""Base classes for transcription providers.

This module defines the abstract interface for audio/video transcription
providers in Gobbler.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class TranscriptionSegment:
    """A single segment of a transcription with timing information.

    Attributes:
        text: The transcribed text for this segment
        start: Start time in seconds
        end: End time in seconds
        confidence: Optional confidence score (0.0 to 1.0)
    """

    text: str
    start: float
    end: float
    confidence: float | None = None


@dataclass
class TranscriptionResult:
    """Result from a transcription provider.

    Attributes:
        text: Full transcribed text
        segments: List of timed segments
        language: Detected or specified language code
        duration: Total audio duration in seconds
        metadata: Additional provider-specific metadata
    """

    text: str
    segments: list[TranscriptionSegment]
    language: str
    duration: float
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def word_count(self) -> int:
        """Get approximate word count of transcription."""
        return len(self.text.split())


class TranscriptionProvider(ABC):
    """Abstract base class for transcription providers.

    All transcription providers must implement this interface to ensure
    consistent behavior across different backends (e.g., local Whisper,
    OpenAI API, Deepgram, etc.).

    Example:
        class MyTranscriptionProvider(TranscriptionProvider):
            @property
            def name(self) -> str:
                return "my-provider"

            async def transcribe(
                self,
                audio_path: Path,
                language: str = "auto",
                **options,
            ) -> TranscriptionResult:
                # Implementation here
                pass

            def supports_format(self, file_extension: str) -> bool:
                return file_extension.lower() in {".mp3", ".wav", ".m4a"}
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Provider name for identification and logging.

        Returns:
            Unique provider identifier in kebab-case (e.g., "whisper-local")
        """

    @abstractmethod
    async def transcribe(
        self,
        audio_path: Path,
        language: str = "auto",
        **options: Any,
    ) -> TranscriptionResult:
        """Transcribe audio/video file to text.

        Args:
            audio_path: Path to audio or video file
            language: Language code (ISO 639-1) or "auto" for detection
            **options: Provider-specific options (e.g., model size, word timestamps)

        Returns:
            TranscriptionResult with text, segments, and metadata

        Raises:
            FileNotFoundError: If audio_path doesn't exist
            ValueError: If file format is not supported
            RuntimeError: If transcription fails
        """

    @abstractmethod
    def supports_format(self, file_extension: str) -> bool:
        """Check if this provider supports the given file format.

        Args:
            file_extension: File extension including dot (e.g., ".mp3")

        Returns:
            True if format is supported
        """

    def __repr__(self) -> str:
        """Return string representation of provider."""
        return f"{self.__class__.__name__}(name={self.name!r})"
