"""Conversion commands for individual content items."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import TYPE_CHECKING, Annotated, cast

import typer

if TYPE_CHECKING:
    from gobbler_core.providers.document import DocumentProvider
    from gobbler_core.providers.transcription import TranscriptionProvider
    from gobbler_core.providers.webpage import WebPageProvider

from gobbler_cli.output import (
    OutputFormat,
    format_json_error,
    format_json_success,
    print_error,
    print_success,
    print_warning,
    write_json_result,
    write_output,
)
from gobbler_cli.progress import ProgressTracker

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
        gobbler youtube https://youtube.com/watch?v=ABC123 -o out.md --skip-if-exists
        echo "https://youtube.com/watch?v=ABC123" | gobbler youtube
    """
    # Handle stdin input
    actual_url = url
    if url is None or url == "-":
        actual_url = _read_stdin_url()
        if not actual_url:
            print_error("No URL provided. Provide a URL as argument or pipe from stdin.")
            raise typer.Exit(1)

    asyncio.run(
        _convert_youtube(
            url=actual_url,
            output=output,
            language=language,
            timestamps=timestamps,
            clean=clean,
            output_format=output_format,
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
    if len(parts) != 2:
        return text

    frontmatter_and_header = parts[0] + "# Video Transcript\n\n"
    content = parts[1]

    # Split into lines and merge
    lines = content.split("\n\n")

    # Merge lines into sentences/paragraphs
    merged = []
    current_paragraph = []

    for line in lines:
        line = line.strip()
        if not line:
            continue

        current_paragraph.append(line)

        # Start new paragraph after sentence-ending punctuation
        # But only if we have a reasonable amount of content
        if len(" ".join(current_paragraph)) > 200 and re.search(r"[.!?]$", line):
            merged.append(" ".join(current_paragraph))
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
    skip_if_exists: bool = False,
) -> None:
    """Async implementation of YouTube conversion."""
    try:
        # Check if output exists and should skip
        if skip_if_exists and output and output.exists():
            if output_format == OutputFormat.JSON:
                json_result = {
                    "success": True,
                    "skipped": True,
                    "reason": "output_exists",
                    "output": str(output),
                    "source": url,
                }
                write_json_result(json_result)
            else:
                print_warning(f"Skipped: {output} already exists")
            return

        # Import here to avoid circular imports and defer heavy imports
        from gobbler_core.converters.youtube import convert_youtube_to_markdown

        with ProgressTracker("Converting YouTube video"):
            result, metadata = await convert_youtube_to_markdown(
                video_url=url,
                language=language,
                include_timestamps=timestamps,
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
        if output_format == OutputFormat.JSON:
            json_result = format_json_error(str(e), "YOUTUBE_CONVERSION_ERROR", source=url)
            write_json_result(json_result)
        else:
            print_error(f"Failed to convert YouTube video: {e}")
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
            if output_format == OutputFormat.JSON:
                json_result = {
                    "success": True,
                    "skipped": True,
                    "reason": "output_exists",
                    "output": str(output),
                    "source": source,
                }
                write_json_result(json_result)
            else:
                print_warning(f"Skipped: {output} already exists")
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
                print_error(str(e))
                raise typer.Exit(1) from None

        with ProgressTracker("Transcribing audio file"):
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
    except Exception as e:
        if output_format == OutputFormat.JSON:
            json_result = format_json_error(str(e), "AUDIO_CONVERSION_ERROR", source=source)
            write_json_result(json_result)
        else:
            print_error(f"Failed to transcribe audio: {e}")
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
            if output_format == OutputFormat.JSON:
                json_result = {
                    "success": True,
                    "skipped": True,
                    "reason": "output_exists",
                    "output": str(output),
                    "source": source,
                }
                write_json_result(json_result)
            else:
                print_warning(f"Skipped: {output} already exists")
            return

        # Validate file exists
        if not file_path.exists():
            msg = f"File not found: {file_path}"
            raise ValueError(msg)

        # Import here to avoid circular imports and defer heavy imports
        from gobbler_core.converters.document import convert_document_to_markdown
        from gobbler_core.providers import ProviderNotFoundError, ProviderRegistry

        # Create provider if specified
        document_provider: DocumentProvider | None = None
        if provider_name:
            try:
                # Registry returns ContentProvider, cast to specific type
                document_provider = cast(
                    "DocumentProvider",
                    ProviderRegistry.create("document", provider_name),
                )
            except ProviderNotFoundError as e:
                print_error(str(e))
                raise typer.Exit(1) from None

        with ProgressTracker("Converting document"):
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
    except Exception as e:
        if output_format == OutputFormat.JSON:
            json_result = format_json_error(str(e), "DOCUMENT_CONVERSION_ERROR", source=source)
            write_json_result(json_result)
        else:
            print_error(f"Failed to convert document: {e}")
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
        echo "https://example.com" | gobbler webpage
    """
    # Handle stdin input
    actual_url = url
    if url is None or url == "-":
        actual_url = _read_stdin_url()
        if not actual_url:
            print_error("No URL provided. Provide a URL as argument or pipe from stdin.")
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
            skip_if_exists=skip_if_exists,
        )
    )


async def _convert_webpage(  # noqa: PLR0912
    url: str,
    output: Path | None,
    css_selector: str | None,
    clean: bool,
    timeout: int,
    include_images: bool,
    output_format: OutputFormat,
    provider_name: str | None = None,
    skip_if_exists: bool = False,
) -> None:
    """Async implementation of webpage conversion."""
    try:
        # Check if output exists and should skip
        if skip_if_exists and output and output.exists():
            if output_format == OutputFormat.JSON:
                json_result = {
                    "success": True,
                    "skipped": True,
                    "reason": "output_exists",
                    "output": str(output),
                    "source": url,
                }
                write_json_result(json_result)
            else:
                print_warning(f"Skipped: {output} already exists")
            return

        # Use selector-based conversion if selector is provided or clean mode
        if css_selector or clean:
            from gobbler_mcp.converters.webpage_selector import convert_webpage_with_selector

            # If clean mode without selector, try common main content selectors
            effective_selector = css_selector
            if clean and not css_selector:
                effective_selector = "main, article, [role='main'], .content, #content"

            with ProgressTracker(
                "Converting web page" + (" with selector" if css_selector else " (clean mode)")
            ):
                result, metadata = await convert_webpage_with_selector(
                    url=url,
                    css_selector=effective_selector,
                    timeout=timeout,
                    include_images=include_images,
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
                    print_error(str(e))
                    raise typer.Exit(1) from None
            else:
                # Use default provider which reads config (including proxy)
                webpage_provider = get_default_provider()

            with ProgressTracker("Converting web page"):
                result, metadata = await convert_webpage_to_markdown(
                    url=url,
                    timeout=timeout,
                    include_images=include_images,
                    provider=webpage_provider,
                )

        if output_format == OutputFormat.JSON:
            json_result = format_json_success(result, metadata, source=url)
            write_json_result(json_result, output)
        else:
            write_output(result, output, output_format)
            if output:
                print_success("Web page converted successfully")
    except Exception as e:
        if output_format == OutputFormat.JSON:
            json_result = format_json_error(str(e), "WEBPAGE_CONVERSION_ERROR", source=url)
            write_json_result(json_result)
        else:
            print_error(f"Failed to convert web page: {e}")
        raise typer.Exit(1) from None
