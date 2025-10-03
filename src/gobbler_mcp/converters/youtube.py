"""YouTube transcript conversion module."""

import logging
import re
from typing import Dict, Optional, Tuple

import yt_dlp
from youtube_transcript_api import (
    NoTranscriptFound,
    TranscriptsDisabled,
    VideoUnavailable,
    YouTubeTranscriptApi,
)

from ..utils.frontmatter import count_words, create_youtube_frontmatter

logger = logging.getLogger(__name__)


def extract_video_id(video_url: str) -> str:
    """
    Extract video ID from YouTube URL.

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
    """
    Format seconds into MM:SS or HH:MM:SS timestamp.

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
    else:
        return f"{minutes:02d}:{secs:02d}"


def get_video_metadata(video_url: str) -> Dict[str, Optional[str]]:
    """
    Extract video metadata using yt-dlp.

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
) -> Tuple[str, Dict]:
    """
    Convert YouTube video to markdown transcript.

    Args:
        video_url: YouTube video URL
        include_timestamps: Include timestamp markers
        language: Language code or 'auto'

    Returns:
        Tuple of (markdown_content, metadata)

    Raises:
        ValueError: Invalid URL
        VideoUnavailable: Video not found
        TranscriptsDisabled: No transcript available
        NoTranscriptFound: Language not available
    """
    # Extract video ID
    video_id = extract_video_id(video_url)
    logger.info(f"Extracting transcript for video {video_id}")

    # Get video metadata
    video_metadata = get_video_metadata(video_url)

    # Fetch transcript
    api = YouTubeTranscriptApi()
    if language == "auto":
        transcript_list = api.list(video_id)
        try:
            transcript = transcript_list.find_generated_transcript(["en"])
        except:
            transcript = transcript_list.find_transcript(
                ["en", "es", "de", "fr", "pt", "ja", "ko", "zh"]
            )
        transcript_data = transcript.fetch()
        detected_language = transcript.language_code
    else:
        transcript_list = api.list(video_id)
        transcript = transcript_list.find_transcript([language])
        transcript_data = transcript.fetch()
        detected_language = language

    # Calculate duration
    total_duration = (
        transcript_data[-1].start + transcript_data[-1].duration
        if transcript_data
        else 0
    )

    # Build transcript text
    lines = []
    for entry in transcript_data:
        text = entry.text.strip()
        if include_timestamps:
            timestamp = format_timestamp(entry.start)
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
        language=detected_language,
        word_count=word_count,
        title=video_metadata.get("title"),
        channel=video_metadata.get("channel"),
        thumbnail=video_metadata.get("thumbnail"),
        description=video_metadata.get("description"),
    )

    # Combine into markdown
    markdown = frontmatter + "# Video Transcript\n\n" + transcript_text

    # Metadata for response
    metadata = {
        "video_id": video_id,
        "title": video_metadata.get("title"),
        "channel": video_metadata.get("channel"),
        "duration": int(total_duration),
        "language": detected_language,
        "word_count": word_count,
    }

    logger.info(f"Successfully converted video {video_id} ({word_count} words)")
    return markdown, metadata
