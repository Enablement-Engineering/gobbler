#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "gobbler-mcp",
#   "yt-dlp>=2024.0.0",
# ]
# [tool.uv.sources]
# gobbler-mcp = { path = "../../../", editable = true }
# ///
"""
Transcribe YouTube video to markdown.

Usage:
    uv run transcribe.py <video_url> [--timestamps] [--language LANG] [--output FILE]

Provider options (multiple backends available):
    # Default: youtube-transcript-api (free, may get IP blocked)
    uv run transcribe.py <url>

    # TranscriptAPI.com (paid API, 1 credit per transcript, no IP blocks)
    uv run transcribe.py <url> --provider transcriptapi --api-key YOUR_KEY

    # Auto-fallback: try free first, fall back to paid API if blocked
    uv run transcribe.py <url> --provider auto --api-key YOUR_KEY

Proxy support (for youtube-transcript-api provider):
    uv run transcribe.py <url> --webshare-user USER --webshare-pass PASS
    uv run transcribe.py <url> --proxy "http://user:pass@host:port"

Examples:
    uv run transcribe.py "https://youtube.com/watch?v=dQw4w9WgXcQ"
    uv run transcribe.py "https://youtu.be/dQw4w9WgXcQ" --timestamps
    uv run transcribe.py "https://youtube.com/watch?v=VIDEO_ID" --provider transcriptapi
"""

import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path

# Import provider classes from gobbler_core (shared standalone package)
from gobbler_core.providers.youtube import (
    TranscriptProvider,
    YouTubeTranscriptAPIProvider,
    TranscriptAPIProvider,
    AutoFallbackProvider,
    create_proxy_config,
    create_provider,
)


# Always need these imports for metadata and formatting
import re
import yt_dlp


def extract_video_id(video_url: str) -> str:
    """Extract video ID from YouTube URL."""
    if re.match(r"^[a-zA-Z0-9_-]{11}$", video_url):
        return video_url

    pattern = r"^https?://(www\.)?(youtube\.com/watch\?v=|youtu\.be/)([a-zA-Z0-9_-]{11})"
    match = re.match(pattern, video_url)
    if not match:
        raise ValueError(
            "Invalid YouTube URL format. Expected: https://youtube.com/watch?v=VIDEO_ID "
            "or https://youtu.be/VIDEO_ID"
        )
    return match.group(3)


def format_timestamp(seconds: float) -> str:
    """Format seconds into MM:SS or HH:MM:SS timestamp."""
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    if hours > 0:
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"
    return f"{minutes:02d}:{secs:02d}"


def get_video_metadata(video_url: str) -> dict:
    """Extract video metadata using yt-dlp."""
    ydl_opts = {"quiet": True, "no_warnings": True, "extract_flat": True}
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
        print(f"Warning: Failed to extract video metadata: {e}", file=sys.stderr)
        return {"title": None, "channel": None, "thumbnail": None, "description": None}


def create_frontmatter(metadata: dict) -> str:
    """Create YAML frontmatter from metadata."""
    lines = ["---"]
    for key, value in metadata.items():
        if value is None:
            continue
        if isinstance(value, str):
            if ":" in value or "#" in value or "\n" in value:
                escaped = value.replace('"', '\\"').replace("\n", " ")
                value = f'"{escaped}"'
            lines.append(f"{key}: {value}")
        else:
            lines.append(f"{key}: {value}")
    lines.append("---")
    lines.append("")
    return "\n".join(lines)


def transcribe_youtube(
    video_url: str,
    include_timestamps: bool = False,
    language: str = "auto",
    provider: TranscriptProvider = None,
) -> str:
    """Convert YouTube video to markdown transcript."""
    video_id = extract_video_id(video_url)
    video_metadata = get_video_metadata(video_url)

    if provider is None:
        provider = YouTubeTranscriptAPIProvider()

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
    word_count = len(transcript_text.split())

    # Create frontmatter
    metadata = {
        "source": video_url,
        "type": "youtube_transcript",
        "video_id": video_id,
    }
    if video_metadata.get("title"):
        metadata["title"] = video_metadata["title"]
    if video_metadata.get("channel"):
        metadata["channel"] = video_metadata["channel"]
    if video_metadata.get("thumbnail"):
        metadata["thumbnail"] = video_metadata["thumbnail"]

    metadata.update(
        {
            "duration": int(total_duration),
            "language": result.language,
            "word_count": word_count,
            "converted_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        }
    )

    frontmatter = create_frontmatter(metadata)
    return frontmatter + "# Video Transcript\n\n" + transcript_text


def main():
    parser = argparse.ArgumentParser(
        description="Transcribe YouTube video to markdown",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Providers:
  youtube-transcript-api  Free, but may get IP blocked by YouTube
  transcriptapi           Paid API (~$0.01/transcript), no IP blocks
  auto                    Try free first, fall back to paid if blocked

Environment variables:
  TRANSCRIPTAPI_KEY       API key for TranscriptAPI.com
  WEBSHARE_USER/PASS      Webshare proxy credentials
  YOUTUBE_PROXY           Generic proxy URL

Get TranscriptAPI key at: https://transcriptapi.com/dashboard/api-keys
Get Webshare proxies at: https://www.webshare.io/
        """,
    )
    parser.add_argument("url", help="YouTube video URL")
    parser.add_argument("--timestamps", "-t", action="store_true", help="Include timestamps")
    parser.add_argument("--language", "-l", default="auto", help="Language code (default: auto)")
    parser.add_argument("--output", "-o", help="Output file path")

    provider_group = parser.add_argument_group("provider options")
    provider_group.add_argument(
        "--provider",
        "-p",
        choices=["youtube-transcript-api", "transcriptapi", "auto"],
        default="youtube-transcript-api",
        help="Transcript provider (default: youtube-transcript-api)",
    )
    provider_group.add_argument("--api-key", help="API key for TranscriptAPI.com")

    proxy_group = parser.add_argument_group("proxy options")
    proxy_group.add_argument("--webshare-user", help="Webshare proxy username")
    proxy_group.add_argument("--webshare-pass", help="Webshare proxy password")
    proxy_group.add_argument("--proxy", help="Generic proxy URL")

    args = parser.parse_args()

    try:
        proxy_config = create_proxy_config(
            webshare_user=args.webshare_user,
            webshare_pass=args.webshare_pass,
            proxy_url=args.proxy,
        )

        provider = create_provider(
            provider_name=args.provider,
            api_key=args.api_key,
            proxy_config=proxy_config,
        )

        markdown = transcribe_youtube(
            args.url,
            include_timestamps=args.timestamps,
            language=args.language,
            provider=provider,
        )

        if args.output:
            Path(args.output).write_text(markdown)
            print(f"Saved to {args.output}", file=sys.stderr)
        else:
            print(markdown)

    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        error_msg = str(e)
        if "IpBlocked" in error_msg or "blocked" in error_msg.lower():
            print(f"Error: {e}", file=sys.stderr)
            print("\nYour IP is blocked by YouTube. Options:", file=sys.stderr)
            print(
                "  1. Use TranscriptAPI.com: --provider transcriptapi --api-key KEY",
                file=sys.stderr,
            )
            print("  2. Use auto-fallback:     --provider auto --api-key KEY", file=sys.stderr)
            print(
                "  3. Use a proxy:           --webshare-user USER --webshare-pass PASS",
                file=sys.stderr,
            )
        else:
            print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
