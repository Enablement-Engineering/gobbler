#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["yt-dlp>=2024.0.0"]
# ///
"""
Get YouTube video metadata without downloading.

Usage:
    uv run get_metadata.py <video_url>

Examples:
    uv run get_metadata.py "https://youtube.com/watch?v=dQw4w9WgXcQ"
    uv run get_metadata.py "https://youtu.be/dQw4w9WgXcQ"
"""

import argparse
import json
import sys

import yt_dlp


def get_metadata(video_url: str) -> dict:
    """Get video metadata from YouTube."""
    ydl_opts = {
        "quiet": True,
        "no_warnings": True,
    }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(video_url, download=False)

        return {
            "id": info.get("id"),
            "title": info.get("title"),
            "channel": info.get("channel") or info.get("uploader"),
            "channel_id": info.get("channel_id"),
            "duration": info.get("duration"),
            "duration_string": info.get("duration_string"),
            "view_count": info.get("view_count"),
            "like_count": info.get("like_count"),
            "upload_date": info.get("upload_date"),
            "description": info.get("description"),
            "thumbnail": info.get("thumbnail"),
            "categories": info.get("categories"),
            "tags": info.get("tags"),
            "availability": info.get("availability"),
        }


def main():
    parser = argparse.ArgumentParser(description="Get YouTube video metadata")
    parser.add_argument("url", help="YouTube video URL")
    parser.add_argument(
        "--pretty", "-p",
        action="store_true",
        help="Pretty print JSON output"
    )
    args = parser.parse_args()

    try:
        metadata = get_metadata(args.url)

        if args.pretty:
            print(json.dumps(metadata, indent=2, ensure_ascii=False))
        else:
            print(json.dumps(metadata, ensure_ascii=False))

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
