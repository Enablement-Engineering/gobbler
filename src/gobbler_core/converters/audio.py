"""Audio/video transcription module using faster-whisper with Metal/CoreML acceleration."""

# ruff: noqa: PTH108, PTH110, PTH202

import contextlib
import logging
import os
import subprocess
import tempfile
import time
from collections.abc import Callable

from faster_whisper import WhisperModel

from gobbler_core.utils.file_handler import get_file_extension, validate_input_path
from gobbler_core.utils.frontmatter import count_words, create_audio_frontmatter

logger = logging.getLogger(__name__)

SUPPORTED_EXTENSIONS = (".mp3", ".wav", ".flac", ".m4a", ".mp4", ".mov", ".avi", ".mkv")
VALID_MODELS = ("tiny", "base", "small", "medium", "large")
# Files larger than 50MB should be pre-processed to extract audio
MAX_FILE_SIZE_BYTES = 50 * 1024 * 1024

# Global model instance (lazy loaded)
_whisper_model = None
_current_model_size = None


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
        result = subprocess.run(  # noqa: S603  # nosec B603 B607
            [  # noqa: S607
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
            raise RuntimeError(msg)  # noqa: TRY301
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


async def convert_audio_to_markdown(  # noqa: C901, PLR0915
    file_path: str,
    model: str = "small",
    language: str = "auto",
    metrics_callback: Callable[[str, int], None] | None = None,
    logger_instance: logging.Logger | None = None,
) -> tuple[str, dict]:
    """Transcribe audio/video to markdown using faster-whisper with Metal/CoreML acceleration.

    Uses local faster-whisper library with automatic CoreML acceleration on M-series Macs.
    Supports automatic language detection and various audio/video formats via ffmpeg.

    Args:
        file_path: Absolute path to audio/video file
        model: Whisper model size (tiny, base, small, medium, large)
        language: Language code (ISO 639-1) or 'auto' for detection
        metrics_callback: Optional callback for metrics tracking,
            called with (converter_type, size_bytes)
        logger_instance: Optional custom logger instance

    Returns:
        Tuple of (markdown_content, metadata)

    Raises:
        ValueError: Invalid file path, unsupported format, or invalid model
        RuntimeError: Transcription failed or file read error
    """
    # Use provided logger or fall back to module-level logger
    log = logger_instance if logger_instance is not None else logger

    # Validate file path
    error = validate_input_path(file_path, SUPPORTED_EXTENSIONS)
    if error:
        raise ValueError(error)

    # Validate model
    if model not in VALID_MODELS:
        msg = f"Invalid model: {model}. Supported models: {', '.join(VALID_MODELS)}"
        raise ValueError(msg)

    file_format = get_file_extension(file_path)

    log.info(
        "Starting audio transcription",
        extra={
            "extra_fields": {
                "file_path": file_path,
                "file_format": file_format,
                "model": model,
                "language": language,
            }
        },
    )
    start_time = time.time()

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
        transcript_lines = []
        duration = 0

        for segment in segments:
            transcript_lines.append(segment.text.strip())
            duration = max(duration, segment.end)

        transcript_text = " ".join(transcript_lines).strip()
        detected_language = info.language

        if not transcript_text:
            msg = (
                "Transcription failed: Unable to detect speech in audio. "
                "The file may be corrupted, silent, or in an unsupported language."
            )
            raise RuntimeError(msg)  # noqa: TRY301

    except Exception as e:
        # Clean up temp file on error
        if temp_file:
            with contextlib.suppress(OSError):
                os.unlink(temp_file)
        msg = f"Transcription failed: {e}"
        raise RuntimeError(msg) from e

    conversion_time_ms = int((time.time() - start_time) * 1000)
    word_count = count_words(transcript_text)
    duration = int(duration)

    # Create frontmatter
    frontmatter = create_audio_frontmatter(
        file_path=file_path,
        duration=duration,
        language=detected_language,
        model=model,
        word_count=word_count,
        conversion_time_ms=conversion_time_ms,
    )

    # Build markdown content
    markdown = frontmatter + "# Audio Transcript\n\n" + transcript_text

    # Track conversion size if callback provided
    if metrics_callback is not None:
        metrics_callback("audio", len(markdown))

    # Build metadata
    metadata = {
        "file_path": file_path,
        "duration": duration,
        "language": detected_language,
        "model": model,
        "word_count": word_count,
        "conversion_time_ms": conversion_time_ms,
    }

    log.info(
        "Audio transcription completed",
        extra={
            "extra_fields": {
                "word_count": word_count,
                "duration": duration,
                "language": detected_language,
                "model": model,
                "conversion_time_ms": conversion_time_ms,
            }
        },
    )

    # Clean up temporary file if created
    if temp_file and os.path.exists(temp_file):
        try:
            os.unlink(temp_file)
            log.debug("Cleaned up temporary file: %s", temp_file)
        except Exception as e:
            log.warning("Failed to delete temporary file %s: %s", temp_file, e)

    return markdown, metadata
