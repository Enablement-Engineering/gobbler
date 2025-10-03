"""Audio/video transcription module using faster-whisper with Metal/CoreML acceleration."""

import logging
import os
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Dict, Tuple

from faster_whisper import WhisperModel

from ..utils.file_handler import get_file_extension, validate_input_path
from ..utils.frontmatter import count_words, create_audio_frontmatter

logger = logging.getLogger(__name__)

SUPPORTED_EXTENSIONS = (".mp3", ".wav", ".flac", ".m4a", ".mp4", ".mov", ".avi", ".mkv")
VALID_MODELS = ("tiny", "base", "small", "medium", "large")
# Files larger than 50MB should be pre-processed to extract audio
MAX_FILE_SIZE_BYTES = 50 * 1024 * 1024

# Global model instance (lazy loaded)
_whisper_model = None
_current_model_size = None


async def _extract_audio(video_path: str) -> str:
    """
    Extract audio from video file to compressed MP3.

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
        result = subprocess.run(
            [
                "ffmpeg",
                "-i", video_path,
                "-vn",  # No video
                "-acodec", "libmp3lame",
                "-ar", "16000",  # 16kHz sample rate
                "-ac", "1",  # Mono
                "-y",  # Overwrite
                temp_path
            ],
            capture_output=True,
            text=True,
            timeout=300  # 5 minute timeout for extraction
        )

        if result.returncode != 0:
            # Clean up temp file on error
            if os.path.exists(temp_path):
                os.unlink(temp_path)
            raise RuntimeError(
                f"ffmpeg audio extraction failed: {result.stderr}"
            )

        return temp_path

    except subprocess.TimeoutExpired:
        if os.path.exists(temp_path):
            os.unlink(temp_path)
        raise RuntimeError("Audio extraction timed out after 5 minutes")
    except FileNotFoundError:
        if os.path.exists(temp_path):
            os.unlink(temp_path)
        raise RuntimeError(
            "ffmpeg not found. Please install ffmpeg to process large video files."
        )
    except Exception as e:
        if os.path.exists(temp_path):
            os.unlink(temp_path)
        raise RuntimeError(f"Audio extraction failed: {e}")


def _get_whisper_model(model_size: str) -> WhisperModel:
    """
    Get or initialize Whisper model.

    Models are cached globally to avoid reloading on each transcription.
    On M-series Macs, automatically uses CoreML acceleration.

    Args:
        model_size: Size of model (tiny, base, small, medium, large)

    Returns:
        WhisperModel instance
    """
    global _whisper_model, _current_model_size

    # Return cached model if same size
    if _whisper_model is not None and _current_model_size == model_size:
        return _whisper_model

    logger.info(f"Loading Whisper model: {model_size}")

    # Load model with optimal settings for M-series
    # compute_type="auto" uses CoreML on M-series, CPU on others
    _whisper_model = WhisperModel(
        model_size,
        device="cpu",  # faster-whisper uses CPU/CoreML, not CUDA
        compute_type="auto",  # Automatically uses CoreML on M-series
    )
    _current_model_size = model_size

    logger.info(f"Whisper model loaded: {model_size}")
    return _whisper_model


async def convert_audio_to_markdown(
    file_path: str,
    model: str = "small",
    language: str = "auto",
) -> Tuple[str, Dict]:
    """
    Transcribe audio/video to markdown using faster-whisper with Metal/CoreML acceleration.

    Uses local faster-whisper library with automatic CoreML acceleration on M-series Macs.
    Supports automatic language detection and various audio/video formats via ffmpeg.

    Args:
        file_path: Absolute path to audio/video file
        model: Whisper model size (tiny, base, small, medium, large)
        language: Language code (ISO 639-1) or 'auto' for detection

    Returns:
        Tuple of (markdown_content, metadata)

    Raises:
        ValueError: Invalid file path, unsupported format, or invalid model
        RuntimeError: Transcription failed or file read error
    """
    # Validate file path
    error = validate_input_path(file_path, SUPPORTED_EXTENSIONS)
    if error:
        raise ValueError(error)

    # Validate model
    if model not in VALID_MODELS:
        raise ValueError(
            f"Invalid model: {model}. Supported models: {', '.join(VALID_MODELS)}"
        )

    file_format = get_file_extension(file_path)

    logger.info(
        f"Transcribing audio: {file_path} (format: {file_format}, model: {model})"
    )
    start_time = time.time()

    # Check file size and extract audio if needed
    file_size = os.path.getsize(file_path)
    temp_file = None
    processing_file = file_path

    if file_size > MAX_FILE_SIZE_BYTES:
        logger.info(
            f"File size ({file_size / 1024 / 1024:.1f}MB) exceeds threshold. "
            "Extracting audio to compressed format..."
        )
        temp_file = await _extract_audio(file_path)
        processing_file = temp_file
        logger.info(
            f"Audio extracted to temporary file "
            f"({os.path.getsize(temp_file) / 1024 / 1024:.1f}MB)"
        )

    # Get Whisper model
    try:
        whisper = _get_whisper_model(model)
    except Exception as e:
        # Clean up temp file on error
        if temp_file and os.path.exists(temp_file):
            try:
                os.unlink(temp_file)
            except:
                pass
        raise RuntimeError(f"Failed to load Whisper model: {e}")

    # Transcribe audio
    try:
        logger.info("Starting transcription with faster-whisper...")

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
            raise RuntimeError(
                "Transcription failed: Unable to detect speech in audio. "
                "The file may be corrupted, silent, or in an unsupported language."
            )

    except Exception as e:
        # Clean up temp file on error
        if temp_file and os.path.exists(temp_file):
            try:
                os.unlink(temp_file)
            except:
                pass
        raise RuntimeError(f"Transcription failed: {e}")

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

    # Build metadata
    metadata = {
        "file_path": file_path,
        "duration": duration,
        "language": detected_language,
        "model": model,
        "word_count": word_count,
        "conversion_time_ms": conversion_time_ms,
    }

    logger.info(
        f"Transcription complete: {word_count} words, "
        f"{duration}s duration, language: {detected_language}"
    )

    # Clean up temporary file if created
    if temp_file and os.path.exists(temp_file):
        try:
            os.unlink(temp_file)
            logger.debug(f"Cleaned up temporary file: {temp_file}")
        except Exception as e:
            logger.warning(f"Failed to delete temporary file {temp_file}: {e}")

    return markdown, metadata
