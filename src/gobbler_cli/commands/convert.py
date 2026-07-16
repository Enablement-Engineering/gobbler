"""Conversion commands for individual content items."""

from __future__ import annotations

import asyncio
import re
import time
from contextlib import nullcontext
from pathlib import Path
from typing import TYPE_CHECKING, Annotated, Any, cast
from urllib.parse import urlparse

import typer

if TYPE_CHECKING:
    from gobbler_core.providers.document import DocumentProvider
    from gobbler_core.providers.transcription import TranscriptionProvider
    from gobbler_core.providers.webpage import WebPageProvider

from gobbler_cli.output import (
    OutputFormat,
    add_json_contract,
    format_json_error,
    format_json_success,
    open_output_file,
    print_error,
    print_success,
    print_warning,
    validate_open_request,
    write_json_result,
    write_output,
)
from gobbler_cli.progress import ProgressTracker
from gobbler_core.utils.redaction import REDACTED, redact_value

YOUTUBE_TIMEOUT_DEFAULT = 120
YOUTUBE_INVALID_URL_MESSAGE = (
    "Invalid YouTube URL: expected https://youtube.com/watch?v=VIDEO_ID "
    "or https://youtu.be/VIDEO_ID."
)
YOUTUBE_INVALID_URL_CODE = "YOUTUBE_INVALID_URL"
YOUTUBE_TRANSCRIPTAPI_BILLING_REQUIRED_CODE = "YOUTUBE_TRANSCRIPTAPI_BILLING_REQUIRED"
YOUTUBE_TRANSCRIPTAPI_PAYMENT_REQUIRED_STATUS_CODE = 402
YOUTUBE_TRANSCRIPTAPI_BILLING_REQUIRED_SUGGESTION = (
    "Check TranscriptAPI billing, quota, and active plan/account state, or use another "
    "transcript source."
)
YOUTUBE_INVALID_URL_SUGGESTION = (
    "Provide a YouTube URL like https://youtube.com/watch?v=dQw4w9WgXcQ "
    "or https://youtu.be/dQw4w9WgXcQ."
)
WEBPAGE_INVALID_URL_MESSAGE = "Invalid webpage URL: expected an absolute http:// or https:// URL."
WEBPAGE_INVALID_URL_CODE = "WEBPAGE_INVALID_URL"
WEBPAGE_INVALID_URL_SUGGESTION = "Provide a URL like https://example.com."
ASCII_CONTROL_CODEPOINT_LIMIT = 32
ASCII_DELETE_CODEPOINT = 127
YOUTUBE_URL_PATTERN = re.compile(
    r"^https?://(www\.)?(youtube\.com/watch\?v=|youtu\.be/)([a-zA-Z0-9_-]{11})(?=$|[&?#/])"
)


def _webpage_success_receipt(
    *,
    url: str,
    output: Path | None,
    markdown: str,
    metadata: dict[str, Any],
    provider_name: str | None,
    use_proxy: bool,
    elapsed_time_ms: int,
) -> dict[str, Any]:
    """Build a success receipt without retaining sensitive URL components."""
    return {
        "provider": str(metadata.get("provider") or provider_name or "crawl4ai"),
        "proxy_mode": "enabled" if use_proxy else "disabled",
        "source_host": urlparse(url).hostname,
        "output_path": str(output) if output else None,
        "byte_count": len(markdown.encode("utf-8")),
        "elapsed_time_ms": elapsed_time_ms,
    }


app = typer.Typer(help="Convert individual content items to markdown")


def _read_stdin_url() -> str | None:
    """Read a URL from stdin if available.

    Returns:
        URL string or None if stdin is empty/not available
    """
    import sys

    if sys.stdin.isatty():
        return None

    line = sys.stdin.readline().strip()
    return line if line else None


def _safe_error_text(error: Exception) -> str:
    """Return a redacted error string for CLI diagnostics."""
    return str(redact_value(str(error)))


def _safe_error_diagnostics(error: Exception) -> dict[str, Any] | None:
    """Return redacted structured diagnostics attached to an exception."""
    diagnostics = getattr(error, "diagnostics", None)
    if not isinstance(diagnostics, dict):
        return None
    redacted = redact_value(diagnostics)
    return redacted if isinstance(redacted, dict) else None


def _is_transcriptapi_billing_required_error(
    error_text: str, diagnostics: dict[str, Any] | None
) -> bool:
    """Return True for TranscriptAPI payment/account-plan failures."""
    if diagnostics:
        provider = str(diagnostics.get("provider", "")).lower()
        error_type = str(diagnostics.get("error_type", "")).lower()
        status_code = diagnostics.get("status_code")
        if provider == "transcriptapi":
            return (
                error_type == "billing_required"
                or status_code == YOUTUBE_TRANSCRIPTAPI_PAYMENT_REQUIRED_STATUS_CODE
            )

    lowered = error_text.lower()
    return "transcriptapi" in lowered and (
        "payment required" in lowered or "active paid plan" in lowered or "billing" in lowered
    )


def _youtube_error_response_metadata(
    error_text: str, diagnostics: dict[str, Any] | None
) -> tuple[str, str | None]:
    """Return the stable JSON error code and suggestion for a YouTube failure."""
    if _is_transcriptapi_billing_required_error(error_text, diagnostics):
        return (
            YOUTUBE_TRANSCRIPTAPI_BILLING_REQUIRED_CODE,
            YOUTUBE_TRANSCRIPTAPI_BILLING_REQUIRED_SUGGESTION,
        )
    return "YOUTUBE_CONVERSION_ERROR", None


def _webpage_json_error_suggestion(diagnostics: dict[str, Any] | None) -> str | None:
    """Return contextual webpage JSON guidance from provider diagnostics when available."""
    if not diagnostics:
        return None
    advice = diagnostics.get("advice")
    if isinstance(advice, str) and advice.strip():
        return str(redact_value(advice))
    return None


def _write_missing_input_error(message: str, error_code: str, output_format: OutputFormat) -> None:
    """Write a missing input error in the requested output format."""
    if output_format == OutputFormat.JSON:
        write_json_result(format_json_error(message, error_code))
    else:
        print_error(message)


def _write_skip_result(output: Path, source: str, output_format: OutputFormat) -> None:
    """Write an idempotent skip result in the requested output format."""
    if output_format == OutputFormat.JSON:
        write_json_result(
            add_json_contract(
                {
                    "success": True,
                    "skipped": True,
                    "reason": "output_exists",
                    "output": str(output),
                    "source": source,
                }
            )
        )
    else:
        print_warning(f"Skipped: {output} already exists")


def _write_provider_not_found_error(
    error: Exception,
    error_code: str,
    source: str,
    output_format: OutputFormat,
    *,
    json_source: str | None = None,
) -> None:
    """Write a provider lookup failure in the requested output format."""
    error_text = _safe_error_text(error)
    if output_format == OutputFormat.JSON:
        write_json_result(format_json_error(error_text, error_code, source=json_source or source))
    else:
        print_error(error_text)


def _validate_open_option(
    open_requested: bool, output: Path | None, output_format: OutputFormat
) -> None:
    """Validate a conversion ``--open`` request and render a clear CLI error."""
    try:
        validate_open_request(open_requested, output, output_format)
    except ValueError as exc:
        if output_format == OutputFormat.JSON:
            write_json_result(format_json_error(str(exc), "OPEN_NOT_AVAILABLE"))
        else:
            print_error(str(exc))
        raise typer.Exit(2) from None


def _open_output_or_warn(output: Path) -> None:
    """Open a completed output without turning opener failure into conversion failure."""
    try:
        open_output_file(output)
    except RuntimeError as exc:
        print_warning(str(exc))


def _is_valid_webpage_url(url: str) -> bool:
    """Return whether a single webpage URL is an absolute HTTP(S) URL.

    Args:
        url: User-provided webpage URL.

    Returns:
        True when the URL has an http/https scheme and hostname.
    """
    if any(
        char.isspace()
        or ord(char) < ASCII_CONTROL_CODEPOINT_LIMIT
        or ord(char) == ASCII_DELETE_CODEPOINT
        for char in url
    ):
        return False

    try:
        parsed = urlparse(url)
        hostname = parsed.hostname
        # Accessing .port forces urllib.parse to validate malformed or out-of-range ports.
        _ = parsed.port
    except ValueError:
        return False

    return parsed.scheme in {"http", "https"} and bool(hostname)


def _write_invalid_webpage_url_error(url: str, output_format: OutputFormat) -> None:
    """Write an invalid webpage URL error in the requested output format.

    Args:
        url: User-provided webpage URL.
        output_format: Requested CLI output format.
    """
    if output_format == OutputFormat.JSON:
        write_json_result(
            format_json_error(
                WEBPAGE_INVALID_URL_MESSAGE,
                WEBPAGE_INVALID_URL_CODE,
                source=_safe_webpage_failure_source(url),
                suggestion=WEBPAGE_INVALID_URL_SUGGESTION,
            )
        )
    else:
        print_error(WEBPAGE_INVALID_URL_MESSAGE)


def _sanitize_unparseable_webpage_source(url: str) -> str:
    """Best-effort source sanitizer for URL strings that urllib rejects."""
    source_without_params = re.split(r"[?#]", url, maxsplit=1)[0]
    if "://" in source_without_params:
        scheme, rest = source_without_params.split("://", 1)
        if "@" in rest:
            _, hostpath = rest.rsplit("@", 1)
            return f"{scheme}://{REDACTED}@{hostpath}"
        return source_without_params

    if source_without_params.startswith("//") and "@" in source_without_params[2:]:
        _, hostpath = source_without_params[2:].rsplit("@", 1)
        return f"//{REDACTED}@{hostpath}"

    if "@" in source_without_params:
        return REDACTED

    return source_without_params


def _safe_webpage_success_source(url: str) -> str:
    """Return the host-only source identifier safe for persisted success JSON."""
    try:
        hostname = urlparse(url).hostname
    except ValueError:
        return REDACTED
    return hostname or REDACTED


def _sanitize_webpage_success_value(value: Any, url: str, safe_source: str) -> Any:
    """Replace a submitted URL wherever a successful JSON payload may retain it."""
    if isinstance(value, str):
        return value.replace(url, safe_source)
    if isinstance(value, dict):
        return {
            key: _sanitize_webpage_success_value(child, url, safe_source)
            for key, child in value.items()
        }
    if isinstance(value, list):
        return [_sanitize_webpage_success_value(child, url, safe_source) for child in value]
    return value


def _safe_webpage_failure_source(url: str) -> str:
    """Return a sanitized source URL for webpage JSON failure payloads.

    The original input can contain userinfo, query tokens, or fragments. Failure
    payloads are often persisted by automation, so keep only the stable URL
    identifier needed for debugging while removing credential-bearing parts.
    """
    try:
        parsed = urlparse(url)
    except ValueError:
        return _sanitize_unparseable_webpage_source(url)

    netloc = parsed.netloc
    if netloc and "@" in netloc:
        _, hostport = netloc.rsplit("@", 1)
        netloc = f"{REDACTED}@{hostport}"

    sanitized = parsed._replace(netloc=netloc, query="", fragment="").geturl()
    if not netloc and "@" in sanitized:
        return REDACTED
    return sanitized


def _validate_webpage_url(url: str, output_format: OutputFormat) -> None:
    """Reject invalid single webpage command URLs with CLI output.

    Args:
        url: User-provided webpage URL.
        output_format: Requested CLI output format.

    Raises:
        typer.Exit: If the URL is not an absolute http:// or https:// URL.
    """
    if _is_valid_webpage_url(url):
        return

    _write_invalid_webpage_url_error(url, output_format)
    raise typer.Exit(1)


def _is_valid_youtube_url(url: str) -> bool:
    """Return whether a single YouTube URL matches supported extraction formats.

    Args:
        url: User-provided YouTube URL.

    Returns:
        True when the URL matches the supported YouTube video URL formats.
    """
    return bool(YOUTUBE_URL_PATTERN.match(url))


def _safe_youtube_failure_source(url: str) -> str:
    """Return a sanitized source for invalid YouTube JSON diagnostics."""
    try:
        return _safe_webpage_failure_source(url)
    except Exception:
        return REDACTED


def _write_invalid_youtube_url_error(url: str, output_format: OutputFormat) -> None:
    """Write an invalid YouTube URL error in the requested output format.

    Args:
        url: User-provided YouTube URL.
        output_format: Requested CLI output format.
    """
    if output_format == OutputFormat.JSON:
        write_json_result(
            format_json_error(
                YOUTUBE_INVALID_URL_MESSAGE,
                YOUTUBE_INVALID_URL_CODE,
                source=_safe_youtube_failure_source(url),
                suggestion=YOUTUBE_INVALID_URL_SUGGESTION,
            )
        )
    else:
        print_error(YOUTUBE_INVALID_URL_MESSAGE)


def _validate_youtube_url(url: str, output_format: OutputFormat) -> None:
    """Reject invalid single YouTube command URLs with CLI output.

    Args:
        url: User-provided YouTube URL.
        output_format: Requested CLI output format.

    Raises:
        typer.Exit: If the URL is not a supported YouTube video URL.
    """
    if _is_valid_youtube_url(url):
        return

    _write_invalid_youtube_url_error(url, output_format)
    raise typer.Exit(1)


@app.command()
def youtube(
    url: Annotated[
        str | None, typer.Argument(help="YouTube video URL (use - or omit for stdin)")
    ] = None,
    output: Annotated[
        Path | None,
        typer.Option("--output", "-o", help="Output file path (stdout if not specified)"),
    ] = None,
    language: Annotated[
        str,
        typer.Option("--language", "-l", help="Preferred transcript language"),
    ] = "en",
    timestamps: Annotated[
        bool,
        typer.Option("--timestamps/--no-timestamps", help="Include timestamps in output"),
    ] = False,
    clean: Annotated[
        bool,
        typer.Option(
            "--clean/--no-clean", "-c", help="Merge choppy captions into flowing paragraphs"
        ),
    ] = False,
    output_format: Annotated[
        OutputFormat,
        typer.Option("--format", "-f", help="Output format"),
    ] = OutputFormat.MARKDOWN,
    timeout: Annotated[
        int,
        typer.Option("--timeout", "-t", help="Timeout in seconds for the full YouTube conversion"),
    ] = YOUTUBE_TIMEOUT_DEFAULT,
    skip_if_exists: Annotated[
        bool,
        typer.Option("--skip-if-exists", help="Skip conversion if output file already exists"),
    ] = False,
    open_result: Annotated[
        bool, typer.Option("--open", help="Open the output file after successful conversion")
    ] = False,
) -> None:
    """Convert a YouTube video to markdown.

    Examples:
        gobbler youtube https://youtube.com/watch?v=ABC123
        gobbler youtube https://youtube.com/watch?v=ABC123 -o transcript.md
        gobbler youtube https://youtube.com/watch?v=ABC123 --clean  # Flowing paragraphs
        gobbler youtube https://youtube.com/watch?v=ABC123 --language es --timestamps
        gobbler youtube https://youtube.com/watch?v=ABC123 --timeout 90
        gobbler youtube https://youtube.com/watch?v=ABC123 -o out.md --skip-if-exists
        echo "https://youtube.com/watch?v=ABC123" | gobbler youtube
    """
    _validate_open_option(open_result, output, output_format)
    output_existed = bool(output and output.exists())
    # Handle stdin input
    actual_url = url
    if url is None or url == "-":
        actual_url = _read_stdin_url()
        if not actual_url:
            _write_missing_input_error(
                "No URL provided. Provide a URL as argument or pipe from stdin.",
                "YOUTUBE_MISSING_URL",
                output_format,
            )
            raise typer.Exit(1)

    assert actual_url is not None
    if skip_if_exists and output and output.exists():
        _write_skip_result(output, actual_url, output_format)
        return

    _validate_youtube_url(actual_url, output_format)

    asyncio.run(
        _convert_youtube(
            url=actual_url,
            output=output,
            language=language,
            timestamps=timestamps,
            clean=clean,
            output_format=output_format,
            timeout=timeout,
            skip_if_exists=skip_if_exists,
        )
    )
    if open_result and output and not (skip_if_exists and output_existed):
        _open_output_or_warn(output)


def _clean_transcript(text: str) -> str:
    """Merge choppy caption lines into flowing paragraphs.

    YouTube captions are often broken into short 2-5 second segments.
    This function merges them into natural paragraphs.

    Args:
        text: Raw transcript with many short lines

    Returns:
        Cleaned transcript with flowing paragraphs
    """
    import re

    # Split into frontmatter and content
    parts = text.split("# Video Transcript\n\n", 1)
    expected_parts = 2
    if len(parts) != expected_parts:
        return text

    frontmatter_and_header = parts[0] + "# Video Transcript\n\n"
    content = parts[1]

    # Split into lines and merge
    lines = content.split("\n\n")

    # Merge lines into sentences/paragraphs
    merged = []
    current_paragraph: list[str] = []
    min_paragraph_length = 200

    for raw_line in lines:
        cleaned_line = raw_line.strip()
        if not cleaned_line:
            continue

        current_paragraph.append(cleaned_line)

        # Start new paragraph after sentence-ending punctuation
        # But only if we have a reasonable amount of content
        paragraph_text = " ".join(current_paragraph)
        if len(paragraph_text) > min_paragraph_length and re.search(r"[.!?]$", cleaned_line):
            merged.append(paragraph_text)
            current_paragraph = []

    # Don't forget the last paragraph
    if current_paragraph:
        merged.append(" ".join(current_paragraph))

    # Join paragraphs with double newlines
    cleaned_content = "\n\n".join(merged)

    return frontmatter_and_header + cleaned_content


async def _convert_youtube(
    url: str,
    output: Path | None,
    language: str,
    timestamps: bool,
    clean: bool,
    output_format: OutputFormat,
    timeout: int,
    skip_if_exists: bool = False,
) -> None:
    """Async implementation of YouTube conversion."""
    try:
        # Check if output exists and should skip
        if skip_if_exists and output and output.exists():
            _write_skip_result(output, url, output_format)
            return

        # Import here to avoid circular imports and defer heavy imports
        from gobbler_core.converters.youtube import convert_youtube_to_markdown

        progress_context = (
            nullcontext()
            if output_format == OutputFormat.JSON
            else ProgressTracker("Converting YouTube video")
        )
        with progress_context:
            result, metadata = await convert_youtube_to_markdown(
                video_url=url,
                language=language,
                include_timestamps=timestamps,
                timeout=timeout,
            )

        # Apply clean mode if requested (incompatible with timestamps)
        if clean and not timestamps:
            result = _clean_transcript(result)
            # Recalculate word count after cleaning
            from gobbler_core.utils.frontmatter import count_words

            metadata["word_count"] = count_words(result)

        if output_format == OutputFormat.JSON:
            json_result = format_json_success(result, metadata, source=url)
            write_json_result(json_result, output)
        else:
            write_output(result, output, output_format)
            if output:
                print_success("YouTube video converted successfully")
    except Exception as e:
        error_text = _safe_error_text(e)
        diagnostics = _safe_error_diagnostics(e)
        if output_format == OutputFormat.JSON:
            error_code, suggestion = _youtube_error_response_metadata(error_text, diagnostics)
            json_result = format_json_error(
                error_text,
                error_code,
                source=url,
                suggestion=suggestion,
            )
            if diagnostics:
                json_result["diagnostics"] = diagnostics
            write_json_result(json_result)
        else:
            print_error(f"Failed to convert YouTube video: {error_text}")
        raise typer.Exit(1) from None


@app.command()
def audio(
    file_path: Annotated[Path, typer.Argument(help="Audio file path")],
    output: Annotated[
        Path | None,
        typer.Option("--output", "-o", help="Output file path (stdout if not specified)"),
    ] = None,
    language: Annotated[
        str | None,
        typer.Option("--language", "-l", help="Audio language (auto-detect if not specified)"),
    ] = None,
    model: Annotated[
        str,
        typer.Option("--model", "-m", help="Whisper model size (tiny/base/small/medium/large)"),
    ] = "small",
    timestamps: Annotated[
        bool,
        typer.Option("--timestamps/--no-timestamps", help="Include timestamps in output"),
    ] = False,
    output_format: Annotated[
        OutputFormat,
        typer.Option("--format", "-f", help="Output format"),
    ] = OutputFormat.MARKDOWN,
    provider: Annotated[
        str | None,
        typer.Option("--provider", "-p", help="Transcription provider (default: whisper-local)"),
    ] = None,
    skip_if_exists: Annotated[
        bool,
        typer.Option("--skip-if-exists", help="Skip conversion if output file already exists"),
    ] = False,
    open_result: Annotated[
        bool, typer.Option("--open", help="Open the output file after successful conversion")
    ] = False,
) -> None:
    """Transcribe an audio file to markdown.

    Examples:
        gobbler audio recording.mp3
        gobbler audio recording.mp3 -o transcript.md
        gobbler audio recording.mp3 --model medium --language es
        gobbler audio recording.mp3 -o out.md --skip-if-exists
    """
    _validate_open_option(open_result, output, output_format)
    output_existed = bool(output and output.exists())
    asyncio.run(
        _convert_audio(
            file_path=file_path,
            output=output,
            language=language,
            model=model,
            timestamps=timestamps,
            output_format=output_format,
            provider_name=provider,
            skip_if_exists=skip_if_exists,
        )
    )
    if open_result and output and not (skip_if_exists and output_existed):
        _open_output_or_warn(output)


async def _convert_audio(
    file_path: Path,
    output: Path | None,
    language: str | None,
    model: str,
    timestamps: bool,
    output_format: OutputFormat,
    provider_name: str | None = None,
    skip_if_exists: bool = False,
) -> None:
    """Async implementation of audio conversion."""
    source = str(file_path)
    try:
        # Check if output exists and should skip
        if skip_if_exists and output and output.exists():
            _write_skip_result(output, source, output_format)
            return

        # Validate file exists
        if not file_path.exists():
            msg = f"File not found: {file_path}"
            raise ValueError(msg)

        # Import here to avoid circular imports and defer heavy imports
        from gobbler_core.converters.audio import convert_audio_to_markdown
        from gobbler_core.providers import ProviderNotFoundError, ProviderRegistry

        # Create provider if specified
        transcription_provider: TranscriptionProvider | None = None
        if provider_name:
            try:
                # Registry returns ContentProvider, cast to specific type
                transcription_provider = cast(
                    "TranscriptionProvider",
                    ProviderRegistry.create("transcription", provider_name, model=model),
                )
            except ProviderNotFoundError as e:
                _write_provider_not_found_error(
                    e,
                    "AUDIO_PROVIDER_NOT_FOUND",
                    source,
                    output_format,
                )
                raise typer.Exit(1) from None

        progress_context = (
            nullcontext()
            if output_format == OutputFormat.JSON
            else ProgressTracker("Transcribing audio file")
        )
        with progress_context:
            result, metadata = await convert_audio_to_markdown(
                file_path=str(file_path),
                language=language or "auto",
                model=model,
                include_timestamps=timestamps,
                provider=transcription_provider,
            )

        if output_format == OutputFormat.JSON:
            json_result = format_json_success(result, metadata, source=source)
            write_json_result(json_result, output)
        else:
            write_output(result, output, output_format)
            if output:
                print_success("Audio file transcribed successfully")
    except typer.Exit:
        raise
    except Exception as e:
        error_text = _safe_error_text(e)
        if output_format == OutputFormat.JSON:
            json_result = format_json_error(error_text, "AUDIO_CONVERSION_ERROR", source=source)
            write_json_result(json_result)
        else:
            print_error(f"Failed to transcribe audio: {error_text}")
        raise typer.Exit(1) from None


@app.command()
def document(
    file_path: Annotated[Path, typer.Argument(help="Document file path")],
    output: Annotated[
        Path | None,
        typer.Option("--output", "-o", help="Output file path (stdout if not specified)"),
    ] = None,
    ocr: Annotated[
        bool,
        typer.Option("--ocr/--no-ocr", help="Enable OCR for scanned documents"),
    ] = True,
    output_format: Annotated[
        OutputFormat,
        typer.Option("--format", "-f", help="Output format"),
    ] = OutputFormat.MARKDOWN,
    provider: Annotated[
        str | None,
        typer.Option("--provider", "-p", help="Document conversion provider (default: docling)"),
    ] = None,
    skip_if_exists: Annotated[
        bool,
        typer.Option("--skip-if-exists", help="Skip conversion if output file already exists"),
    ] = False,
    open_result: Annotated[
        bool, typer.Option("--open", help="Open the output file after successful conversion")
    ] = False,
) -> None:
    """Convert a document (PDF, DOCX, etc.) to markdown.

    Examples:
        gobbler document report.pdf
        gobbler document report.pdf -o output.md
        gobbler document scanned.pdf --ocr
        gobbler document report.pdf -o out.md --skip-if-exists
    """
    _validate_open_option(open_result, output, output_format)
    output_existed = bool(output and output.exists())
    asyncio.run(
        _convert_document(
            file_path=file_path,
            output=output,
            ocr=ocr,
            output_format=output_format,
            provider_name=provider,
            skip_if_exists=skip_if_exists,
        )
    )
    if open_result and output and not (skip_if_exists and output_existed):
        _open_output_or_warn(output)


async def _convert_document(
    file_path: Path,
    output: Path | None,
    ocr: bool,
    output_format: OutputFormat,
    provider_name: str | None = None,
    skip_if_exists: bool = False,
) -> None:
    """Async implementation of document conversion."""
    source = str(file_path)
    try:
        # Check if output exists and should skip
        if skip_if_exists and output and output.exists():
            _write_skip_result(output, source, output_format)
            return

        # Validate file exists
        if not file_path.exists():
            msg = f"File not found: {file_path}"
            raise ValueError(msg)

        # Import here to avoid circular imports and defer heavy imports
        from gobbler_core.converters.document import convert_document_to_markdown
        from gobbler_core.providers import ProviderNotFoundError, ProviderRegistry
        from gobbler_core.providers.document import get_default_provider

        # Create provider - use default if not specified (reads config for service URL)
        document_provider: DocumentProvider
        if provider_name:
            try:
                # Registry returns ContentProvider, cast to specific type
                document_provider = cast(
                    "DocumentProvider",
                    ProviderRegistry.create("document", provider_name),
                )
            except ProviderNotFoundError as e:
                _write_provider_not_found_error(
                    e,
                    "DOCUMENT_PROVIDER_NOT_FOUND",
                    source,
                    output_format,
                )
                raise typer.Exit(1) from None
        else:
            # Use default provider which reads config (including service URL)
            document_provider = get_default_provider()

        progress_context = (
            nullcontext()
            if output_format == OutputFormat.JSON
            else ProgressTracker("Converting document")
        )
        with progress_context:
            result, metadata = await convert_document_to_markdown(
                file_path=str(file_path),
                enable_ocr=ocr,
                provider=document_provider,
            )

        if output_format == OutputFormat.JSON:
            json_result = format_json_success(result, metadata, source=source)
            write_json_result(json_result, output)
        else:
            write_output(result, output, output_format)
            if output:
                print_success("Document converted successfully")
    except typer.Exit:
        raise
    except Exception as e:
        error_text = _safe_error_text(e)
        if output_format == OutputFormat.JSON:
            json_result = format_json_error(error_text, "DOCUMENT_CONVERSION_ERROR", source=source)
            write_json_result(json_result)
        else:
            print_error(f"Failed to convert document: {error_text}")
        raise typer.Exit(1) from None


@app.command()
def webpage(
    url: Annotated[
        str | None, typer.Argument(help="Web page URL (use - or omit for stdin)")
    ] = None,
    output: Annotated[
        Path | None,
        typer.Option("--output", "-o", help="Output file path (stdout if not specified)"),
    ] = None,
    css_selector: Annotated[
        str | None,
        typer.Option("--selector", "-s", help="CSS selector to extract specific content"),
    ] = None,
    clean: Annotated[
        bool,
        typer.Option("--clean/--no-clean", "-c", help="Auto-strip nav/footer/sidebar boilerplate"),
    ] = False,
    timeout: Annotated[
        int,
        typer.Option("--timeout", "-t", help="Request timeout in seconds"),
    ] = 30,
    include_images: Annotated[
        bool,
        typer.Option("--images/--no-images", help="Include images in output"),
    ] = True,
    output_format: Annotated[
        OutputFormat,
        typer.Option("--format", "-f", help="Output format"),
    ] = OutputFormat.MARKDOWN,
    provider: Annotated[
        str | None,
        typer.Option("--provider", "-p", help="Webpage conversion provider (default: crawl4ai)"),
    ] = None,
    use_proxy: Annotated[
        bool,
        typer.Option(
            "--proxy/--no-proxy",
            help="Use configured Crawl4AI webpage proxy settings",
        ),
    ] = True,
    verbose: Annotated[
        bool,
        typer.Option("--verbose", "-v", help="Enable verbose/debug logging"),
    ] = False,
    skip_if_exists: Annotated[
        bool,
        typer.Option("--skip-if-exists", help="Skip conversion if output file already exists"),
    ] = False,
    open_result: Annotated[
        bool, typer.Option("--open", help="Open the output file after successful conversion")
    ] = False,
) -> None:
    """Convert a web page to markdown.

    Examples:
        gobbler webpage https://example.com
        gobbler webpage https://example.com -o page.md
        gobbler webpage https://example.com --selector "article"
        gobbler webpage https://example.com --clean  # Auto-strip boilerplate
        gobbler webpage https://example.com --no-proxy
        echo "https://example.com" | gobbler webpage
    """
    _validate_open_option(open_result, output, output_format)
    output_existed = bool(output and output.exists())
    # Handle stdin input
    actual_url = url
    if url is None or url == "-":
        actual_url = _read_stdin_url()
        if not actual_url:
            _write_missing_input_error(
                "No URL provided. Provide a URL as argument or pipe from stdin.",
                "WEBPAGE_MISSING_URL",
                output_format,
            )
            raise typer.Exit(1)
    assert actual_url is not None
    if verbose:
        import logging

        logging.basicConfig(level=logging.DEBUG, format="%(name)s: %(message)s")

    asyncio.run(
        _convert_webpage(
            url=actual_url,
            output=output,
            css_selector=css_selector,
            clean=clean,
            timeout=timeout,
            include_images=include_images,
            output_format=output_format,
            provider_name=provider,
            use_proxy=use_proxy,
            skip_if_exists=skip_if_exists,
        )
    )
    if open_result and output and not (skip_if_exists and output_existed):
        _open_output_or_warn(output)


async def _convert_webpage(  # noqa: PLR0915
    url: str,
    output: Path | None,
    css_selector: str | None,
    clean: bool,
    timeout: int,
    include_images: bool,
    output_format: OutputFormat,
    provider_name: str | None = None,
    use_proxy: bool = True,
    skip_if_exists: bool = False,
) -> None:
    """Async implementation of webpage conversion."""
    try:
        # Check if output exists and should skip
        if skip_if_exists and output and output.exists():
            _write_skip_result(output, url, output_format)
            return

        _validate_webpage_url(url, output_format)
        conversion_started = time.perf_counter()

        # Use selector-based conversion if selector is provided or clean mode
        if css_selector or clean:
            from gobbler_core.converters.webpage_selector import convert_webpage_with_selector

            # If clean mode without selector, try common main content selectors
            effective_selector = css_selector
            if clean and not css_selector:
                effective_selector = "main, article, [role='main'], .content, #content"

            progress_context = (
                nullcontext()
                if output_format == OutputFormat.JSON
                else ProgressTracker(
                    "Converting web page" + (" with selector" if css_selector else " (clean mode)")
                )
            )
            with progress_context:
                result, metadata = await convert_webpage_with_selector(
                    url=url,
                    css_selector=effective_selector,
                    timeout=timeout,
                    include_images=include_images,
                    use_proxy=use_proxy,
                )
        else:
            # Import here to avoid circular imports and defer heavy imports
            from gobbler_core.converters.webpage import convert_webpage_to_markdown
            from gobbler_core.providers import ProviderNotFoundError, ProviderRegistry
            from gobbler_core.providers.webpage import get_default_provider

            # Create provider - use default if not specified (includes proxy config)
            webpage_provider: WebPageProvider
            if provider_name:
                try:
                    # Registry returns ContentProvider, cast to specific type
                    webpage_provider = cast(
                        "WebPageProvider",
                        ProviderRegistry.create("webpage", provider_name),
                    )
                except ProviderNotFoundError as e:
                    _write_provider_not_found_error(
                        e,
                        "WEBPAGE_PROVIDER_NOT_FOUND",
                        url,
                        output_format,
                        json_source=_safe_webpage_failure_source(url),
                    )
                    raise typer.Exit(1) from None
            else:
                # Use default provider which reads config (including proxy)
                webpage_provider = get_default_provider(use_proxy=use_proxy)

            progress_context = (
                nullcontext()
                if output_format == OutputFormat.JSON
                else ProgressTracker("Converting web page")
            )
            with progress_context:
                result, metadata = await convert_webpage_to_markdown(
                    url=url,
                    timeout=timeout,
                    include_images=include_images,
                    provider=webpage_provider,
                    use_proxy=use_proxy,
                )

        if output_format == OutputFormat.JSON:
            safe_source = _safe_webpage_success_source(url)
            safe_result = str(_sanitize_webpage_success_value(result, url, safe_source))
            safe_metadata = cast(
                "dict[str, Any]", _sanitize_webpage_success_value(metadata, url, safe_source)
            )
            json_result = format_json_success(safe_result, safe_metadata, source=safe_source)
            json_result["receipt"] = _webpage_success_receipt(
                url=url,
                output=output,
                markdown=result,
                metadata=metadata,
                provider_name=provider_name,
                use_proxy=use_proxy,
                elapsed_time_ms=int((time.perf_counter() - conversion_started) * 1000),
            )
            write_json_result(json_result, output)
        else:
            write_output(result, output, output_format)
            if output:
                print_success("Web page converted successfully")
    except typer.Exit:
        raise
    except Exception as e:
        error_text = _safe_error_text(e)
        diagnostics = _safe_error_diagnostics(e)
        if output_format == OutputFormat.JSON:
            json_result = format_json_error(
                error_text,
                "WEBPAGE_CONVERSION_ERROR",
                source=_safe_webpage_failure_source(url),
                suggestion=_webpage_json_error_suggestion(diagnostics),
            )
            if diagnostics:
                json_result["diagnostics"] = diagnostics
            write_json_result(json_result)
        else:
            print_error(f"Failed to convert web page: {error_text}")
        raise typer.Exit(1) from None
