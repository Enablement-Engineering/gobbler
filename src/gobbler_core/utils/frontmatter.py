"""Utilities for generating YAML frontmatter in markdown files."""

from datetime import UTC, datetime
from typing import Any


def _escape_yaml_string(value: str) -> str:
    """Escape a string for safe YAML output.

    Uses double-quoted scalar style for strings containing special characters.
    This handles newlines, quotes, colons, and other YAML special characters.

    Args:
        value: String value to escape

    Returns:
        Properly escaped YAML string
    """
    # Characters that appear anywhere requiring quoting
    special_chars = ("\n", "\r", "\t", '"', ":", "#")

    # Characters at the start that require quoting (YAML special syntax)
    special_start_chars = (" ", "'", '"', "-", "[", "{", "@", "`", "!", "&", "*", "|", ">", "%")

    # Check if quoting is needed
    needs_quoting = (
        any(char in value for char in special_chars)
        or value.startswith(special_start_chars)
        or value.endswith(" ")
    )

    if not needs_quoting:
        return value

    # Escape special characters for double-quoted style
    escaped = value.replace("\\", "\\\\")  # Backslash first
    escaped = escaped.replace('"', '\\"')  # Double quotes
    escaped = escaped.replace("\n", "\\n")  # Newlines
    escaped = escaped.replace("\r", "\\r")  # Carriage returns
    escaped = escaped.replace("\t", "\\t")  # Tabs

    return f'"{escaped}"'


def create_frontmatter(metadata: dict[str, Any]) -> str:
    """Create YAML frontmatter from metadata dictionary.

    Args:
        metadata: Dictionary of metadata fields

    Returns:
        YAML frontmatter string with separators
    """
    lines = ["---"]
    for key, value in metadata.items():
        # Format value based on type
        if isinstance(value, str):
            formatted_value = _escape_yaml_string(value)
            lines.append(f"{key}: {formatted_value}")
        elif isinstance(value, (int, float, bool)):
            lines.append(f"{key}: {value}")
        elif value is None:
            lines.append(f"{key}: null")
        else:
            # Convert to string for other types
            lines.append(f"{key}: {value}")

    lines.append("---")
    lines.append("")  # Empty line after frontmatter
    return "\n".join(lines)


def get_iso8601_timestamp() -> str:
    """Get current timestamp in ISO 8601 format.

    Returns:
        ISO 8601 timestamp string (e.g., "2025-10-02T14:32:11Z")
    """
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def count_words(text: str) -> int:
    """Count words in text.

    Args:
        text: Text to count words in

    Returns:
        Word count
    """
    return len(text.split())


def create_youtube_frontmatter(
    video_url: str,
    video_id: str,
    duration: int,
    language: str,
    word_count: int,
    title: str | None = None,
    channel: str | None = None,
    thumbnail: str | None = None,
    description: str | None = None,
) -> str:
    """Create frontmatter for YouTube transcript.

    Args:
        video_url: Original YouTube URL
        video_id: YouTube video ID
        duration: Video duration in seconds
        language: Transcript language code
        word_count: Number of words in transcript
        title: Video title (optional)
        channel: Channel name (optional)
        thumbnail: Thumbnail URL (optional)
        description: Video description (optional)

    Returns:
        YAML frontmatter string
    """
    metadata = {
        "source": video_url,
        "type": "youtube_transcript",
        "video_id": video_id,
    }

    # Add optional metadata if available
    if title:
        metadata["title"] = title
    if channel:
        metadata["channel"] = channel
    if thumbnail:
        metadata["thumbnail"] = thumbnail
    if description:
        metadata["description"] = description

    metadata.update(
        {
            "duration": duration,
            "language": language,
            "word_count": word_count,
            "converted_at": get_iso8601_timestamp(),
        }
    )

    return create_frontmatter(metadata)


def create_webpage_frontmatter(
    url: str,
    title: str,
    word_count: int,
    conversion_time_ms: int,
) -> str:
    """Create frontmatter for web page conversion.

    Args:
        url: Original URL
        title: Page title
        word_count: Number of words in content
        conversion_time_ms: Conversion time in milliseconds

    Returns:
        YAML frontmatter string
    """
    metadata = {
        "source": url,
        "type": "webpage",
        "title": title,
        "word_count": word_count,
        "conversion_time_ms": conversion_time_ms,
        "converted_at": get_iso8601_timestamp(),
    }
    return create_frontmatter(metadata)


def create_document_frontmatter(
    file_path: str,
    doc_format: str,
    pages: int,
    word_count: int,
    conversion_time_ms: int,
) -> str:
    """Create frontmatter for document conversion.

    Args:
        file_path: Original file path
        doc_format: Document format (pdf, docx, etc.)
        pages: Number of pages
        word_count: Number of words in content
        conversion_time_ms: Conversion time in milliseconds

    Returns:
        YAML frontmatter string
    """
    metadata = {
        "source": file_path,
        "type": "document",
        "format": doc_format,
        "pages": pages,
        "word_count": word_count,
        "conversion_time_ms": conversion_time_ms,
        "converted_at": get_iso8601_timestamp(),
    }
    return create_frontmatter(metadata)


def create_audio_frontmatter(
    file_path: str,
    duration: int,
    language: str,
    model: str,
    word_count: int,
    conversion_time_ms: int,
) -> str:
    """Create frontmatter for audio transcription.

    Args:
        file_path: Original file path
        duration: Audio duration in seconds
        language: Detected language code
        model: Whisper model used
        word_count: Number of words in transcript
        conversion_time_ms: Conversion time in milliseconds

    Returns:
        YAML frontmatter string
    """
    metadata = {
        "source": file_path,
        "type": "audio_transcript",
        "duration": duration,
        "language": language,
        "model": model,
        "word_count": word_count,
        "conversion_time_ms": conversion_time_ms,
        "converted_at": get_iso8601_timestamp(),
    }
    return create_frontmatter(metadata)
