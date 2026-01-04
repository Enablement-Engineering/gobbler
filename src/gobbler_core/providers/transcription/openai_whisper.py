"""OpenAI Whisper API transcription provider.

This provider uses the OpenAI Whisper API for cloud-based transcription
with high accuracy and support for multiple languages.
"""

from __future__ import annotations

import contextlib
import logging
import os
import subprocess
import tempfile
from pathlib import Path
from typing import Any

import httpx

from gobbler_core.providers.registry import ProviderRegistry
from gobbler_core.providers.transcription.base import (
    TranscriptionProvider,
    TranscriptionResult,
    TranscriptionSegment,
)

logger = logging.getLogger(__name__)

# Supported audio formats for OpenAI Whisper API
SUPPORTED_EXTENSIONS: set[str] = {
    ".mp3",
    ".mp4",
    ".m4a",
    ".wav",
    ".webm",
    ".mpeg",
    ".mpga",
}

# OpenAI Whisper API file size limit (25MB)
MAX_FILE_SIZE_BYTES: int = 25 * 1024 * 1024

# OpenAI API endpoint
OPENAI_API_URL = "https://api.openai.com/v1/audio/transcriptions"

# HTTP status codes
HTTP_OK = 200


class OpenAIWhisperProvider(TranscriptionProvider):
    """Cloud transcription provider using OpenAI Whisper API.

    Uses the OpenAI Whisper API for high-quality cloud-based transcription.
    Supports automatic language detection and provides word-level timestamps.

    Attributes:
        api_key: OpenAI API key for authentication
        model: Whisper model to use (currently only "whisper-1")
        timeout: Request timeout in seconds

    Example:
        provider = OpenAIWhisperProvider(api_key="sk-...")
        result = await provider.transcribe(Path("audio.mp3"), language="en")
        print(result.text)
    """

    def __init__(
        self,
        api_key: str | None = None,
        model: str = "whisper-1",
        timeout: float = 120.0,
    ) -> None:
        """Initialize the OpenAI Whisper provider.

        Args:
            api_key: OpenAI API key. If not provided, reads from OPENAI_API_KEY env var.
            model: Whisper model to use (default: "whisper-1")
            timeout: Request timeout in seconds (default: 120.0)

        Raises:
            ValueError: If no API key is provided and OPENAI_API_KEY env var is not set
        """
        self._api_key = api_key or os.environ.get("OPENAI_API_KEY")
        if not self._api_key:
            msg = (
                "OpenAI API key not provided. "
                "Set OPENAI_API_KEY environment variable or pass api_key parameter."
            )
            raise ValueError(msg)

        # Valid OpenAI Whisper models - ignore local whisper model names
        valid_openai_models = {"whisper-1"}
        if model not in valid_openai_models:
            # If passed a local whisper model name (tiny/base/small/medium/large),
            # use the default OpenAI model instead
            logger.debug("Ignoring invalid OpenAI model '%s', using 'whisper-1'", model)
            model = "whisper-1"

        self.model = model
        self.timeout = timeout

    @property
    def name(self) -> str:
        """Return provider name."""
        return "openai-whisper"

    @staticmethod
    def _raise_file_too_large_error(extracted_size: int) -> None:
        """Raise error when extracted audio still exceeds size limit.

        Args:
            extracted_size: Size of extracted file in bytes

        Raises:
            RuntimeError: Always raises with file size error message
        """
        msg = (
            f"Extracted audio ({extracted_size / 1024 / 1024:.1f}MB) "
            f"still exceeds OpenAI limit (25MB). "
            f"Please provide a shorter audio file."
        )
        raise RuntimeError(msg)

    async def transcribe(
        self,
        audio_path: Path,
        language: str = "auto",
        **options: Any,
    ) -> TranscriptionResult:
        """Transcribe audio/video file using OpenAI Whisper API.

        Args:
            audio_path: Path to audio or video file
            language: Language code (ISO 639-1) or "auto" for detection
            **options: Additional options:
                - prompt (str): Optional text to guide the model's style
                - temperature (float): Sampling temperature (0.0 to 1.0)

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
                "File size (%.1fMB) exceeds OpenAI limit (25MB). Extracting compressed audio...",
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
        """Perform the actual transcription via OpenAI API.

        Args:
            audio_path: Path to audio file (may be temp file)
            language: Language code or "auto"
            **options: Additional transcription options

        Returns:
            TranscriptionResult

        Raises:
            RuntimeError: If API call fails
        """
        logger.info("Starting transcription with OpenAI Whisper API...")

        # Build form data
        form_data: dict[str, Any] = {
            "model": self.model,
            "response_format": "verbose_json",
        }

        # Only include language if not auto-detect
        if language != "auto":
            form_data["language"] = language

        # Add optional parameters
        if "prompt" in options:
            form_data["prompt"] = options["prompt"]
        if "temperature" in options:
            form_data["temperature"] = options["temperature"]

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                with audio_path.open("rb") as audio_file:
                    files = {"file": (audio_path.name, audio_file, "audio/mpeg")}
                    response = await client.post(
                        OPENAI_API_URL,
                        headers={"Authorization": f"Bearer {self._api_key}"},
                        data=form_data,
                        files=files,
                    )

                if response.status_code != HTTP_OK:
                    error_detail = response.text
                    msg = f"OpenAI API error ({response.status_code}): {error_detail}"
                    raise RuntimeError(msg)

                data = response.json()

            return self._parse_response(data)

        except httpx.TimeoutException as e:
            msg = f"OpenAI API request timed out after {self.timeout}s"
            raise RuntimeError(msg) from e
        except httpx.RequestError as e:
            msg = f"OpenAI API request failed: {e}"
            raise RuntimeError(msg) from e
        except RuntimeError:
            raise
        except Exception as e:
            msg = f"Transcription failed: {e}"
            raise RuntimeError(msg) from e

    def _parse_response(self, data: dict[str, Any]) -> TranscriptionResult:
        """Parse OpenAI API response into TranscriptionResult.

        Args:
            data: JSON response from OpenAI API

        Returns:
            TranscriptionResult with segments and metadata
        """
        text = data.get("text", "")
        language = data.get("language", "unknown")
        duration = data.get("duration", 0.0)

        # Parse segments from verbose_json response
        segments: list[TranscriptionSegment] = []
        raw_segments = data.get("segments", [])

        for seg in raw_segments:
            segment_text = seg.get("text", "").strip()
            if segment_text:
                segments.append(
                    TranscriptionSegment(
                        text=segment_text,
                        start=seg.get("start", 0.0),
                        end=seg.get("end", 0.0),
                        confidence=seg.get("avg_logprob"),
                    )
                )

        return TranscriptionResult(
            text=text,
            segments=segments,
            language=language,
            duration=duration,
            metadata={
                "model": self.model,
                "provider": self.name,
            },
        )

    async def _extract_audio(self, video_path: Path) -> Path:
        """Extract audio from video file to compressed MP3.

        Uses ffmpeg to extract audio track and convert to mono 16kHz MP3
        to reduce file size below OpenAI's 25MB limit.

        Args:
            video_path: Path to source video file

        Returns:
            Path to temporary MP3 file

        Raises:
            RuntimeError: If ffmpeg extraction fails
        """
        # Create temporary file for extracted audio
        temp_fd, temp_path_str = tempfile.mkstemp(suffix=".mp3", prefix="gobbler_openai_audio_")
        os.close(temp_fd)
        temp_path = Path(temp_path_str)

        try:
            # Extract audio using ffmpeg with aggressive compression
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
                    "-b:a",
                    "64k",  # Low bitrate for smaller file size
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

            # Verify the extracted file is under the limit
            extracted_size = temp_path.stat().st_size
            if extracted_size > MAX_FILE_SIZE_BYTES:
                temp_path.unlink()
                self._raise_file_too_large_error(extracted_size)

            logger.info(
                "Extracted audio: %.1fMB (original: %.1fMB)",
                extracted_size / 1024 / 1024,
                video_path.stat().st_size / 1024 / 1024,
            )
            return temp_path  # noqa: TRY300

        except subprocess.TimeoutExpired as err:
            if temp_path.exists():
                temp_path.unlink()
            msg = "Audio extraction timed out after 60 minutes"
            raise RuntimeError(msg) from err
        except FileNotFoundError as err:
            if temp_path.exists():
                temp_path.unlink()
            msg = "ffmpeg not found. Please install ffmpeg to process large audio files."
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
ProviderRegistry.register("transcription", "openai-whisper", OpenAIWhisperProvider)
