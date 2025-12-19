#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["faster-whisper>=1.0.0"]
# ///
"""
Transcribe audio/video to markdown using faster-whisper.

Usage:
    uv run transcribe.py <file_path> [--model SIZE] [--language LANG] [--output FILE]

Examples:
    uv run transcribe.py audio.mp3
    uv run transcribe.py video.mp4 --model medium
    uv run transcribe.py recording.wav --language en --output transcript.md
"""

import argparse
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from faster_whisper import WhisperModel

SUPPORTED_EXTENSIONS = (".mp3", ".wav", ".flac", ".m4a", ".ogg", ".mp4", ".mov", ".avi", ".mkv", ".webm")
VALID_MODELS = ("tiny", "base", "small", "medium", "large")


def create_frontmatter(
    file_path: str,
    duration: int,
    language: str,
    model: str,
    word_count: int,
    conversion_time_ms: int
) -> str:
    """Create YAML frontmatter for audio transcript."""
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    return f"""---
source: "{file_path}"
type: audio
duration_seconds: {duration}
language: {language}
model: {model}
word_count: {word_count}
conversion_time_ms: {conversion_time_ms}
converted_at: {timestamp}
---

"""


def transcribe_audio(
    file_path: str,
    model_size: str = "small",
    language: str = "auto",
) -> str:
    """Transcribe audio/video file to markdown."""
    path = Path(file_path)

    if not path.exists():
        raise FileNotFoundError(f"File not found: {file_path}")

    ext = path.suffix.lower()
    if ext not in SUPPORTED_EXTENSIONS:
        raise ValueError(f"Unsupported format: {ext}. Supported: {SUPPORTED_EXTENSIONS}")

    if model_size not in VALID_MODELS:
        raise ValueError(f"Invalid model: {model_size}. Supported: {VALID_MODELS}")

    start_time = time.time()

    # Load model (uses CoreML on M-series Macs)
    print(f"Loading Whisper model: {model_size}...", file=sys.stderr)
    model = WhisperModel(
        model_size,
        device="cpu",  # faster-whisper uses CPU/CoreML
        compute_type="auto",  # Automatically uses CoreML on M-series
    )

    # Transcribe
    print("Transcribing...", file=sys.stderr)
    lang = None if language == "auto" else language

    segments, info = model.transcribe(
        str(path),
        language=lang,
        beam_size=5,
        vad_filter=True,  # Voice activity detection
    )

    # Build transcript
    transcript_lines = []
    duration = 0

    for segment in segments:
        transcript_lines.append(segment.text.strip())
        duration = max(duration, segment.end)

    transcript_text = " ".join(transcript_lines).strip()
    detected_language = info.language

    if not transcript_text:
        raise RuntimeError("No speech detected in audio")

    conversion_time_ms = int((time.time() - start_time) * 1000)
    word_count = len(transcript_text.split())
    duration = int(duration)

    # Create frontmatter
    frontmatter = create_frontmatter(
        file_path=str(path.absolute()),
        duration=duration,
        language=detected_language,
        model=model_size,
        word_count=word_count,
        conversion_time_ms=conversion_time_ms,
    )

    return frontmatter + "# Audio Transcript\n\n" + transcript_text


def main():
    parser = argparse.ArgumentParser(description="Transcribe audio/video to markdown")
    parser.add_argument("file", help="Audio/video file path")
    parser.add_argument("--model", "-m", default="small", choices=VALID_MODELS, help="Model size")
    parser.add_argument("--language", "-l", default="auto", help="Language code or 'auto'")
    parser.add_argument("--output", "-o", help="Output file path")
    args = parser.parse_args()

    try:
        markdown = transcribe_audio(
            args.file,
            model_size=args.model,
            language=args.language,
        )

        if args.output:
            Path(args.output).write_text(markdown)
            print(f"Saved to {args.output}", file=sys.stderr)
        else:
            print(markdown)

    except FileNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
