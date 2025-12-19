#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""
Extract audio from video files using ffmpeg.

Usage:
    uv run extract_audio.py <video_path> [--output FILE]

Examples:
    uv run extract_audio.py video.mp4
    uv run extract_audio.py movie.mov --output audio.mp3
"""

import argparse
import subprocess
import sys
from pathlib import Path

VIDEO_EXTENSIONS = (".mp4", ".mov", ".avi", ".mkv", ".webm", ".flv", ".wmv")


def extract_audio(video_path: str, output_path: str = None) -> str:
    """
    Extract audio from video file.

    Uses ffmpeg to extract audio track and convert to mono 16kHz MP3,
    optimized for speech transcription.

    Args:
        video_path: Path to source video file
        output_path: Optional output path (default: same name with .mp3)

    Returns:
        Path to extracted audio file
    """
    path = Path(video_path)

    if not path.exists():
        raise FileNotFoundError(f"File not found: {video_path}")

    ext = path.suffix.lower()
    if ext not in VIDEO_EXTENSIONS:
        raise ValueError(f"Unsupported format: {ext}. Supported: {VIDEO_EXTENSIONS}")

    # Default output path
    if output_path is None:
        output_path = str(path.with_suffix(".mp3"))

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
                "-i", str(path),
                "-vn",
                "-acodec", "libmp3lame",
                "-ar", "16000",
                "-ac", "1",
                "-y",
                output_path
            ],
            capture_output=True,
            text=True,
            timeout=3600  # 60 minute timeout
        )

        if result.returncode != 0:
            raise RuntimeError(f"ffmpeg failed: {result.stderr}")

        return output_path

    except subprocess.TimeoutExpired:
        raise RuntimeError("Audio extraction timed out after 60 minutes")
    except FileNotFoundError:
        raise RuntimeError("ffmpeg not found. Please install ffmpeg.")


def main():
    parser = argparse.ArgumentParser(description="Extract audio from video")
    parser.add_argument("file", help="Video file path")
    parser.add_argument("--output", "-o", help="Output audio file path")
    args = parser.parse_args()

    try:
        output = extract_audio(args.file, args.output)
        print(f"Audio extracted to: {output}", file=sys.stderr)

    except FileNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
