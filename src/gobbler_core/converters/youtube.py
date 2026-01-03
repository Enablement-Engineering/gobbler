"""YouTube transcript conversion module with proxy and fallback support."""

import logging
import re
from collections.abc import Callable

import yt_dlp

from gobbler_core.providers.youtube import (
    TranscriptProvider,
    create_provider,
    create_proxy_config,
)
from gobbler_core.utils.frontmatter import count_words, create_youtube_frontmatter

logger = logging.getLogger(__name__)


def extract_video_id(video_url: str) -> str:
    """Extract video ID from YouTube URL.

    Args:
        video_url: YouTube video URL

    Returns:
        11-character video ID

    Raises:
        ValueError: If URL format is invalid
    """
    pattern = r"^https?://(www\.)?(youtube\.com/watch\?v=|youtu\.be/)([a-zA-Z0-9_-]{11})"
    match = re.match(pattern, video_url)

    if not match:
        raise ValueError(
            "Invalid YouTube URL format. Expected: https://youtube.com/watch?v=VIDEO_ID "
            "or https://youtu.be/VIDEO_ID"
        )

    return match.group(3)


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


def get_video_metadata(video_url: str) -> dict[str, str | None]:
    """Extract video metadata using yt-dlp.

    Args:
        video_url: YouTube video URL

    Returns:
        Dictionary with title, channel, thumbnail URL, and description
    """
    ydl_opts = {
        "quiet": True,
        "no_warnings": True,
        "extract_flat": True,
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(video_url, download=False)
            return {
                "title": info.get("title"),
                "channel": info.get("channel") or info.get("uploader"),
                "thumbnail": info.get("thumbnail"),
                "description": info.get("description"),
            }
    except Exception as e:
        logger.warning(f"Failed to extract video metadata: {e}")
        return {"title": None, "channel": None, "thumbnail": None, "description": None}


async def convert_youtube_to_markdown(
    video_url: str,
    include_timestamps: bool = False,
    language: str = "auto",
    metrics_callback: Callable[[str, int], None] | None = None,
    provider: TranscriptProvider | None = None,
    logger_instance: logging.Logger | None = None,
) -> tuple[str, dict]:
    """Convert YouTube video to markdown transcript.

    Uses proxy and fallback providers based on environment configuration:
    - WEBSHARE_USER/WEBSHARE_PASS: Rotating proxy for free API
    - YOUTUBE_PROXY: Generic proxy URL
    - TRANSCRIPTAPI_KEY: Paid API fallback

    Args:
        video_url: YouTube video URL
        include_timestamps: Include timestamp markers
        language: Language code or 'auto'
        metrics_callback: Optional callback for metrics tracking (converter_type, size_bytes)
        provider: Optional pre-built TranscriptProvider instance
        logger_instance: Optional custom logger instance

    Returns:
        Tuple of (markdown_content, metadata)

    Raises:
        ValueError: Invalid URL
        RuntimeError: Transcript fetch failed
    """
    # Use custom logger or fall back to module logger
    active_logger = logger_instance or logger

    # Extract video ID
    video_id = extract_video_id(video_url)

    active_logger.info(
        "Starting YouTube conversion",
        extra={
            "extra_fields": {
                "video_url": video_url,
                "video_id": video_id,
                "language": language,
                "include_timestamps": include_timestamps,
            }
        },
    )

    # Get video metadata using yt-dlp (always reliable)
    video_metadata = get_video_metadata(video_url)

    # Use provided provider or create one with proxy/fallback support from environment
    if provider is None:
        proxy_config = create_proxy_config()
        provider = create_provider(provider_name="auto", proxy_config=proxy_config)

    # Fetch transcript using provider
    result = provider.fetch(video_id, language)

    # Merge metadata (prefer yt-dlp, fall back to provider)
    for key in ["title", "channel", "thumbnail"]:
        if not video_metadata.get(key) and result.metadata.get(key):
            video_metadata[key] = result.metadata[key]

    # Calculate duration
    total_duration = (
        result.segments[-1].start + result.segments[-1].duration if result.segments else 0
    )

    # Build transcript text
    lines = []
    for segment in result.segments:
        text = segment.text
        if include_timestamps:
            timestamp = format_timestamp(segment.start)
            lines.append(f"[{timestamp}] {text}")
        else:
            lines.append(text)

    transcript_text = "\n\n".join(lines)
    word_count = count_words(transcript_text)

    # Create frontmatter
    frontmatter = create_youtube_frontmatter(
        video_url=video_url,
        video_id=video_id,
        duration=int(total_duration),
        language=result.language,
        word_count=word_count,
        title=video_metadata.get("title"),
        channel=video_metadata.get("channel"),
        thumbnail=video_metadata.get("thumbnail"),
        description=video_metadata.get("description"),
    )

    # Combine into markdown
    markdown = frontmatter + "# Video Transcript\n\n" + transcript_text

    # Track conversion size if callback provided
    if metrics_callback is not None:
        metrics_callback("youtube", len(markdown))

    # Metadata for response
    metadata = {
        "video_id": video_id,
        "title": video_metadata.get("title"),
        "channel": video_metadata.get("channel"),
        "duration": int(total_duration),
        "language": result.language,
        "word_count": word_count,
    }

    active_logger.info(
        "YouTube conversion completed",
        extra={
            "extra_fields": {
                "video_id": video_id,
                "word_count": word_count,
                "language": result.language,
                "duration": int(total_duration),
            }
        },
    )

    return markdown, metadata
