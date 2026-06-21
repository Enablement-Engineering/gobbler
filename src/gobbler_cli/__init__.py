"""Gobbler CLI - Command-line interface for Gobbler content conversion.

This package provides a user-friendly CLI for converting content (YouTube videos,
audio files, documents, and web pages) to markdown with YAML frontmatter.

Usage:
    $ gobbler youtube https://youtube.com/watch?v=ABC123
    $ gobbler audio recording.mp3 -o transcript.md
    $ gobbler batch youtube-playlist https://... --output ./transcripts/
    $ gobbler daemon start
    $ gobbler jobs list

The CLI supports both direct mode (using converters directly) and API mode
(communicating with the gobbler daemon).
"""

__version__ = "0.2.3"

__all__ = ["__version__"]
