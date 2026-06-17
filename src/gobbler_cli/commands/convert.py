"""Conversion commands for individual content items."""

from __future__ import annotations

import asyncio
from contextlib import nullcontext
from pathlib import Path
from typing import TYPE_CHECKING, Annotated, Any, cast

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
    print_error,
    print_success,
    print_warning,
    write_json_result,
    write_output,
)
from gobbler_cli.progress import ProgressTracker
from gobbler_core.utils.redaction import redact_value

YOUTUBE_TIMEOUT_DEFAULT = 120

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
) -> None:
    """Write a provider lookup failure in the requested output format."""
    error_text = _safe_error_text(error)
    if output_format == OutputFormat.JSON:
        write_json_result(format_json_error(error_text, error_code, source=source))
    else:
        print_error(error_text)


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
            json_result = format_json_error(error_text, "YOUTUBE_CONVERSION_ERROR", source=url)
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
) -> None:
    """Transcribe an audio file to markdown.

    Examples:
        gobbler audio recording.mp3
        gobbler audio recording.mp3 -o transcript.md
        gobbler audio recording.mp3 --model medium --language es
        gobbler audio recording.mp3 -o out.md --skip-if-exists
    """
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
) -> None:
    """Convert a document (PDF, DOCX, etc.) to markdown.

    Examples:
        gobbler document report.pdf
        gobbler document report.pdf -o output.md
        gobbler document scanned.pdf --ocr
        gobbler document report.pdf -o out.md --skip-if-exists
    """
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


async def _convert_webpage(
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
            json_result = format_json_success(result, metadata, source=url)
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
            json_result = format_json_error(error_text, "WEBPAGE_CONVERSION_ERROR", source=url)
            if diagnostics:
                json_result["diagnostics"] = diagnostics
            write_json_result(json_result)
        else:
            print_error(f"Failed to convert web page: {error_text}")
        raise typer.Exit(1) from None
