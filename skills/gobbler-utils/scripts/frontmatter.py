#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""
Generate YAML frontmatter for Gobbler markdown output.

Usage:
    uv run frontmatter.py youtube --url URL --video-id ID [options]
    uv run frontmatter.py webpage --url URL --title TITLE [options]
    uv run frontmatter.py document --path PATH --format FMT [options]
    uv run frontmatter.py audio --path PATH --duration SECS [options]
"""

import argparse
import sys
from datetime import datetime, timezone
from typing import Any


def get_iso8601_timestamp() -> str:
    """Get current timestamp in ISO 8601 format."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def create_frontmatter(metadata: dict[str, Any]) -> str:
    """Create YAML frontmatter from metadata dictionary."""
    lines = ["---"]
    for key, value in metadata.items():
        if value is None:
            continue
        if isinstance(value, str):
            # Escape special characters if needed
            if ":" in value or "#" in value or "\n" in value:
                # Use quoted string for special chars
                escaped = value.replace('"', '\\"')
                value = f'"{escaped}"'
            lines.append(f"{key}: {value}")
        elif isinstance(value, bool):
            lines.append(f"{key}: {'true' if value else 'false'}")
        elif isinstance(value, (int, float)):
            lines.append(f"{key}: {value}")
        else:
            lines.append(f"{key}: {value}")
    lines.append("---")
    lines.append("")
    return "\n".join(lines)


def youtube_frontmatter(args) -> str:
    """Generate YouTube transcript frontmatter."""
    metadata = {
        "source": args.url,
        "type": "youtube_transcript",
        "video_id": args.video_id,
    }
    if args.title:
        metadata["title"] = args.title
    if args.channel:
        metadata["channel"] = args.channel
    if args.thumbnail:
        metadata["thumbnail"] = args.thumbnail
    if args.description:
        metadata["description"] = args.description
    metadata.update({
        "duration": args.duration,
        "language": args.language,
        "word_count": args.word_count,
        "converted_at": get_iso8601_timestamp(),
    })
    return create_frontmatter(metadata)


def webpage_frontmatter(args) -> str:
    """Generate webpage frontmatter."""
    metadata = {
        "source": args.url,
        "type": "webpage",
        "title": args.title,
        "word_count": args.word_count,
        "conversion_time_ms": args.conversion_time,
        "converted_at": get_iso8601_timestamp(),
    }
    return create_frontmatter(metadata)


def document_frontmatter(args) -> str:
    """Generate document frontmatter."""
    metadata = {
        "source": args.path,
        "type": "document",
        "format": args.format,
        "pages": args.pages,
        "word_count": args.word_count,
        "conversion_time_ms": args.conversion_time,
        "converted_at": get_iso8601_timestamp(),
    }
    return create_frontmatter(metadata)


def audio_frontmatter(args) -> str:
    """Generate audio transcript frontmatter."""
    metadata = {
        "source": args.path,
        "type": "audio_transcript",
        "duration": args.duration,
        "language": args.language,
        "model": args.model,
        "word_count": args.word_count,
        "conversion_time_ms": args.conversion_time,
        "converted_at": get_iso8601_timestamp(),
    }
    return create_frontmatter(metadata)


def main():
    parser = argparse.ArgumentParser(description="Generate YAML frontmatter")
    subparsers = parser.add_subparsers(dest="type", required=True)

    # YouTube subcommand
    yt = subparsers.add_parser("youtube", help="YouTube transcript frontmatter")
    yt.add_argument("--url", required=True, help="YouTube video URL")
    yt.add_argument("--video-id", required=True, help="Video ID")
    yt.add_argument("--title", help="Video title")
    yt.add_argument("--channel", help="Channel name")
    yt.add_argument("--thumbnail", help="Thumbnail URL")
    yt.add_argument("--description", help="Video description")
    yt.add_argument("--duration", type=int, default=0, help="Duration in seconds")
    yt.add_argument("--language", default="en", help="Transcript language")
    yt.add_argument("--word-count", type=int, default=0, help="Word count")

    # Webpage subcommand
    wp = subparsers.add_parser("webpage", help="Webpage frontmatter")
    wp.add_argument("--url", required=True, help="Page URL")
    wp.add_argument("--title", required=True, help="Page title")
    wp.add_argument("--word-count", type=int, default=0, help="Word count")
    wp.add_argument("--conversion-time", type=int, default=0, help="Conversion time in ms")

    # Document subcommand
    doc = subparsers.add_parser("document", help="Document frontmatter")
    doc.add_argument("--path", required=True, help="File path")
    doc.add_argument("--format", required=True, help="Document format (pdf, docx, etc.)")
    doc.add_argument("--pages", type=int, default=0, help="Number of pages")
    doc.add_argument("--word-count", type=int, default=0, help="Word count")
    doc.add_argument("--conversion-time", type=int, default=0, help="Conversion time in ms")

    # Audio subcommand
    aud = subparsers.add_parser("audio", help="Audio transcript frontmatter")
    aud.add_argument("--path", required=True, help="File path")
    aud.add_argument("--duration", type=int, required=True, help="Duration in seconds")
    aud.add_argument("--language", default="en", help="Detected language")
    aud.add_argument("--model", default="small", help="Whisper model used")
    aud.add_argument("--word-count", type=int, default=0, help="Word count")
    aud.add_argument("--conversion-time", type=int, default=0, help="Conversion time in ms")

    args = parser.parse_args()

    if args.type == "youtube":
        print(youtube_frontmatter(args))
    elif args.type == "webpage":
        print(webpage_frontmatter(args))
    elif args.type == "document":
        print(document_frontmatter(args))
    elif args.type == "audio":
        print(audio_frontmatter(args))


if __name__ == "__main__":
    main()
