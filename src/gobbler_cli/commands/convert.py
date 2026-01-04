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
    output_format: Annotated[
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
            output_format=output_format,
        )
    )


async def _convert_youtube(
    url: str,
    output: Path | None,
    language: str,
    timestamps: bool,
    output_format: OutputFormat,
) -> None:
    """Async implementation of YouTube conversion."""
    try:
        # Import here to avoid circular imports and defer heavy imports
        from gobbler_core.converters.youtube import convert_youtube_to_markdown  # noqa: PLC0415

        with ProgressTracker("Converting YouTube video"):
            result, metadata = await convert_youtube_to_markdown(
                video_url=url,
                language=language,
                include_timestamps=timestamps,
            )

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
) -> None:
    """Transcribe an audio file to markdown.

    Examples:
        gobbler audio recording.mp3
        gobbler audio recording.mp3 -o transcript.md
        gobbler audio recording.mp3 --model medium --language es
        gobbler audio recording.mp3 --provider whisper-local
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
) -> None:
    """Async implementation of audio conversion."""
    source = str(file_path)
    try:
        # Validate file exists
        if not file_path.exists():
            msg = f"File not found: {file_path}"
            raise ValueError(msg)  # noqa: TRY301

        # Import here to avoid circular imports and defer heavy imports
        from gobbler_core.converters.audio import convert_audio_to_markdown  # noqa: PLC0415
        from gobbler_core.providers import ProviderNotFoundError, ProviderRegistry  # noqa: PLC0415

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
) -> None:
    """Convert a document (PDF, DOCX, etc.) to markdown.

    Examples:
        gobbler document report.pdf
        gobbler document report.pdf -o output.md
        gobbler document scanned.pdf --ocr
        gobbler document report.pdf --provider docling
    """
    asyncio.run(
        _convert_document(
            file_path=file_path,
            output=output,
            ocr=ocr,
            output_format=output_format,
            provider_name=provider,
        )
    )


async def _convert_document(
    file_path: Path,
    output: Path | None,
    ocr: bool,
    output_format: OutputFormat,
    provider_name: str | None = None,
) -> None:
    """Async implementation of document conversion."""
    source = str(file_path)
    try:
        # Validate file exists
        if not file_path.exists():
            msg = f"File not found: {file_path}"
            raise ValueError(msg)  # noqa: TRY301

        # Import here to avoid circular imports and defer heavy imports
        from gobbler_core.converters.document import convert_document_to_markdown  # noqa: PLC0415
        from gobbler_core.providers import ProviderNotFoundError, ProviderRegistry  # noqa: PLC0415

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
) -> None:
    """Convert a web page to markdown.

    Examples:
        gobbler webpage https://example.com
        gobbler webpage https://example.com -o page.md
        gobbler webpage https://example.com --selector "article"
        gobbler webpage https://example.com --no-images
        gobbler webpage https://example.com --provider crawl4ai
    """
    asyncio.run(
        _convert_webpage(
            url=url,
            output=output,
            css_selector=css_selector,
            timeout=timeout,
            include_images=include_images,
            output_format=output_format,
            provider_name=provider,
        )
    )


async def _convert_webpage(
    url: str,
    output: Path | None,
    css_selector: str | None,
    timeout: int,
    include_images: bool,
    output_format: OutputFormat,
    provider_name: str | None = None,
) -> None:
    """Async implementation of webpage conversion."""
    try:
        # Import here to avoid circular imports and defer heavy imports
        from gobbler_core.converters.webpage import convert_webpage_to_markdown  # noqa: PLC0415
        from gobbler_core.providers import ProviderNotFoundError, ProviderRegistry  # noqa: PLC0415

        # Create provider if specified
        webpage_provider: WebPageProvider | None = None
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

        with ProgressTracker("Converting web page"):
            # Note: css_selector is not currently supported by the underlying converter
            # It uses the Gobbler service for extraction instead
            if css_selector and output_format != OutputFormat.JSON:
                print_warning("CSS selector option is not yet implemented in the webpage converter")

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
