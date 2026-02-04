"""Shared knowledge base for error diagnosis and suggestions.

This module consolidates error patterns, solutions, and suggestions
used by both the `explain` command and JSON error responses.
"""

from __future__ import annotations

from dataclasses import dataclass, field


# Time estimation constants (seconds per item)
SECONDS_PER_YOUTUBE_VIDEO = 7  # Average including transcript fetch
SECONDS_PER_AUDIO_FILE = 5  # Whisper transcription (small model)
SECONDS_PER_DOCUMENT = 3  # Docling PDF conversion
SECONDS_PER_WEBPAGE = 8  # Crawl4AI with JS rendering


@dataclass
class ErrorSolution:
    """A documented error pattern with solution.

    Attributes:
        keywords: Words/phrases to match against error messages
        title: Human-readable error name
        description: Explanation of what's happening
        fix: Command or action to fix the issue
        verify: Optional command to verify the fix worked
        docs: Optional link to documentation
        error_codes: Error codes this solution applies to (for JSON output)
    """

    keywords: list[str]
    title: str
    description: str
    fix: str
    verify: str | None = None
    docs: str | None = None
    error_codes: list[str] = field(default_factory=list)


# Consolidated knowledge base of common errors and solutions
ERROR_KNOWLEDGE_BASE: list[ErrorSolution] = [
    # ===================
    # Docling / Document conversion errors
    # ===================
    ErrorSolution(
        keywords=["connection refused", "5001", "docling", "document"],
        title="Docling service not running",
        description="The Docling Docker container is not running or not accessible on port 5001.",
        fix="cd ~/Projects/gobbler && docker compose up -d docling",
        verify="curl -s http://localhost:5001/health && echo ' OK'",
        docs="https://github.com/Enablement-Engineering/gobbler#document-conversion",
        error_codes=["DOCUMENT_CONVERSION_ERROR"],
    ),
    ErrorSolution(
        keywords=["server disconnected", "memory", "oom", "killed"],
        title="Service crashed (likely out of memory)",
        description="The Docker service crashed, usually due to insufficient memory during OCR.",
        fix="Try with --no-ocr flag, or increase Docker memory in docker-compose.yml",
        verify="docker ps --filter 'name=gobbler' --format '{{.Names}}: {{.Status}}'",
        error_codes=["DOCUMENT_CONVERSION_ERROR"],
    ),
    ErrorSolution(
        keywords=["ocr", "failed", "scanned"],
        title="OCR processing failed",
        description="OCR failed on a scanned document. This may be due to memory limits or corrupt files.",
        fix="gobbler document FILE --no-ocr (if digital PDF) or increase Docker memory",
        verify="docker logs gobbler-docling --tail 20",
        error_codes=["DOCUMENT_CONVERSION_ERROR"],
    ),
    ErrorSolution(
        keywords=["timeout", "document", "docling"],
        title="Document conversion timed out",
        description="The document took too long to process, possibly due to size or complexity.",
        fix="Try --no-ocr for faster processing, or process a smaller document",
        error_codes=["DOCUMENT_CONVERSION_ERROR"],
    ),
    # ===================
    # Crawl4AI / Webpage errors
    # ===================
    ErrorSolution(
        keywords=["connection refused", "11235", "crawl4ai", "webpage"],
        title="Crawl4AI service not running",
        description="The Crawl4AI Docker container is not running or not accessible on port 11235.",
        fix="cd ~/Projects/gobbler && docker compose up -d crawl4ai",
        verify="curl -s http://localhost:11235/health && echo ' OK'",
        docs="https://github.com/Enablement-Engineering/gobbler#web-page-conversion",
        error_codes=["WEBPAGE_CONVERSION_ERROR"],
    ),
    ErrorSolution(
        keywords=["timeout", "webpage", "crawl"],
        title="Web page request timed out",
        description="The page took too long to load. May be slow server or complex JavaScript.",
        fix="Increase timeout: gobbler webpage URL --timeout 60",
        verify="curl -I URL (check if site is accessible)",
        error_codes=["WEBPAGE_CONVERSION_ERROR"],
    ),
    ErrorSolution(
        keywords=["blocked", "forbidden", "403", "captcha"],
        title="Website blocking automated access",
        description="The website detected and blocked the automated request.",
        fix="Try using a proxy service in ~/.config/gobbler/config.yml or use the browser extension",
        docs="https://github.com/Enablement-Engineering/gobbler#browser-extension",
        error_codes=["WEBPAGE_CONVERSION_ERROR"],
    ),
    # ===================
    # YouTube errors
    # ===================
    ErrorSolution(
        keywords=["ip blocked", "youtube", "rate limit", "too many"],
        title="YouTube rate limiting / IP blocked",
        description="YouTube is blocking requests from your IP due to too many requests.",
        fix="Configure a Webshare proxy in ~/.config/gobbler/config.yml or wait 10-15 minutes",
        verify="gobbler status --json | grep -A5 proxy",
        error_codes=["YOUTUBE_CONVERSION_ERROR"],
    ),
    ErrorSolution(
        keywords=["no transcript", "captions", "subtitles", "disabled"],
        title="Video has no transcripts available",
        description="This YouTube video doesn't have captions/subtitles available.",
        fix="Check if the video has captions on YouTube. Try --language auto",
        verify="Open video on YouTube and check if CC button is available",
        error_codes=["YOUTUBE_CONVERSION_ERROR"],
    ),
    ErrorSolution(
        keywords=["video unavailable", "private", "removed"],
        title="Video not accessible",
        description="The video is private, removed, or region-blocked.",
        fix="Check if the video is accessible in your browser",
        error_codes=["YOUTUBE_CONVERSION_ERROR"],
    ),
    # ===================
    # Audio / Whisper errors
    # ===================
    ErrorSolution(
        keywords=["ffmpeg", "not found", "command not found"],
        title="ffmpeg not installed",
        description="ffmpeg is required for audio/video processing but is not installed.",
        fix="brew install ffmpeg (macOS) or apt install ffmpeg (Linux)",
        verify="ffmpeg -version",
        error_codes=["AUDIO_CONVERSION_ERROR"],
    ),
    ErrorSolution(
        keywords=["whisper", "model", "download", "huggingface"],
        title="Whisper model download issue",
        description="Failed to download or load the Whisper model from HuggingFace.",
        fix="Check internet connection. Try: export HF_TOKEN=your_token",
        verify="ls ~/.cache/huggingface/hub/ | grep whisper",
        error_codes=["AUDIO_CONVERSION_ERROR"],
    ),
    ErrorSolution(
        keywords=["no speech", "silent", "empty"],
        title="No speech detected in audio",
        description="Whisper couldn't detect any speech in the audio file.",
        fix="Check if the audio file actually contains speech. Try playing it locally.",
        verify="ffprobe FILE (check audio stream info)",
        error_codes=["AUDIO_CONVERSION_ERROR"],
    ),
    ErrorSolution(
        keywords=["memory", "model", "large", "medium"],
        title="Insufficient memory for model",
        description="The Whisper model is too large for available memory.",
        fix="Use a smaller model with --model tiny or --model base",
        error_codes=["AUDIO_CONVERSION_ERROR"],
    ),
    # ===================
    # Docker errors
    # ===================
    ErrorSolution(
        keywords=["docker", "daemon", "not running", "cannot connect"],
        title="Docker not running",
        description="Docker Desktop is not running or not accessible.",
        fix="Start Docker Desktop: open -a Docker (macOS) or systemctl start docker (Linux)",
        verify="docker info",
    ),
    ErrorSolution(
        keywords=["docker", "permission", "denied", "socket"],
        title="Docker permission denied",
        description="Your user doesn't have permission to access Docker.",
        fix="sudo usermod -aG docker $USER && newgrp docker",
        verify="docker ps",
    ),
    # ===================
    # General errors
    # ===================
    ErrorSolution(
        keywords=["file not found", "no such file"],
        title="File not found",
        description="The specified file path doesn't exist.",
        fix="Check the file path and ensure it exists: ls -la FILE",
        verify="ls -la FILE",
    ),
    ErrorSolution(
        keywords=["permission denied", "access denied"],
        title="Permission denied",
        description="You don't have permission to access this file or resource.",
        fix="Check file permissions: ls -la FILE or run with appropriate permissions",
    ),
    ErrorSolution(
        keywords=["unsupported format", "invalid format"],
        title="Unsupported file format",
        description="The file format is not supported by Gobbler.",
        fix="Check supported formats: PDF, DOCX, PPTX, XLSX for documents; MP3, WAV, M4A, MP4 for audio",
        docs="https://github.com/Enablement-Engineering/gobbler#features",
    ),
]


def find_solutions(error_text: str, error_code: str | None = None) -> list[ErrorSolution]:
    """Find matching solutions for an error message.

    Args:
        error_text: The error message or description to diagnose
        error_code: Optional error code to prioritize matches

    Returns:
        List of matching ErrorSolution objects, sorted by relevance
    """
    error_lower = error_text.lower()
    matches: list[tuple[int, ErrorSolution]] = []

    for solution in ERROR_KNOWLEDGE_BASE:
        # Count keyword matches
        match_count = sum(1 for kw in solution.keywords if kw in error_lower)

        # Bonus for matching error code
        if error_code and error_code in solution.error_codes:
            match_count += 2

        if match_count > 0:
            matches.append((match_count, solution))

    # Sort by match count (descending)
    matches.sort(key=lambda x: x[0], reverse=True)

    return [sol for _, sol in matches]


def get_suggestion_for_error(error_code: str, error_message: str) -> str | None:
    """Get a suggestion for a specific error (used by JSON error responses).

    Args:
        error_code: The error code (e.g., DOCUMENT_CONVERSION_ERROR)
        error_message: The error message text

    Returns:
        A suggestion string, or None if no match found
    """
    solutions = find_solutions(error_message, error_code)
    if solutions:
        return solutions[0].fix
    return None
