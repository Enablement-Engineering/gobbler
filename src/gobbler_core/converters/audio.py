"""Audio/video transcription module using faster-whisper with Metal/CoreML acceleration.

This module provides audio transcription capabilities with support for
pluggable transcription providers. The default provider uses faster-whisper
with CoreML acceleration on M-series Macs.

Example:
    # Using default provider
    markdown, metadata = await convert_audio_to_markdown("audio.mp3")

    # Using a specific provider
    from gobbler_core.providers.transcription import WhisperLocalProvider
    provider = WhisperLocalProvider(model="large")
    markdown, metadata = await convert_audio_to_markdown("audio.mp3", provider=provider)
"""

# ruff: noqa: PTH108, PTH110, PTH202

from __future__ import annotations

import contextlib
import logging
import os
import subprocess
import tempfile
import time
from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING, Any

from faster_whisper import WhisperModel

from gobbler_core.utils.file_handler import get_file_extension, validate_input_path
from gobbler_core.utils.frontmatter import count_words, create_audio_frontmatter
from gobbler_core.utils.redaction import neutralize_github_mentions

if TYPE_CHECKING:
    from gobbler_core.providers.transcription import TranscriptionProvider, TranscriptionResult

logger = logging.getLogger(__name__)

SUPPORTED_EXTENSIONS = (".mp3", ".wav", ".flac", ".m4a", ".mp4", ".mov", ".avi", ".mkv")
VALID_MODELS = ("tiny", "base", "small", "medium", "large")
# Files larger than 50MB should be pre-processed to extract audio
MAX_FILE_SIZE_BYTES = 50 * 1024 * 1024

# Global model instance (lazy loaded) - kept for backwards compatibility
_whisper_model = None
_current_model_size = None


def format_timestamp(seconds: float) -> str:
    """Format seconds into MM:SS or HH:MM:SS timestamp.

    Args:
        seconds: Time in seconds

    Returns:
        Formatted timestamp string
    """
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)

    if hours > 0:
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"
    return f"{minutes:02d}:{secs:02d}"


async def _extract_audio(video_path: str) -> str:
    """Extract audio from video file to compressed MP3.

    Uses ffmpeg to extract audio track and convert to mono 16kHz MP3,
    significantly reducing file size for large videos.

    Args:
        video_path: Path to source video file

    Returns:
        Path to temporary MP3 file

    Raises:
        RuntimeError: If ffmpeg extraction fails
    """
    # Create temporary file for extracted audio
    temp_fd, temp_path = tempfile.mkstemp(suffix=".mp3", prefix="gobbler_audio_")
    os.close(temp_fd)  # Close fd, we'll write via ffmpeg

    try:
        # Extract audio using ffmpeg
        # -vn: no video
        # -acodec libmp3lame: MP3 codec
        # -ar 16000: 16kHz sample rate (sufficient for speech)
        # -ac 1: mono (reduces size)
        # -y: overwrite output file
        # Using ffmpeg with fixed arguments for audio extraction
        # video_path is validated earlier in convert_audio_to_markdown via validate_input_path
        result = subprocess.run(  # nosec B603 B607
            [
                "ffmpeg",
                "-i",
                video_path,
                "-vn",
                "-acodec",
                "libmp3lame",
                "-ar",
                "16000",
                "-ac",
                "1",
                "-y",
                temp_path,
            ],
            check=False,
            capture_output=True,
            text=True,
            timeout=3600,  # 60 minute timeout for extraction (handles very large files)
        )

        if result.returncode != 0:
            # Clean up temp file on error
            if os.path.exists(temp_path):
                os.unlink(temp_path)
            msg = f"ffmpeg audio extraction failed: {result.stderr}"
            raise RuntimeError(msg)
        else:  # noqa: RET506
            return temp_path

    except subprocess.TimeoutExpired as err:
        if os.path.exists(temp_path):
            os.unlink(temp_path)
        msg = "Audio extraction timed out after 60 minutes"
        raise RuntimeError(msg) from err
    except FileNotFoundError as err:
        if os.path.exists(temp_path):
            os.unlink(temp_path)
        msg = "ffmpeg not found. Please install ffmpeg to process large video files."
        raise RuntimeError(msg) from err
    except Exception as e:
        if os.path.exists(temp_path):
            os.unlink(temp_path)
        msg = f"Audio extraction failed: {e}"
        raise RuntimeError(msg) from e


def _get_whisper_model(model_size: str) -> WhisperModel:
    """Get or initialize Whisper model.

    Models are cached globally to avoid reloading on each transcription.
    On M-series Macs, automatically uses CoreML acceleration.

    Args:
        model_size: Size of model (tiny, base, small, medium, large)

    Returns:
        WhisperModel instance
    """
    global _whisper_model, _current_model_size  # noqa: PLW0603

    # Return cached model if same size
    if _whisper_model is not None and _current_model_size == model_size:
        return _whisper_model

    logger.info("Loading Whisper model: %s", model_size)

    # Load model with optimal settings for M-series
    # compute_type="auto" uses CoreML on M-series, CPU on others
    _whisper_model = WhisperModel(
        model_size,
        device="cpu",  # faster-whisper uses CPU/CoreML, not CUDA
        compute_type="auto",  # Automatically uses CoreML on M-series
    )
    _current_model_size = model_size

    logger.info("Whisper model loaded: %s", model_size)
    return _whisper_model


async def convert_audio_to_markdown(  # noqa: C901, PLR0912, PLR0915
    file_path: str,
    model: str = "small",
    language: str = "auto",
    include_timestamps: bool = False,
    metrics_callback: Callable[[str, int], None] | None = None,
    logger_instance: logging.Logger | None = None,
    provider: TranscriptionProvider | None = None,
) -> tuple[str, dict[str, Any]]:
    """Transcribe audio/video to markdown using a transcription provider.

    Uses a pluggable transcription provider for the actual transcription.
    If no provider is specified, uses the default WhisperLocalProvider with
    automatic CoreML acceleration on M-series Macs.

    Args:
        file_path: Absolute path to audio/video file
        model: Whisper model size (tiny, base, small, medium, large)
            Only used if provider is None (default provider)
        language: Language code (ISO 639-1) or 'auto' for detection
        include_timestamps: Include timestamp markers in output (default: False)
        metrics_callback: Optional callback for metrics tracking,
            called with (converter_type, size_bytes)
        logger_instance: Optional custom logger instance
        provider: Optional transcription provider. If None, uses default
            WhisperLocalProvider with the specified model.

    Returns:
        Tuple of (markdown_content, metadata)

    Raises:
        ValueError: Invalid file path, unsupported format, or invalid model
        RuntimeError: Transcription failed or file read error

    Example:
        # Using default provider
        markdown, metadata = await convert_audio_to_markdown("audio.mp3")

        # Using a specific provider
        from gobbler_core.providers.transcription import WhisperLocalProvider
        provider = WhisperLocalProvider(model="large")
        markdown, metadata = await convert_audio_to_markdown("audio.mp3", provider=provider)

        # With timestamps
        markdown, metadata = await convert_audio_to_markdown("audio.mp3", include_timestamps=True)
    """
    # Use provided logger or fall back to module-level logger
    log = logger_instance if logger_instance is not None else logger

    # Validate file path
    error = validate_input_path(file_path, SUPPORTED_EXTENSIONS)
    if error:
        raise ValueError(error)

    file_format = get_file_extension(file_path)

    log.info(
        "Starting audio transcription",
        extra={
            "extra_fields": {
                "file_path": file_path,
                "file_format": file_format,
                "model": model,
                "language": language,
                "provider": provider.name if provider else "whisper-local",
            }
        },
    )
    start_time = time.time()

    # Store transcription result for timestamp formatting
    transcription_result: TranscriptionResult | None = None

    # Use provider-based transcription if a provider is specified
    if provider is not None:
        result = await provider.transcribe(Path(file_path), language=language)
        transcription_result = result
        transcript_text = result.text
        detected_language = result.language
        duration = int(result.duration)
        provider_name = provider.name
    else:
        # Legacy path: use built-in whisper model directly
        # Validate model only for legacy path
        if model not in VALID_MODELS:
            msg = f"Invalid model: {model}. Supported models: {', '.join(VALID_MODELS)}"
            raise ValueError(msg)

        # Check file size and extract audio if needed
        file_size = os.path.getsize(file_path)
        temp_file: str | None = None
        processing_file = file_path

        if file_size > MAX_FILE_SIZE_BYTES:
            file_size_mb = file_size / 1024 / 1024
            log.info(
                "File size (%.1fMB) exceeds threshold. Extracting audio to compressed format...",
                file_size_mb,
            )
            temp_file = await _extract_audio(file_path)
            processing_file = temp_file
            temp_file_size_mb = os.path.getsize(temp_file) / 1024 / 1024
            log.info("Audio extracted to temporary file (%.1fMB)", temp_file_size_mb)

        # Get Whisper model
        try:
            whisper = _get_whisper_model(model)
        except Exception as e:
            # Clean up temp file on error
            if temp_file:
                with contextlib.suppress(OSError):
                    os.unlink(temp_file)
            msg = f"Failed to load Whisper model: {e}"
            raise RuntimeError(msg) from e

        # Transcribe audio
        try:
            log.info("Starting transcription with faster-whisper...")

            # Prepare language parameter
            lang = None if language == "auto" else language

            # Transcribe (this is synchronous but fast with CoreML)
            segments, info = whisper.transcribe(
                processing_file,
                language=lang,
                beam_size=5,
                vad_filter=True,  # Voice activity detection helps filter silence
            )

            # Build transcript from segments
            # Import here to avoid circular imports at module level
            from gobbler_core.providers.transcription import (
                TranscriptionResult as TResult,
                TranscriptionSegment,
            )

            transcript_lines = []
            result_segments: list[TranscriptionSegment] = []
            duration = 0

            for segment in segments:
                transcript_lines.append(segment.text.strip())
                duration = max(duration, segment.end)
                result_segments.append(
                    TranscriptionSegment(
                        text=segment.text.strip(),
                        start=segment.start,
                        end=segment.end,
                    )
                )

            transcript_text = " ".join(transcript_lines).strip()
            detected_language = info.language

            # Build TranscriptionResult for consistent handling with provider path
            transcription_result = TResult(
                text=transcript_text,
                segments=result_segments,
                language=detected_language,
                duration=duration,
            )

            if not transcript_text:
                msg = (
                    "Transcription failed: Unable to detect speech in audio. "
                    "The file may be corrupted, silent, or in an unsupported language."
                )
                raise RuntimeError(msg)

        except Exception as e:
            # Clean up temp file on error
            if temp_file:
                with contextlib.suppress(OSError):
                    os.unlink(temp_file)
            msg = f"Transcription failed: {e}"
            raise RuntimeError(msg) from e
        finally:
            # Clean up temporary file if created
            if temp_file and os.path.exists(temp_file):
                try:
                    os.unlink(temp_file)
                    log.debug("Cleaned up temporary file: %s", temp_file)
                except Exception as e:
                    log.warning("Failed to delete temporary file %s: %s", temp_file, e)

        duration = int(duration)
        provider_name = "whisper-local"

    conversion_time_ms = int((time.time() - start_time) * 1000)
    word_count = count_words(transcript_text)

    # Create frontmatter
    frontmatter = create_audio_frontmatter(
        file_path=file_path,
        duration=duration,
        language=detected_language,
        model=model,
        word_count=word_count,
        conversion_time_ms=conversion_time_ms,
    )

    # Build transcript text with optional timestamps
    if include_timestamps and transcription_result is not None and transcription_result.segments:
        lines = []
        for segment in transcription_result.segments:
            timestamp = format_timestamp(segment.start)
            lines.append(f"[{timestamp}] {segment.text}")
        formatted_transcript = "\n\n".join(lines)
    else:
        formatted_transcript = transcript_text

    # Build markdown content
    markdown = neutralize_github_mentions(
        frontmatter + "# Audio Transcript\n\n" + formatted_transcript
    )

    # Track conversion size if callback provided
    if metrics_callback is not None:
        metrics_callback("audio", len(markdown))

    # Build metadata
    metadata = {
        "file_path": file_path,
        "duration": duration,
        "language": detected_language,
        "model": model if provider is None else provider_name,
        "word_count": word_count,
        "conversion_time_ms": conversion_time_ms,
        "provider": provider_name,
    }

    log.info(
        "Audio transcription completed",
        extra={
            "extra_fields": {
                "word_count": word_count,
                "duration": duration,
                "language": detected_language,
                "model": model if provider is None else provider_name,
                "conversion_time_ms": conversion_time_ms,
                "provider": provider_name,
            }
        },
    )

    return markdown, metadata
