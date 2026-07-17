"""Local Whisper transcription provider using faster-whisper.

This provider uses the faster-whisper library and CTranslate2 for local
transcription. The current provider requests CPU execution.
"""

from __future__ import annotations

import contextlib
import logging
import os
import subprocess
import tempfile
from pathlib import Path
from typing import Any, ClassVar

from faster_whisper import WhisperModel

from gobbler_core.providers.registry import ProviderRegistry
from gobbler_core.providers.transcription.base import (
    TranscriptionProvider,
    TranscriptionResult,
    TranscriptionSegment,
)

logger = logging.getLogger(__name__)

# Supported audio/video formats
SUPPORTED_EXTENSIONS: set[str] = {
    ".mp3",
    ".wav",
    ".flac",
    ".m4a",
    ".mp4",
    ".mov",
    ".avi",
    ".mkv",
    ".webm",
    ".ogg",
}

# Valid Whisper model sizes
VALID_MODELS: tuple[str, ...] = ("tiny", "base", "small", "medium", "large")

# Files larger than 50MB should be pre-processed to extract audio
MAX_FILE_SIZE_BYTES: int = 50 * 1024 * 1024


class WhisperLocalProvider(TranscriptionProvider):
    """Local transcription provider using faster-whisper.

    Uses the faster-whisper library with CTranslate2 on CPU. Models are
    cached globally to avoid reloading.

    Attributes:
        model_size: Whisper model size (tiny, base, small, medium, large)

    Example:
        provider = WhisperLocalProvider(model="small")
        result = await provider.transcribe(Path("audio.mp3"), language="en")
        print(result.text)
    """

    # Class-level model cache for reuse across instances
    _model_cache: ClassVar[dict[str, WhisperModel]] = {}

    def __init__(self, model: str = "small") -> None:
        """Initialize the Whisper provider.

        Args:
            model: Whisper model size (tiny, base, small, medium, large)

        Raises:
            ValueError: If model size is invalid
        """
        if model not in VALID_MODELS:
            msg = f"Invalid model: {model}. Supported models: {', '.join(VALID_MODELS)}"
            raise ValueError(msg)

        self.model_size = model
        self._ensure_model_loaded()

    @property
    def name(self) -> str:
        """Return provider name."""
        return "whisper-local"

    @staticmethod
    def _raise_no_speech_error() -> None:
        """Raise error when no speech is detected."""
        msg = (
            "Transcription failed: Unable to detect speech in audio. "
            "The file may be corrupted, silent, or in an unsupported language."
        )
        raise RuntimeError(msg)

    def _ensure_model_loaded(self) -> WhisperModel:
        """Ensure the Whisper model is loaded and cached.

        Returns:
            Loaded WhisperModel instance
        """
        if self.model_size not in self._model_cache:
            logger.info("Loading Whisper model: %s", self.model_size)
            self._model_cache[self.model_size] = WhisperModel(
                self.model_size,
                device="cpu",
                compute_type="auto",
            )
            logger.info("Whisper model loaded: %s", self.model_size)

        return self._model_cache[self.model_size]

    async def transcribe(
        self,
        audio_path: Path,
        language: str = "auto",
        **options: Any,
    ) -> TranscriptionResult:
        """Transcribe audio/video file using faster-whisper.

        Args:
            audio_path: Path to audio or video file
            language: Language code (ISO 639-1) or "auto" for detection
            **options: Additional options:
                - beam_size (int): Beam size for decoding (default: 5)
                - vad_filter (bool): Enable voice activity detection (default: True)

        Returns:
            TranscriptionResult with transcribed text and segments

        Raises:
            FileNotFoundError: If audio_path doesn't exist
            ValueError: If file format is not supported
            RuntimeError: If transcription fails
        """
        # Validate file exists
        if not audio_path.exists():
            msg = f"Audio file not found: {audio_path}"
            raise FileNotFoundError(msg)

        # Validate format
        ext = audio_path.suffix.lower()
        if not self.supports_format(ext):
            msg = f"Unsupported format: {ext}. Supported: {', '.join(sorted(SUPPORTED_EXTENSIONS))}"
            raise ValueError(msg)

        # Check file size and extract audio if needed
        file_size = audio_path.stat().st_size
        temp_file: Path | None = None
        processing_path = audio_path

        if file_size > MAX_FILE_SIZE_BYTES:
            file_size_mb = file_size / 1024 / 1024
            logger.info(
                "File size (%.1fMB) exceeds threshold. Extracting audio...",
                file_size_mb,
            )
            temp_file = await self._extract_audio(audio_path)
            processing_path = temp_file

        try:
            return await self._do_transcribe(
                processing_path,
                language=language,
                **options,
            )
        finally:
            # Clean up temp file
            if temp_file and temp_file.exists():
                with contextlib.suppress(OSError):
                    temp_file.unlink()
                    logger.debug("Cleaned up temporary file: %s", temp_file)

    async def _do_transcribe(
        self,
        audio_path: Path,
        language: str = "auto",
        **options: Any,
    ) -> TranscriptionResult:
        """Perform the actual transcription.

        Args:
            audio_path: Path to audio file (may be temp file)
            language: Language code or "auto"
            **options: Transcription options

        Returns:
            TranscriptionResult
        """
        model = self._ensure_model_loaded()

        # Prepare options
        beam_size = options.get("beam_size", 5)
        vad_filter = options.get("vad_filter", True)
        lang = None if language == "auto" else language

        logger.info("Starting transcription with faster-whisper...")

        try:
            # Transcribe (synchronous but fast with CoreML)
            segments_gen, info = model.transcribe(
                str(audio_path),
                language=lang,
                beam_size=beam_size,
                vad_filter=vad_filter,
            )

            # Build segments list
            segments: list[TranscriptionSegment] = []
            text_parts: list[str] = []
            duration = 0.0

            for segment in segments_gen:
                text = segment.text.strip()
                if text:
                    text_parts.append(text)
                    # Note: faster-whisper doesn't provide per-segment confidence
                    segments.append(
                        TranscriptionSegment(
                            text=text,
                            start=segment.start,
                            end=segment.end,
                            confidence=None,
                        )
                    )
                duration = max(duration, segment.end)

            full_text = " ".join(text_parts)

            if not full_text:
                self._raise_no_speech_error()

            return TranscriptionResult(
                text=full_text,
                segments=segments,
                language=info.language,
                duration=duration,
                metadata={
                    "model": self.model_size,
                    "language_probability": info.language_probability,
                },
            )

        except RuntimeError:
            raise
        except Exception as e:
            msg = f"Transcription failed: {e}"
            raise RuntimeError(msg) from e

    async def _extract_audio(self, video_path: Path) -> Path:
        """Extract audio from video file to compressed MP3.

        Uses ffmpeg to extract audio track and convert to mono 16kHz MP3.

        Args:
            video_path: Path to source video file

        Returns:
            Path to temporary MP3 file

        Raises:
            RuntimeError: If ffmpeg extraction fails
        """
        # Create temporary file for extracted audio
        temp_fd, temp_path_str = tempfile.mkstemp(suffix=".mp3", prefix="gobbler_audio_")
        os.close(temp_fd)
        temp_path = Path(temp_path_str)

        try:
            # Extract audio using ffmpeg
            result = subprocess.run(
                [
                    "ffmpeg",
                    "-i",
                    str(video_path),
                    "-vn",
                    "-acodec",
                    "libmp3lame",
                    "-ar",
                    "16000",
                    "-ac",
                    "1",
                    "-y",
                    str(temp_path),
                ],
                check=False,
                capture_output=True,
                text=True,
                timeout=3600,
            )

            if result.returncode != 0:
                if temp_path.exists():
                    temp_path.unlink()
                msg = f"ffmpeg audio extraction failed: {result.stderr}"
                raise RuntimeError(msg)

            return temp_path  # noqa: TRY300

        except subprocess.TimeoutExpired as err:
            if temp_path.exists():
                temp_path.unlink()
            msg = "Audio extraction timed out after 60 minutes"
            raise RuntimeError(msg) from err
        except FileNotFoundError as err:
            if temp_path.exists():
                temp_path.unlink()
            msg = "ffmpeg not found. Please install ffmpeg to process large video files."
            raise RuntimeError(msg) from err
        except RuntimeError:
            raise
        except Exception as e:
            if temp_path.exists():
                temp_path.unlink()
            msg = f"Audio extraction failed: {e}"
            raise RuntimeError(msg) from e

    def supports_format(self, file_extension: str) -> bool:
        """Check if file format is supported.

        Args:
            file_extension: File extension including dot (e.g., ".mp3")

        Returns:
            True if format is supported
        """
        return file_extension.lower() in SUPPORTED_EXTENSIONS


# Register provider with the registry
ProviderRegistry.register("transcription", "whisper-local", WhisperLocalProvider)
