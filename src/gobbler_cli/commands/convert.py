"""Conversion commands for individual content items."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Annotated

import typer

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


@app.command()
def youtube(
    url: Annotated[str, typer.Argument(help="YouTube video URL")],
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
    format: Annotated[
        OutputFormat,
        typer.Option("--format", "-f", help="Output format"),
    ] = OutputFormat.MARKDOWN,
) -> None:
    """Convert a YouTube video to markdown.

    Examples:
        gobbler youtube https://youtube.com/watch?v=ABC123
        gobbler youtube https://youtube.com/watch?v=ABC123 -o transcript.md
        gobbler youtube https://youtube.com/watch?v=ABC123 --language es --timestamps
    """
    asyncio.run(
        _convert_youtube(
            url=url,
            output=output,
            language=language,
            timestamps=timestamps,
            format=format,
        )
    )


async def _convert_youtube(
    url: str,
    output: Path | None,
    language: str,
    timestamps: bool,
    format: OutputFormat,
) -> None:
    """Async implementation of YouTube conversion."""
    try:
        # Import here to avoid circular imports and defer heavy imports
        from gobbler_core.converters.youtube import convert_youtube_to_markdown

        with ProgressTracker("Converting YouTube video"):
            result, metadata = await convert_youtube_to_markdown(
                video_url=url,
                language=language,
                include_timestamps=timestamps,
            )

        if format == OutputFormat.JSON:
            json_result = format_json_success(result, metadata, source=url)
            write_json_result(json_result, output)
        else:
            write_output(result, output, format)
            if output:
                print_success("YouTube video converted successfully")
    except Exception as e:
        if format == OutputFormat.JSON:
            json_result = format_json_error(str(e), "YOUTUBE_CONVERSION_ERROR", source=url)
            write_json_result(json_result)
        else:
            print_error(f"Failed to convert YouTube video: {e}")
        raise typer.Exit(1)


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
    format: Annotated[
        OutputFormat,
        typer.Option("--format", "-f", help="Output format"),
    ] = OutputFormat.MARKDOWN,
) -> None:
    """Transcribe an audio file to markdown.

    Examples:
        gobbler audio recording.mp3
        gobbler audio recording.mp3 -o transcript.md
        gobbler audio recording.mp3 --model medium --language es
    """
    asyncio.run(
        _convert_audio(
            file_path=file_path,
            output=output,
            language=language,
            model=model,
            timestamps=timestamps,
            format=format,
        )
    )


async def _convert_audio(
    file_path: Path,
    output: Path | None,
    language: str | None,
    model: str,
    timestamps: bool,
    format: OutputFormat,
) -> None:
    """Async implementation of audio conversion."""
    source = str(file_path)
    try:
        # Validate file exists
        if not file_path.exists():
            raise ValueError(f"File not found: {file_path}")

        # Import here to avoid circular imports and defer heavy imports
        from gobbler_core.converters.audio import convert_audio_to_markdown

        with ProgressTracker("Transcribing audio file"):
            # Note: timestamps option is not currently supported by the underlying converter
            if timestamps and format != OutputFormat.JSON:
                print_warning("Timestamps option is not yet implemented in the audio converter")

            result, metadata = await convert_audio_to_markdown(
                file_path=str(file_path),
                language=language or "auto",
                model=model,
            )

        if format == OutputFormat.JSON:
            json_result = format_json_success(result, metadata, source=source)
            write_json_result(json_result, output)
        else:
            write_output(result, output, format)
            if output:
                print_success("Audio file transcribed successfully")
    except Exception as e:
        if format == OutputFormat.JSON:
            json_result = format_json_error(str(e), "AUDIO_CONVERSION_ERROR", source=source)
            write_json_result(json_result)
        else:
            print_error(f"Failed to transcribe audio: {e}")
        raise typer.Exit(1)


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
    format: Annotated[
        OutputFormat,
        typer.Option("--format", "-f", help="Output format"),
    ] = OutputFormat.MARKDOWN,
) -> None:
    """Convert a document (PDF, DOCX, etc.) to markdown.

    Examples:
        gobbler document report.pdf
        gobbler document report.pdf -o output.md
        gobbler document scanned.pdf --ocr
    """
    asyncio.run(
        _convert_document(
            file_path=file_path,
            output=output,
            ocr=ocr,
            format=format,
        )
    )


async def _convert_document(
    file_path: Path,
    output: Path | None,
    ocr: bool,
    format: OutputFormat,
) -> None:
    """Async implementation of document conversion."""
    source = str(file_path)
    try:
        # Validate file exists
        if not file_path.exists():
            raise ValueError(f"File not found: {file_path}")

        # Import here to avoid circular imports and defer heavy imports
        from gobbler_core.converters.document import convert_document_to_markdown

        with ProgressTracker("Converting document"):
            result, metadata = await convert_document_to_markdown(
                file_path=str(file_path),
                enable_ocr=ocr,
            )

        if format == OutputFormat.JSON:
            json_result = format_json_success(result, metadata, source=source)
            write_json_result(json_result, output)
        else:
            write_output(result, output, format)
            if output:
                print_success("Document converted successfully")
    except Exception as e:
        if format == OutputFormat.JSON:
            json_result = format_json_error(str(e), "DOCUMENT_CONVERSION_ERROR", source=source)
            write_json_result(json_result)
        else:
            print_error(f"Failed to convert document: {e}")
        raise typer.Exit(1)


@app.command()
def webpage(
    url: Annotated[str, typer.Argument(help="Web page URL")],
    output: Annotated[
        Path | None,
        typer.Option("--output", "-o", help="Output file path (stdout if not specified)"),
    ] = None,
    css_selector: Annotated[
        str | None,
        typer.Option("--selector", "-s", help="CSS selector to extract specific content"),
    ] = None,
    timeout: Annotated[
        int,
        typer.Option("--timeout", "-t", help="Request timeout in seconds"),
    ] = 30,
    format: Annotated[
        OutputFormat,
        typer.Option("--format", "-f", help="Output format"),
    ] = OutputFormat.MARKDOWN,
) -> None:
    """Convert a web page to markdown.

    Examples:
        gobbler webpage https://example.com
        gobbler webpage https://example.com -o page.md
        gobbler webpage https://example.com --selector "article"
    """
    asyncio.run(
        _convert_webpage(
            url=url,
            output=output,
            css_selector=css_selector,
            timeout=timeout,
            format=format,
        )
    )


async def _convert_webpage(
    url: str,
    output: Path | None,
    css_selector: str | None,
    timeout: int,
    format: OutputFormat,
) -> None:
    """Async implementation of webpage conversion."""
    try:
        # Import here to avoid circular imports and defer heavy imports
        from gobbler_core.converters.webpage import convert_webpage_to_markdown

        with ProgressTracker("Converting web page"):
            # Note: css_selector is not currently supported by the underlying converter
            # It uses the Gobbler service for extraction instead
            if css_selector and format != OutputFormat.JSON:
                print_warning("CSS selector option is not yet implemented in the webpage converter")

            result, metadata = await convert_webpage_to_markdown(
                url=url,
                timeout=timeout,
            )

        if format == OutputFormat.JSON:
            json_result = format_json_success(result, metadata, source=url)
            write_json_result(json_result, output)
        else:
            write_output(result, output, format)
            if output:
                print_success("Web page converted successfully")
    except Exception as e:
        if format == OutputFormat.JSON:
            json_result = format_json_error(str(e), "WEBPAGE_CONVERSION_ERROR", source=url)
            write_json_result(json_result)
        else:
            print_error(f"Failed to convert web page: {e}")
        raise typer.Exit(1)
