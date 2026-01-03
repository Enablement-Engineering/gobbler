"""Batch processing tools - thin CLI wrappers.

These tools delegate to the gobbler CLI for actual implementation,
keeping the MCP server lightweight and avoiding code duplication.

Tools:
- batch_transcribe_youtube_playlist: Extract transcripts from YouTube playlists via CLI
- batch_fetch_webpages: Convert multiple web pages to markdown via CLI
- batch_transcribe_audio: Transcribe all audio/video files in a directory via CLI
- batch_convert_documents: Convert all documents in a directory to markdown via CLI
"""

import json
import logging
import subprocess
import tempfile
from pathlib import Path

from fastmcp import FastMCP

from ..constants import (
    MAX_BATCH_CONCURRENCY_AUDIO,
    MAX_BATCH_CONCURRENCY_DOCUMENT,
    MAX_BATCH_CONCURRENCY_WEBPAGE,
    MAX_BATCH_CONCURRENCY_YOUTUBE,
    MAX_BATCH_URLS,
    MAX_TIMEOUT,
    MIN_TIMEOUT,
)

logger = logging.getLogger(__name__)


def _run_cli(cmd: list[str], timeout: int = 3600) -> tuple[bool, str]:
    """Run a CLI command and return success status and output.

    Args:
        cmd: Command list to execute
        timeout: Timeout in seconds (default: 1 hour for batch operations)

    Returns:
        Tuple of (success, output) where output is stdout on success or stderr on failure
    """
    try:
        # cmd is built from hardcoded "gobbler" binary with validated user arguments
        result = subprocess.run(  # noqa: S603  # nosec B603
            cmd,
            check=False, capture_output=True,
            text=True,
            timeout=timeout,
        )
        if result.returncode != 0:
            return (
                False,
                result.stderr.strip() or f"Command failed with exit code {result.returncode}",
            )
        return True, result.stdout
    except subprocess.TimeoutExpired:
        return False, f"Command timed out after {timeout} seconds"
    except FileNotFoundError:
        return False, "gobbler CLI not found. Ensure it's installed and in PATH."
    except Exception as e:
        return False, f"Failed to run command: {e!s}"


def _parse_json_output(output: str) -> dict:
    """Parse JSON output from CLI command.

    Args:
        output: Raw CLI output (may contain JSON or text)

    Returns:
        Parsed dict or error dict
    """
    try:
        return json.loads(output)
    except json.JSONDecodeError:
        # If not JSON, wrap the text output
        return {"output": output, "format": "text"}


def _format_batch_report(data: dict) -> str:
    """Format batch result data as a human-readable report.

    Args:
        data: Batch result dictionary from CLI

    Returns:
        Formatted markdown report
    """
    # If it's just text output, return as-is
    if data.get("format") == "text":
        return data.get("output", "")

    # Build report from structured data
    total = data.get("total_items", data.get("total", 0))
    successful = data.get("successful", data.get("success", 0))
    failed = data.get("failed", data.get("failures", 0))
    skipped = data.get("skipped", 0)
    output_dir = data.get("output_dir", "")
    processing_time = data.get("processing_time_seconds", data.get("time", 0))

    success_rate = (successful / total * 100) if total > 0 else 0

    # Format processing time
    minutes = int(processing_time // 60)
    seconds = int(processing_time % 60)
    time_str = f"{minutes}m {seconds}s" if minutes > 0 else f"{seconds}s"

    lines = [
        "# Batch Operation Summary\n",
        f"**Status:** {'Completed' if failed == 0 else 'Completed with errors'}\n",
        "## Statistics",
        f"- **Total Items:** {total}",
        f"- **Successful:** {successful} ({success_rate:.1f}%)",
        f"- **Failed:** {failed}",
        f"- **Skipped:** {skipped}",
        f"- **Processing Time:** {time_str}\n",
    ]

    # Show successful items
    success_details = data.get("success_details", data.get("successful_items", []))
    if success_details:
        lines.append("## Successful Items")
        for i, item in enumerate(success_details[:10], 1):  # Limit to first 10
            if isinstance(item, dict):
                source = item.get("source", item.get("file", "unknown"))
                output = item.get("output_file", item.get("output", ""))
                lines.append(f"{i}. {source} -> {output}")
            else:
                lines.append(f"{i}. {item}")
        if len(success_details) > 10:
            lines.append(f"... and {len(success_details) - 10} more")
        lines.append("")

    # Show failed items
    failures = data.get("failures", data.get("failed_items", []))
    if failures:
        lines.append("## Failed Items")
        for i, item in enumerate(failures[:10], 1):
            if isinstance(item, dict):
                source = item.get("source", item.get("file", "unknown"))
                error = item.get("error", "Unknown error")
                lines.append(f"{i}. {source} - {error}")
            else:
                lines.append(f"{i}. {item}")
        if len(failures) > 10:
            lines.append(f"... and {len(failures) - 10} more")
        lines.append("")

    # Output location
    if output_dir:
        lines.append("## Output Location")
        lines.append(f"All files saved to: {output_dir}\n")

    return "\n".join(lines)


def register_tools(mcp: FastMCP):
    """Register batch processing tools with the MCP server."""

    @mcp.tool()
    async def batch_transcribe_youtube_playlist(
        playlist_url: str,
        output_dir: str,
        include_timestamps: bool = False,
        language: str = "en",
        concurrency: int = 3,
    ) -> str:
        """Extract transcripts from all videos in a YouTube playlist.

        Processes videos with controlled concurrency. All transcripts are saved
        to the output directory as markdown files.

        Args:
            playlist_url: YouTube playlist URL (youtube.com/playlist?list=...)
            output_dir: Directory to save markdown transcripts (must be absolute path)
            include_timestamps: Include timestamp markers in transcripts (default: False)
            language: Transcript language code (default: 'en')
            concurrency: Number of videos to process concurrently (default: 3, max: 10)

        Returns:
            Batch summary report with statistics and file list
        """
        # Validate output directory
        output_path = Path(output_dir)
        if not output_path.is_absolute():
            return f"Error: output_dir must be an absolute path. Got: {output_dir}"

        # Validate concurrency
        if concurrency < 1 or concurrency > MAX_BATCH_CONCURRENCY_YOUTUBE:
            return f"Error: concurrency must be between 1 and {MAX_BATCH_CONCURRENCY_YOUTUBE}"

        # Build CLI command
        cmd = [
            "gobbler",
            "batch",
            "youtube-playlist",
            playlist_url,
            "--output",
            output_dir,
            "--language",
            language,
            "--concurrency",
            str(concurrency),
            "--json",  # Use JSON output for parsing
        ]

        if include_timestamps:
            cmd.append("--timestamps")

        # Run CLI command (long timeout for playlists)
        success, output = _run_cli(cmd, timeout=7200)  # 2 hour timeout

        if not success:
            return f"Error: {output}"

        # Parse and format output
        data = _parse_json_output(output)
        return _format_batch_report(data)

    @mcp.tool()
    async def batch_fetch_webpages(
        urls: list[str],
        output_dir: str,
        timeout: int = 30,
        concurrency: int = 5,
        skip_existing: bool = True,
    ) -> str:
        """Convert multiple web pages to markdown format.

        Processes URLs with controlled concurrency to avoid overwhelming target servers.
        Automatically generates filenames from page titles or URLs.
        All results are saved to the output directory.

        Args:
            urls: List of web page URLs to convert (max: 100 URLs per batch)
            output_dir: Directory to save markdown files (must be absolute path)
            timeout: Request timeout per page in seconds (default: 30, max: 120)
            concurrency: Number of pages to process concurrently (default: 5, max: 10)
            skip_existing: Skip URLs that already have output files (default: True)

        Returns:
            Batch summary report with statistics and file list
        """
        # Validate parameters
        if not urls:
            return "Error: urls list cannot be empty"

        if len(urls) > MAX_BATCH_URLS:
            return f"Error: Maximum {MAX_BATCH_URLS} URLs per batch. Please split into smaller batches."

        if timeout < MIN_TIMEOUT or timeout > MAX_TIMEOUT:
            return f"Error: timeout must be between {MIN_TIMEOUT} and {MAX_TIMEOUT} seconds"

        if concurrency < 1 or concurrency > MAX_BATCH_CONCURRENCY_WEBPAGE:
            return f"Error: concurrency must be between 1 and {MAX_BATCH_CONCURRENCY_WEBPAGE}"

        # Validate output directory
        output_path = Path(output_dir)
        if not output_path.is_absolute():
            return f"Error: output_dir must be an absolute path. Got: {output_dir}"

        # Write URLs to a temporary file for CLI input
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            for url in urls:
                f.write(url + "\n")
            urls_file = f.name

        try:
            # Build CLI command
            cmd = [
                "gobbler",
                "batch",
                "webpages",
                urls_file,
                "--output-dir",
                output_dir,
                "--timeout",
                str(timeout),
                "--concurrency",
                str(concurrency),
                "--json",  # Use JSON output for parsing
            ]

            if not skip_existing:
                cmd.append("--no-skip-existing")

            # Run CLI command
            success, output = _run_cli(cmd, timeout=len(urls) * timeout + 300)

            if not success:
                return f"Error: {output}"

            # Parse and format output
            data = _parse_json_output(output)
            return _format_batch_report(data)

        finally:
            # Clean up temp file
            Path(urls_file).unlink(missing_ok=True)

    @mcp.tool()
    async def batch_transcribe_audio(
        input_dir: str,
        output_dir: str | None = None,
        model: str = "small",
        language: str = "auto",
        pattern: str = "*",
        recursive: bool = False,
        concurrency: int = 2,
    ) -> str:
        """Transcribe all audio/video files in a directory.

        Automatically detects supported file formats and processes them with Whisper.
        Supported formats: mp3, mp4, wav, m4a, mov, avi, mkv, flac, ogg, webm.
        All results are saved to the output directory.

        Args:
            input_dir: Directory containing audio/video files (must be absolute path)
            output_dir: Directory for transcripts (default: same as input_dir)
            model: Whisper model size (default: 'small', options: tiny, base, small, medium, large)
            language: Audio language code or 'auto' (default: 'auto')
            pattern: Glob pattern for file matching (default: '*' for all supported formats)
            recursive: Search subdirectories (default: False)
            concurrency: Number of files to process concurrently (default: 2, max: 4)

        Returns:
            Batch summary report with statistics and file list
        """
        # Validate input directory
        input_path = Path(input_dir)
        if not input_path.is_absolute():
            return f"Error: input_dir must be an absolute path. Got: {input_dir}"

        if not input_path.exists():
            return f"Error: Directory not found: {input_dir}"

        if not input_path.is_dir():
            return f"Error: Not a directory: {input_dir}"

        # Validate concurrency
        if concurrency < 1 or concurrency > MAX_BATCH_CONCURRENCY_AUDIO:
            return f"Error: concurrency must be between 1 and {MAX_BATCH_CONCURRENCY_AUDIO}"

        # Build CLI command
        cmd = [
            "gobbler",
            "batch",
            "directory",
            str(input_dir),
            "--pattern",
            pattern,
            "--concurrency",
            str(concurrency),
            "--type",
            "audio",
            "--json",  # Use JSON output for parsing
        ]

        if output_dir:
            cmd.extend(["--output", output_dir])

        if language != "auto":
            cmd.extend(["--language", language])

        if model != "small":
            cmd.extend(["--model", model])

        if recursive:
            cmd.append("--recursive")

        # Run CLI command (very long timeout for audio transcription)
        success, output = _run_cli(cmd, timeout=86400)  # 24 hour timeout

        if not success:
            return f"Error: {output}"

        # Parse and format output
        data = _parse_json_output(output)
        return _format_batch_report(data)

    @mcp.tool()
    async def batch_convert_documents(
        input_dir: str,
        output_dir: str | None = None,
        enable_ocr: bool = True,
        pattern: str = "*",
        recursive: bool = False,
        concurrency: int = 3,
    ) -> str:
        """Convert all documents in a directory to markdown.

        Supports PDF, DOCX, PPTX, XLSX with optional OCR for scanned documents.
        All results are saved to the output directory.

        Args:
            input_dir: Directory containing documents (must be absolute path)
            output_dir: Directory for markdown files (default: same as input_dir)
            enable_ocr: Enable OCR for scanned documents (default: True)
            pattern: Glob pattern for file matching (default: '*' for all supported formats)
            recursive: Search subdirectories (default: False)
            concurrency: Number of documents to process concurrently (default: 3, max: 5)

        Returns:
            Batch summary report with statistics and file list
        """
        # Validate input directory
        input_path = Path(input_dir)
        if not input_path.is_absolute():
            return f"Error: input_dir must be an absolute path. Got: {input_dir}"

        if not input_path.exists():
            return f"Error: Directory not found: {input_dir}"

        if not input_path.is_dir():
            return f"Error: Not a directory: {input_dir}"

        # Validate concurrency
        if concurrency < 1 or concurrency > MAX_BATCH_CONCURRENCY_DOCUMENT:
            return f"Error: concurrency must be between 1 and {MAX_BATCH_CONCURRENCY_DOCUMENT}"

        # Build CLI command
        cmd = [
            "gobbler",
            "batch",
            "directory",
            str(input_dir),
            "--pattern",
            pattern,
            "--concurrency",
            str(concurrency),
            "--type",
            "document",
            "--json",  # Use JSON output for parsing
        ]

        if output_dir:
            cmd.extend(["--output", output_dir])

        if not enable_ocr:
            cmd.append("--no-ocr")

        if recursive:
            cmd.append("--recursive")

        # Run CLI command
        success, output = _run_cli(cmd, timeout=10800)  # 3 hour timeout

        if not success:
            return f"Error: {output}"

        # Parse and format output
        data = _parse_json_output(output)
        return _format_batch_report(data)
