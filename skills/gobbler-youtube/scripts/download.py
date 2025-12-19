#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["yt-dlp>=2024.0.0"]
# ///
"""
Download YouTube video or audio.

Usage:
    uv run download.py <video_url> --output-dir DIR [--quality QUALITY] [--audio-only]

Examples:
    uv run download.py "https://youtube.com/watch?v=dQw4w9WgXcQ" --output-dir ./downloads
    uv run download.py "https://youtu.be/dQw4w9WgXcQ" --quality 720p --output-dir ./downloads
    uv run download.py "https://youtube.com/watch?v=dQw4w9WgXcQ" --audio-only --output-dir ./downloads
"""

import argparse
import re
import sys
from pathlib import Path

import yt_dlp


QUALITY_FORMATS = {
    "best": "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best",
    "1080p": "bestvideo[height<=1080][ext=mp4]+bestaudio[ext=m4a]/best[height<=1080][ext=mp4]/best[height<=1080]",
    "720p": "bestvideo[height<=720][ext=mp4]+bestaudio[ext=m4a]/best[height<=720][ext=mp4]/best[height<=720]",
    "480p": "bestvideo[height<=480][ext=mp4]+bestaudio[ext=m4a]/best[height<=480][ext=mp4]/best[height<=480]",
    "360p": "bestvideo[height<=360][ext=mp4]+bestaudio[ext=m4a]/best[height<=360][ext=mp4]/best[height<=360]",
}


def sanitize_filename(title: str) -> str:
    """Sanitize filename for filesystem."""
    # Remove or replace problematic characters
    sanitized = re.sub(r'[<>:"/\\|?*]', '', title)
    sanitized = re.sub(r'\s+', ' ', sanitized).strip()
    return sanitized[:200]  # Limit length


def download_video(
    video_url: str,
    output_dir: str,
    quality: str = "best",
    audio_only: bool = False,
) -> str:
    """Download YouTube video or audio."""
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    # Get video info first to get title
    with yt_dlp.YoutubeDL({"quiet": True}) as ydl:
        info = ydl.extract_info(video_url, download=False)
        title = sanitize_filename(info.get("title", "video"))

    if audio_only:
        ydl_opts = {
            "format": "bestaudio[ext=m4a]/bestaudio",
            "outtmpl": str(output_path / f"{title}.%(ext)s"),
            "postprocessors": [{
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": "192",
            }],
            "quiet": False,
            "no_warnings": True,
        }
        extension = "mp3"
    else:
        format_string = QUALITY_FORMATS.get(quality, QUALITY_FORMATS["best"])
        ydl_opts = {
            "format": format_string,
            "outtmpl": str(output_path / f"{title}.%(ext)s"),
            "merge_output_format": "mp4",
            "quiet": False,
            "no_warnings": True,
        }
        extension = "mp4"

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        ydl.download([video_url])

    output_file = output_path / f"{title}.{extension}"
    return str(output_file)


def main():
    parser = argparse.ArgumentParser(description="Download YouTube video or audio")
    parser.add_argument("url", help="YouTube video URL")
    parser.add_argument(
        "--output-dir", "-o",
        required=True,
        help="Output directory"
    )
    parser.add_argument(
        "--quality", "-q",
        choices=["best", "1080p", "720p", "480p", "360p"],
        default="best",
        help="Video quality (default: best)"
    )
    parser.add_argument(
        "--audio-only", "-a",
        action="store_true",
        help="Download audio only (MP3)"
    )
    args = parser.parse_args()

    try:
        output_file = download_video(
            args.url,
            args.output_dir,
            quality=args.quality,
            audio_only=args.audio_only,
        )
        print(f"Downloaded: {output_file}")

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
