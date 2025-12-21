"""Batch processing commands for multiple content items."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Optional

import typer
from typing_extensions import Annotated

from gobbler_cli.output import print_error, print_info, print_success
from gobbler_cli.progress import create_progress

app = typer.Typer(help="Batch processing operations")


@app.command()
def youtube_playlist(
    url: Annotated[str, typer.Argument(help="YouTube playlist URL")],
    output_dir: Annotated[
        Path,
        typer.Option("--output", "-o", help="Output directory for transcripts"),
    ],
    language: Annotated[
        str,
        typer.Option("--language", "-l", help="Preferred transcript language"),
    ] = "en",
    timestamps: Annotated[
        bool,
        typer.Option("--timestamps/--no-timestamps", help="Include timestamps in output"),
    ] = False,
    concurrency: Annotated[
        int,
        typer.Option("--concurrency", "-c", help="Number of concurrent conversions"),
    ] = 3,
    format: Annotated[
        str,
        typer.Option("--format", "-f", help="Output format (markdown/json)"),
    ] = "markdown",
) -> None:
    """
    Convert all videos in a YouTube playlist to markdown.

    Examples:
        gobbler batch youtube-playlist https://youtube.com/playlist?list=... -o ./transcripts
        gobbler batch youtube-playlist https://youtube.com/playlist?list=... -o ./out --concurrency 5
    """
    asyncio.run(
        _batch_youtube_playlist(
            url=url,
            output_dir=output_dir,
            language=language,
            timestamps=timestamps,
            concurrency=concurrency,
            format=format,
        )
    )


async def _batch_youtube_playlist(
    url: str,
    output_dir: Path,
    language: str,
    timestamps: bool,
    concurrency: int,
    format: str,
) -> None:
    """Async implementation of YouTube playlist batch processing."""
    try:
        # Create output directory
        output_dir.mkdir(parents=True, exist_ok=True)

        # TODO: Implement playlist extraction and batch processing
        # This will require integration with the batch processing system
        # For now, provide a placeholder implementation
        print_info(
            f"Batch processing YouTube playlist: {url}\n"
            f"Output directory: {output_dir}\n"
            f"Concurrency: {concurrency}"
        )

        # Import batch processing utilities when implemented
        # from gobbler_core.batch import process_youtube_playlist
        # results = await process_youtube_playlist(...)

        print_error(
            "Batch processing not yet implemented. "
            "This requires integration with the daemon/API layer."
        )
        raise typer.Exit(1)

    except Exception as e:
        print_error(f"Failed to process YouTube playlist: {e}")
        raise typer.Exit(1)


@app.command()
def directory(
    input_dir: Annotated[Path, typer.Argument(help="Input directory containing files")],
    output_dir: Annotated[
        Path,
        typer.Option("--output", "-o", help="Output directory for converted files"),
    ],
    pattern: Annotated[
        str,
        typer.Option("--pattern", "-p", help="File pattern to match (e.g., '*.mp3', '*.pdf')"),
    ] = "*.*",
    concurrency: Annotated[
        int,
        typer.Option("--concurrency", "-c", help="Number of concurrent conversions"),
    ] = 3,
    file_type: Annotated[
        Optional[str],
        typer.Option(
            "--type",
            "-t",
            help="File type to process (audio/document/auto-detect if not specified)",
        ),
    ] = None,
) -> None:
    """
    Batch convert files from a directory.

    Examples:
        gobbler batch directory ./recordings -o ./transcripts --pattern "*.mp3"
        gobbler batch directory ./docs -o ./markdown --pattern "*.pdf" --type document
    """
    asyncio.run(
        _batch_directory(
            input_dir=input_dir,
            output_dir=output_dir,
            pattern=pattern,
            concurrency=concurrency,
            file_type=file_type,
        )
    )


async def _batch_directory(
    input_dir: Path,
    output_dir: Path,
    pattern: str,
    concurrency: int,
    file_type: Optional[str],
) -> None:
    """Async implementation of directory batch processing."""
    try:
        # Validate input directory
        if not input_dir.exists() or not input_dir.is_dir():
            raise ValueError(f"Input directory not found: {input_dir}")

        # Create output directory
        output_dir.mkdir(parents=True, exist_ok=True)

        # Find matching files
        files = list(input_dir.glob(pattern))
        if not files:
            print_info(f"No files matching pattern '{pattern}' found in {input_dir}")
            return

        print_info(f"Found {len(files)} files to process")

        # Process files with progress bar
        progress = create_progress()
        with progress:
            task = progress.add_task("Processing files", total=len(files))

            successful = 0
            failed = 0

            for file_path in files:
                try:
                    # Determine file type
                    detected_type = file_type or _detect_file_type(file_path)

                    # Generate output filename
                    output_path = output_dir / f"{file_path.stem}.md"

                    # Convert based on type
                    if detected_type == "audio":
                        from gobbler_core.converters.audio import transcribe_audio

                        result = await transcribe_audio(str(file_path))
                    elif detected_type == "document":
                        from gobbler_core.converters.document import convert_document

                        result = await convert_document(str(file_path))
                    else:
                        print_info(f"Skipping unknown file type: {file_path}")
                        progress.update(task, advance=1)
                        continue

                    # Write output
                    output_path.write_text(result, encoding="utf-8")
                    successful += 1

                except Exception as e:
                    print_error(f"Failed to process {file_path.name}: {e}")
                    failed += 1

                progress.update(task, advance=1)

        # Print summary
        print_success(f"Processed {successful} files successfully")
        if failed > 0:
            print_error(f"{failed} files failed to process")

    except Exception as e:
        print_error(f"Failed to process directory: {e}")
        raise typer.Exit(1)


def _detect_file_type(file_path: Path) -> str:
    """
    Detect file type based on extension.

    Args:
        file_path: Path to the file

    Returns:
        File type string (audio/document/unknown)
    """
    audio_extensions = {".mp3", ".wav", ".m4a", ".flac", ".ogg", ".wma", ".aac"}
    document_extensions = {".pdf", ".docx", ".doc", ".pptx", ".ppt", ".xlsx", ".xls"}

    ext = file_path.suffix.lower()

    if ext in audio_extensions:
        return "audio"
    elif ext in document_extensions:
        return "document"
    else:
        return "unknown"
