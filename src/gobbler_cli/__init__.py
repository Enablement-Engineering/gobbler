"""Gobbler CLI - command-line content conversion and browser automation.

The CLI converts YouTube transcripts, audio/video files, documents, and webpages
to markdown or JSON, manages optional SQLite-backed jobs, and controls the local
browser-extension relay.

Usage:
    $ gobbler youtube https://youtube.com/watch?v=ABC123
    $ gobbler audio recording.mp3 -o transcript.md
    $ gobbler batch youtube-playlist https://... --output-dir ./transcripts/
    $ gobbler jobs worker start
    $ gobbler relay start
"""

__version__ = "0.2.30"

__all__ = ["__version__"]
