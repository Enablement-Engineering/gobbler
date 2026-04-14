"""Batch processing commands for multiple content items."""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path
from typing import Annotated, Any

import typer

from gobbler_cli.knowledge import (
    PREVIEW_ITEM_LIMIT,
    SECONDS_PER_AUDIO_FILE,
    SECONDS_PER_DOCUMENT,
    SECONDS_PER_WEBPAGE,
    SECONDS_PER_YOUTUBE_VIDEO,
    format_duration,
)
from gobbler_cli.output import print_error, print_info, print_success
from gobbler_cli.progress import create_progress


def _write_json_line(data: dict[str, Any]) -> None:
    """Write a JSON line to stdout for streaming output."""
    sys.stdout.write(json.dumps(data, ensure_ascii=False) + "\n")
    sys.stdout.flush()


def _scan_existing_video_ids(directory: Path) -> set[str]:
    """Scan directory for existing video IDs from markdown frontmatter.

    Args:
        directory: Directory to scan for .md files

    Returns:
        Set of video IDs found in frontmatter
    """
    import re

    video_ids: set[str] = set()
    if not directory.exists():
        return video_ids

    # Pattern to match video_id in YAML frontmatter
    video_id_pattern = re.compile(r"^video_id:\s*['\"]?([a-zA-Z0-9_-]+)['\"]?\s*$", re.MULTILINE)

    for md_file in directory.glob("*.md"):
        try:
            # Read just the first 2KB to get frontmatter (efficient)
            content = md_file.read_text(encoding="utf-8")[:2048]
            # Check if it has frontmatter
            if content.startswith("---"):
                # Find end of frontmatter
                end_idx = content.find("---", 3)
                if end_idx > 0:
                    frontmatter = content[3:end_idx]
                    match = video_id_pattern.search(frontmatter)
                    if match:
                        video_ids.add(match.group(1))
        except Exception:  # noqa: S112 # nosec B112 - intentionally skip unreadable files
            continue

    return video_ids


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
    output_format: Annotated[
        str,
        typer.Option("--format", "-f", help="Output format (markdown/json)"),
    ] = "markdown",
    json_output: Annotated[
        bool,
        typer.Option("--json", "-j", help="Output progress and results as JSON lines"),
    ] = False,
    dry_run: Annotated[
        bool,
        typer.Option("--dry-run", help="Preview what would be processed without converting"),
    ] = False,
) -> None:
    """Convert all videos in a YouTube playlist to markdown.

    Examples:
        gobbler batch youtube-playlist https://youtube.com/playlist?list=... -o ./transcripts
        gobbler batch youtube-playlist https://youtube.com/playlist?list=... -o ./out -c 5
        gobbler batch youtube-playlist https://youtube.com/playlist?list=... -o ./out --json
        gobbler batch youtube-playlist https://youtube.com/playlist?list=... -o ./out --dry-run
    """
    asyncio.run(
        _batch_youtube_playlist(
            url=url,
            output_dir=output_dir,
            language=language,
            timestamps=timestamps,
            concurrency=concurrency,
            output_format=output_format,
            json_output=json_output,
            dry_run=dry_run,
        )
    )


async def _batch_youtube_playlist(  # noqa: C901, PLR0912, PLR0915
    url: str,
    output_dir: Path,
    language: str,
    timestamps: bool,
    concurrency: int,
    output_format: str,
    json_output: bool = False,
    dry_run: bool = False,
) -> None:
    """Async implementation of YouTube playlist batch processing."""
    import time

    import yt_dlp

    from gobbler_core.converters.youtube import convert_youtube_to_markdown

    # Use json_output param or check output_format
    use_json = json_output or output_format == "json"
    start_time = time.time()

    try:
        # Create output directory (unless dry run)
        if not dry_run:
            output_dir.mkdir(parents=True, exist_ok=True)

        # Extract playlist videos using yt-dlp
        ydl_opts = {
            "quiet": True,
            "no_warnings": True,
            "extract_flat": True,
            "playlistend": 500,  # Max videos
            "socket_timeout": 30,  # Prevent hung connections
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)

            if not info or "entries" not in info:
                error_msg = "Invalid playlist URL or playlist is empty"
                if use_json:
                    _write_json_line({"success": False, "error": error_msg})
                else:
                    print_error(error_msg)
                raise typer.Exit(1)

            videos = []
            for entry in info["entries"]:
                if entry and "id" in entry:
                    videos.append(
                        {
                            "video_id": entry["id"],
                            "url": f"https://youtube.com/watch?v={entry['id']}",
                            "title": entry.get("title", f"video_{entry['id']}"),
                        }
                    )

        if not videos:
            error_msg = "No videos found in playlist"
            if use_json:
                _write_json_line({"success": False, "error": error_msg})
            else:
                print_error(error_msg)
            raise typer.Exit(1)

        # Scan existing video IDs from frontmatter (reliable skip detection)
        existing_video_ids = _scan_existing_video_ids(output_dir)

        # Handle dry run - show preview without processing
        if dry_run:
            # Check which videos would be processed vs skipped (by video ID)
            would_process = []
            would_skip = []
            for video in videos:
                if video["video_id"] in existing_video_ids:
                    would_skip.append({"video": video, "reason": "video_id_exists"})
                else:
                    would_process.append({"video": video})

            # Estimate time based on concurrency
            estimated_seconds = (len(would_process) * SECONDS_PER_YOUTUBE_VIDEO) // max(
                concurrency, 1
            )
            estimated_time = format_duration(estimated_seconds)

            if use_json:
                _write_json_line(
                    {
                        "type": "dry_run",
                        "total_videos": len(videos),
                        "would_process": len(would_process),
                        "would_skip": len(would_skip),
                        "output_dir": str(output_dir),
                        "output_dir_exists": output_dir.exists(),
                        "estimated_time": estimated_time,
                        "concurrency": concurrency,
                        "videos": [v["video"] for v in would_process],
                        "skipped": [v["video"] for v in would_skip],
                    }
                )
            else:
                from gobbler_cli.output import console

                console.print()
                console.print("[bold]Dry Run Preview[/bold]")
                console.print("═" * 50)
                console.print(f"Playlist:       {url}")
                exists_note = (
                    "[dim](exists)[/dim]" if output_dir.exists() else "[dim](will create)[/dim]"
                )
                console.print(f"Output:         {output_dir} {exists_note}")
                console.print(f"Total videos:   {len(videos)}")
                console.print(f"Would process:  [green]{len(would_process)}[/green]")
                console.print(f"Would skip:     [yellow]{len(would_skip)}[/yellow] (already exist)")
                console.print(f"Concurrency:    {concurrency}")
                console.print(f"Estimated time: ~{estimated_time}")
                console.print()
                if would_process:
                    console.print("[bold]Videos to process:[/bold]")
                    for i, item in enumerate(would_process[:PREVIEW_ITEM_LIMIT], 1):
                        console.print(f"  {i}. {item['video']['title']}")
                    if len(would_process) > PREVIEW_ITEM_LIMIT:
                        console.print(f"  ... and {len(would_process) - PREVIEW_ITEM_LIMIT} more")
                console.print()
            return

        if use_json:
            _write_json_line(
                {
                    "type": "batch_start",
                    "total": len(videos),
                    "concurrency": concurrency,
                    "output_dir": str(output_dir),
                }
            )
        else:
            print_info(f"Found {len(videos)} videos in playlist")

        # Process videos
        successful = 0
        failed = 0
        skipped = 0
        success_details: list[dict[str, Any]] = []
        failures: list[dict[str, Any]] = []

        semaphore = asyncio.Semaphore(concurrency)

        # Per-video timeout (seconds) - prevents a single hung video from blocking the batch
        per_video_timeout = 120

        async def process_video(
            video: dict[str, Any],
        ) -> tuple[dict[str, Any], bool, str, dict[str, Any] | None]:
            """Process a single video."""
            async with semaphore:
                # Skip if video ID already exists in directory (checked via frontmatter)
                if video["video_id"] in existing_video_ids:
                    return (video, True, "skipped", None)

                # Sanitize filename
                safe_title = "".join(
                    c for c in video["title"] if c.isalnum() or c in (" ", "-", "_")
                ).strip()
                safe_title = safe_title.replace(" ", "_") or f"video_{video['video_id']}"
                output_path = output_dir / f"{safe_title}.md"

                try:
                    # Run in executor with timeout since the underlying calls
                    # (yt-dlp metadata + transcript fetch) are synchronous and
                    # would block the event loop, making asyncio.wait_for ineffective
                    loop = asyncio.get_event_loop()

                    def _sync_convert():
                        import asyncio as _asyncio
                        return _asyncio.run(convert_youtube_to_markdown(
                            video_url=video["url"],
                            include_timestamps=timestamps,
                            language=language,
                        ))

                    markdown, metadata = await asyncio.wait_for(
                        loop.run_in_executor(None, _sync_convert),
                        timeout=per_video_timeout,
                    )

                    # Write output
                    output_path.write_text(markdown, encoding="utf-8")
                    return (video, True, "success", {"output_file": str(output_path), **metadata})

                except asyncio.TimeoutError:
                    return (video, False, f"Timed out after {per_video_timeout}s", None)
                except Exception as e:
                    return (video, False, str(e), None)

        # Create and run tasks
        tasks = [process_video(v) for v in videos]

        if use_json:
            for coro in asyncio.as_completed(tasks):
                video, success, message, metadata = await coro

                if success:
                    if message == "skipped":
                        skipped += 1
                        _write_json_line(
                            {
                                "type": "item_skipped",
                                "source": video["url"],
                                "title": video["title"],
                            }
                        )
                    else:
                        successful += 1
                        success_details.append(
                            {
                                "source": video["url"],
                                "output_file": metadata.get("output_file", "") if metadata else "",
                            }
                        )
                        _write_json_line(
                            {
                                "type": "item_success",
                                "source": video["url"],
                                "title": video["title"],
                            }
                        )
                else:
                    failed += 1
                    failures.append({"source": video["url"], "error": message})
                    _write_json_line(
                        {
                            "type": "item_error",
                            "source": video["url"],
                            "error": message,
                        }
                    )

            # Output final JSON summary
            processing_time = time.time() - start_time
            _write_json_line(
                {
                    "type": "batch_complete",
                    "success": failed == 0,
                    "total_items": len(videos),
                    "successful": successful,
                    "failed": failed,
                    "skipped": skipped,
                    "output_dir": str(output_dir),
                    "processing_time_seconds": processing_time,
                    "success_details": success_details,
                    "failures": failures,
                }
            )
        else:
            # Progress bar mode
            progress = create_progress()
            with progress:
                task = progress.add_task("Processing videos", total=len(videos))

                for coro in asyncio.as_completed(tasks):
                    video, success, message, metadata = await coro

                    if success:
                        if message == "skipped":
                            skipped += 1
                        else:
                            successful += 1
                    else:
                        failed += 1
                        print_error(f"Failed: {video['title']} - {message}")

                    progress.update(task, advance=1)

            print_success(f"Processed {successful} videos successfully")
            if skipped > 0:
                print_info(f"Skipped {skipped} existing files")
            if failed > 0:
                print_error(f"{failed} videos failed to process")
                raise typer.Exit(1)

    except typer.Exit:
        raise
    except Exception as e:
        if use_json:
            _write_json_line({"success": False, "error": str(e)})
        else:
            print_error(f"Failed to process YouTube playlist: {e}")
        raise typer.Exit(1) from None


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
        str | None,
        typer.Option(
            "--type",
            "-t",
            help="File type to process (audio/document/auto-detect if not specified)",
        ),
    ] = None,
    json_output: Annotated[
        bool,
        typer.Option("--json", "-j", help="Output progress and results as JSON lines"),
    ] = False,
    dry_run: Annotated[
        bool,
        typer.Option("--dry-run", help="Preview what would be processed without converting"),
    ] = False,
) -> None:
    """Batch convert files from a directory.

    Examples:
        gobbler batch directory ./recordings -o ./transcripts --pattern "*.mp3"
        gobbler batch directory ./docs -o ./markdown --pattern "*.pdf" --type document
        gobbler batch directory ./docs -o ./markdown --json
        gobbler batch directory ./docs -o ./markdown --dry-run
    """
    asyncio.run(
        _batch_directory(
            input_dir=input_dir,
            output_dir=output_dir,
            pattern=pattern,
            concurrency=concurrency,
            file_type=file_type,
            json_output=json_output,
            dry_run=dry_run,
        )
    )


async def _batch_directory(  # noqa: C901, PLR0912, PLR0915
    input_dir: Path,
    output_dir: Path,
    pattern: str,
    concurrency: int,
    file_type: str | None,
    json_output: bool = False,
    dry_run: bool = False,
) -> None:
    """Async implementation of directory batch processing."""
    try:
        # Validate input directory
        if not input_dir.exists() or not input_dir.is_dir():
            error_msg = f"Input directory not found: {input_dir}"
            if json_output:
                _write_json_line(
                    {
                        "success": False,
                        "error": error_msg,
                        "error_code": "DIRECTORY_NOT_FOUND",
                    }
                )
            raise ValueError(error_msg)

        # Create output directory (unless dry run)
        if not dry_run:
            output_dir.mkdir(parents=True, exist_ok=True)

        # Find matching files
        files = list(input_dir.glob(pattern))
        if not files:
            if json_output:
                _write_json_line(
                    {
                        "type": "batch_complete",
                        "success": True,
                        "summary": {"total": 0, "successful": 0, "failed": 0, "skipped": 0},
                        "message": f"No files matching pattern '{pattern}' found",
                    }
                )
            else:
                print_info(f"No files matching pattern '{pattern}' found in {input_dir}")
            return

        # Handle dry run
        if dry_run:
            would_process = []
            would_skip = []
            for file_path in files:
                detected_type = file_type or _detect_file_type(file_path)
                output_path = output_dir / f"{file_path.stem}.md"
                if output_path.exists():
                    would_skip.append(
                        {"file": str(file_path), "output": str(output_path), "type": detected_type}
                    )
                elif detected_type in ("audio", "document"):
                    would_process.append(
                        {"file": str(file_path), "output": str(output_path), "type": detected_type}
                    )
                else:
                    would_skip.append(
                        {
                            "file": str(file_path),
                            "output": str(output_path),
                            "type": detected_type,
                            "reason": "unknown_type",
                        }
                    )

            # Estimate time based on file types and concurrency
            audio_count = sum(1 for f in would_process if f["type"] == "audio")
            doc_count = sum(1 for f in would_process if f["type"] == "document")
            estimated_seconds = (
                (audio_count * SECONDS_PER_AUDIO_FILE) + (doc_count * SECONDS_PER_DOCUMENT)
            ) // max(concurrency, 1)
            estimated_time = format_duration(estimated_seconds)

            if json_output:
                _write_json_line(
                    {
                        "type": "dry_run",
                        "total_files": len(files),
                        "would_process": len(would_process),
                        "would_skip": len(would_skip),
                        "input_dir": str(input_dir),
                        "output_dir": str(output_dir),
                        "pattern": pattern,
                        "estimated_time": estimated_time,
                        "files": would_process,
                        "skipped": would_skip,
                    }
                )
            else:
                from gobbler_cli.output import console

                console.print()
                console.print("[bold]Dry Run Preview[/bold]")
                console.print("═" * 50)
                console.print(f"Input:          {input_dir}")
                console.print(f"Pattern:        {pattern}")
                exists_note = (
                    "[dim](exists)[/dim]" if output_dir.exists() else "[dim](will create)[/dim]"
                )
                console.print(f"Output:         {output_dir} {exists_note}")
                console.print(f"Total files:    {len(files)}")
                console.print(f"Would process:  [green]{len(would_process)}[/green]")
                console.print(f"Would skip:     [yellow]{len(would_skip)}[/yellow]")
                console.print(f"Estimated time: ~{estimated_time}")
                console.print()
                if would_process:
                    console.print("[bold]Files to process:[/bold]")
                    for i, item in enumerate(would_process[:PREVIEW_ITEM_LIMIT], 1):
                        console.print(f"  {i}. {item['file']} → {item['output']}")
                    if len(would_process) > PREVIEW_ITEM_LIMIT:
                        console.print(f"  ... and {len(would_process) - PREVIEW_ITEM_LIMIT} more")
                console.print()
            return

        if json_output:
            _write_json_line(
                {
                    "type": "batch_start",
                    "total": len(files),
                    "pattern": pattern,
                    "input_dir": str(input_dir),
                    "output_dir": str(output_dir),
                }
            )
        else:
            print_info(f"Found {len(files)} files to process")

        # Track results
        successful = 0
        failed = 0
        skipped = 0

        # Create semaphore for concurrency control
        semaphore = asyncio.Semaphore(concurrency)

        async def process_file(
            file_path: Path,
        ) -> tuple[Path, bool, str, dict[str, Any] | None]:
            """Process a single file. Returns (file_path, success, status, metadata)."""
            async with semaphore:
                # Determine file type
                detected_type = file_type or _detect_file_type(file_path)

                # Generate output filename
                output_path = output_dir / f"{file_path.stem}.md"

                # Skip unknown types
                if detected_type not in ("audio", "document"):
                    return (file_path, True, "skipped_unknown", None)

                try:
                    # Convert based on type
                    if detected_type == "audio":
                        from gobbler_core.converters.audio import (
                            convert_audio_to_markdown,
                        )

                        result, metadata = await convert_audio_to_markdown(str(file_path))
                    else:  # document
                        from gobbler_core.converters.document import (
                            convert_document_to_markdown,
                        )

                        result, metadata = await convert_document_to_markdown(str(file_path))

                    # Write output
                    output_path.write_text(result, encoding="utf-8")
                    return (file_path, True, "success", {"output": str(output_path), **metadata})

                except Exception as e:
                    return (file_path, False, str(e), None)

        # Create tasks for all files
        tasks = [process_file(f) for f in files]

        if json_output:
            # JSON output mode - stream results as they complete
            for coro in asyncio.as_completed(tasks):
                file_path, success, status, metadata = await coro

                if status == "skipped_unknown":
                    skipped += 1
                    _write_json_line(
                        {
                            "type": "item_skipped",
                            "file": str(file_path),
                            "reason": "unknown_type",
                        }
                    )
                elif success:
                    successful += 1
                    _write_json_line(
                        {
                            "type": "item_success",
                            "file": str(file_path),
                            "output": metadata.get("output") if metadata else None,
                            "metadata": metadata,
                        }
                    )
                else:
                    failed += 1
                    _write_json_line(
                        {
                            "type": "item_error",
                            "file": str(file_path),
                            "error": status,
                        }
                    )

            # Final summary
            _write_json_line(
                {
                    "type": "batch_complete",
                    "success": failed == 0,
                    "summary": {
                        "total": len(files),
                        "successful": successful,
                        "failed": failed,
                        "skipped": skipped,
                    },
                }
            )
        else:
            # Process files with progress bar
            progress = create_progress()
            with progress:
                task = progress.add_task("Processing files", total=len(files))

                for coro in asyncio.as_completed(tasks):
                    file_path, success, status, metadata = await coro

                    if status == "skipped_unknown":
                        skipped += 1
                    elif success:
                        successful += 1
                    else:
                        failed += 1

                    progress.update(task, advance=1)

            # Print summary
            print_success(f"Processed {successful} files successfully (concurrency: {concurrency})")
            if failed > 0:
                print_error(f"{failed} files failed to process")
            if skipped > 0:
                print_info(f"{skipped} files skipped (unknown type)")

    except Exception as e:
        if json_output:
            _write_json_line(
                {
                    "success": False,
                    "error": str(e),
                    "error_code": "BATCH_PROCESSING_ERROR",
                }
            )
        else:
            print_error(f"Failed to process directory: {e}")
        raise typer.Exit(1) from None


def _detect_file_type(file_path: Path) -> str:
    """Detect file type based on extension.

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
    if ext in document_extensions:
        return "document"
    return "unknown"


@app.command()
def webpages(
    input_file: Annotated[
        Path | None,
        typer.Argument(help="File containing URLs (one per line). Use - or omit for stdin."),
    ] = None,
    output_dir: Annotated[
        Path,
        typer.Option("--output-dir", "-o", help="Output directory for converted files"),
    ] = ...,
    concurrency: Annotated[
        int,
        typer.Option(
            "--concurrency",
            "-c",
            help="Number of concurrent conversions (max 10)",
            min=1,
            max=10,
        ),
    ] = 3,
    timeout: Annotated[
        int,
        typer.Option("--timeout", "-t", help="Timeout per page in seconds"),
    ] = 30,
    selector: Annotated[
        str | None,
        typer.Option("--selector", "-s", help="CSS selector to extract specific content"),
    ] = None,
    skip_existing: Annotated[
        bool,
        typer.Option(
            "--skip-existing/--no-skip-existing", help="Skip URLs that already have output files"
        ),
    ] = True,
    queue: Annotated[
        bool,
        typer.Option("--queue", help="Queue the batch job instead of running inline"),
    ] = False,
    json_output: Annotated[
        bool,
        typer.Option("--json", "-j", help="Output progress and results as JSON lines"),
    ] = False,
    dry_run: Annotated[
        bool,
        typer.Option("--dry-run", help="Preview what would be processed without converting"),
    ] = False,
) -> None:
    """Batch convert web pages to markdown.

    Reads URLs from a file (one per line) or stdin, and converts each to markdown.
    Lines starting with # are treated as comments and skipped.

    Examples:
        gobbler batch webpages urls.txt -o ./output
        cat urls.txt | gobbler batch webpages -o ./output
        gobbler batch webpages urls.txt -o ./out --concurrency 5 --timeout 60
        gobbler batch webpages urls.txt -o ./out --queue
        gobbler batch webpages urls.txt -o ./out --json
        gobbler batch webpages urls.txt -o ./out --dry-run
    """
    if queue:
        _queue_batch_webpages(
            input_file=input_file,
            output_dir=output_dir,
            concurrency=concurrency,
            timeout=timeout,
            selector=selector,
            skip_existing=skip_existing,
        )
    else:
        asyncio.run(
            _batch_webpages(
                input_file=input_file,
                output_dir=output_dir,
                concurrency=concurrency,
                timeout=timeout,
                selector=selector,
                skip_existing=skip_existing,
                json_output=json_output,
                dry_run=dry_run,
            )
        )


def _queue_batch_webpages(
    input_file: Path | None,
    output_dir: Path,
    concurrency: int,
    timeout: int,
    selector: str | None,
    skip_existing: bool,
) -> None:
    """Queue the batch webpages job for background processing."""
    from gobbler_queue.manager import JobManager
    from gobbler_queue.models import JobType

    # Read URLs from file or stdin
    urls = _read_urls(input_file)
    if not urls:
        print_error("No valid URLs found in input")
        raise typer.Exit(1)

    # Build command for the worker to execute
    # Store URLs in args since they come from stdin/file
    args = {
        "urls": urls,
        "output_dir": str(output_dir),
        "concurrency": concurrency,
        "timeout": timeout,
        "selector": selector,
        "skip_existing": skip_existing,
    }

    # Build a representative command string
    command = (
        f"gobbler batch webpages --output-dir {output_dir} "
        f"--concurrency {concurrency} --timeout {timeout}"
    )
    if selector:
        command += f" --selector {selector}"
    if not skip_existing:
        command += " --no-skip-existing"

    try:
        manager = JobManager()
        job = manager.create_job(
            job_type=JobType.BATCH_WEBPAGE,
            command=command,
            args=args,
        )
        print_success(f"Queued batch webpage job: {job.id}")
        print_info(f"Processing {len(urls)} URLs")
        print_info("Use 'gobbler queue status' to check progress")
    except Exception as e:
        print_error(f"Failed to queue job: {e}")
        raise typer.Exit(1) from None


def _read_urls(input_file: Path | None) -> list[str]:
    """Read URLs from file or stdin.

    Args:
        input_file: Path to file containing URLs, or None for stdin

    Returns:
        List of valid URLs (empty lines and comments removed)
    """
    import sys

    lines: list[str] = []

    if input_file is None or str(input_file) == "-":
        # Read from stdin
        if sys.stdin.isatty():
            print_error("No input file specified and stdin is empty")
            return []
        lines = sys.stdin.read().splitlines()
    else:
        # Read from file
        if not input_file.exists():
            print_error(f"Input file not found: {input_file}")
            return []
        lines = input_file.read_text(encoding="utf-8").splitlines()

    # Filter out empty lines and comments
    urls = []
    for raw_line in lines:
        stripped = raw_line.strip()
        if stripped and not stripped.startswith("#"):
            urls.append(stripped)

    return urls


def _sanitize_url_to_filename(url: str) -> str:
    """Convert a URL to a safe filename.

    Args:
        url: The URL to sanitize

    Returns:
        A safe filename based on the URL's domain and path
    """
    import re
    from urllib.parse import urlparse

    parsed = urlparse(url)

    # Get domain without www prefix
    domain = parsed.netloc.lower()
    if domain.startswith("www."):
        domain = domain[4:]

    # Get path, remove leading/trailing slashes
    path = parsed.path.strip("/")

    # Combine domain and path
    name = f"{domain}_{path}" if path else domain

    # Replace unsafe characters with underscores
    name = re.sub(r"[^\w\-.]", "_", name)

    # Collapse multiple underscores
    name = re.sub(r"_+", "_", name)

    # Truncate if too long (keep extension room)
    max_filename_length = 200
    if len(name) > max_filename_length:
        name = name[:max_filename_length]

    return name


async def _batch_webpages(  # noqa: C901, PLR0912, PLR0915
    input_file: Path | None,
    output_dir: Path,
    concurrency: int,
    timeout: int,
    selector: str | None,  # noqa: ARG001 - Reserved for future CSS selector support
    skip_existing: bool,
    json_output: bool = False,
    dry_run: bool = False,
) -> None:
    """Async implementation of batch webpage processing."""
    from gobbler_core.converters.webpage import convert_webpage_to_markdown

    try:
        # Read URLs
        urls = _read_urls(input_file)
        if not urls:
            if json_output:
                _write_json_line(
                    {
                        "success": False,
                        "error": "No valid URLs found in input",
                        "error_code": "NO_URLS_FOUND",
                    }
                )
            else:
                print_error("No valid URLs found in input")
            raise typer.Exit(1)

        # Handle dry run
        if dry_run:
            would_process = []
            would_skip = []
            for url in urls:
                filename = _sanitize_url_to_filename(url) + ".md"
                output_path = output_dir / filename
                if skip_existing and output_path.exists():
                    would_skip.append({"url": url, "output": str(output_path), "reason": "exists"})
                else:
                    would_process.append({"url": url, "output": str(output_path)})

            # Estimate time based on concurrency
            estimated_seconds = (len(would_process) * SECONDS_PER_WEBPAGE) // max(concurrency, 1)
            estimated_time = format_duration(estimated_seconds)

            if json_output:
                _write_json_line(
                    {
                        "type": "dry_run",
                        "total_urls": len(urls),
                        "would_process": len(would_process),
                        "would_skip": len(would_skip),
                        "output_dir": str(output_dir),
                        "output_dir_exists": output_dir.exists(),
                        "concurrency": concurrency,
                        "estimated_time": estimated_time,
                        "urls": would_process,
                        "skipped": would_skip,
                    }
                )
            else:
                from gobbler_cli.output import console

                console.print()
                console.print("[bold]Dry Run Preview[/bold]")
                console.print("═" * 50)
                console.print(f"Input:          {input_file or 'stdin'}")
                exists_note = (
                    "[dim](exists)[/dim]" if output_dir.exists() else "[dim](will create)[/dim]"
                )
                console.print(f"Output:         {output_dir} {exists_note}")
                console.print(f"Total URLs:     {len(urls)}")
                console.print(f"Would process:  [green]{len(would_process)}[/green]")
                console.print(f"Would skip:     [yellow]{len(would_skip)}[/yellow] (already exist)")
                console.print(f"Concurrency:    {concurrency}")
                console.print(f"Estimated time: ~{estimated_time}")
                console.print()
                if would_process:
                    console.print("[bold]URLs to process:[/bold]")
                    for i, item in enumerate(would_process[:PREVIEW_ITEM_LIMIT], 1):
                        console.print(f"  {i}. {item['url']}")
                    if len(would_process) > PREVIEW_ITEM_LIMIT:
                        console.print(f"  ... and {len(would_process) - PREVIEW_ITEM_LIMIT} more")
                console.print()
            return

        # Create output directory
        output_dir.mkdir(parents=True, exist_ok=True)

        if json_output:
            _write_json_line(
                {
                    "type": "batch_start",
                    "total": len(urls),
                    "concurrency": concurrency,
                    "output_dir": str(output_dir),
                }
            )
        else:
            print_info(f"Processing {len(urls)} URLs with concurrency {concurrency}")

        # Track results
        successful = 0
        failed = 0
        skipped = 0
        results: list[dict[str, Any]] = []

        # Create semaphore for concurrency control
        semaphore = asyncio.Semaphore(concurrency)

        async def process_url(url: str) -> tuple[str, bool, str, dict[str, Any] | None]:
            """Process a single URL. Returns (url, success, message, metadata)."""
            async with semaphore:
                # Generate output filename
                filename = _sanitize_url_to_filename(url) + ".md"
                output_path = output_dir / filename

                # Check if already exists
                if skip_existing and output_path.exists():
                    return (url, True, "skipped", None)

                try:
                    # Convert webpage to markdown
                    markdown_content, metadata = await convert_webpage_to_markdown(
                        url=url,
                        timeout=timeout,
                    )

                    # Write output
                    output_path.write_text(markdown_content, encoding="utf-8")
                except Exception as e:
                    return (url, False, str(e), None)
                else:
                    return (url, True, "success", metadata)

        if json_output:
            # JSON output mode - no progress bar, stream JSON lines
            tasks = [process_url(url) for url in urls]

            for coro in asyncio.as_completed(tasks):
                url, success, message, metadata = await coro

                if success:
                    if message == "skipped":
                        skipped += 1
                        _write_json_line(
                            {
                                "type": "item_skipped",
                                "url": url,
                                "reason": "already_exists",
                            }
                        )
                    else:
                        successful += 1
                        _write_json_line(
                            {
                                "type": "item_success",
                                "url": url,
                                "metadata": metadata,
                            }
                        )
                        results.append({"url": url, "success": True, "metadata": metadata})
                else:
                    failed += 1
                    _write_json_line(
                        {
                            "type": "item_error",
                            "url": url,
                            "error": message,
                        }
                    )
                    results.append({"url": url, "success": False, "error": message})

            # Final summary
            _write_json_line(
                {
                    "type": "batch_complete",
                    "success": failed == 0,
                    "summary": {
                        "total": len(urls),
                        "successful": successful,
                        "failed": failed,
                        "skipped": skipped,
                    },
                }
            )
        else:
            # Normal progress bar mode
            progress = create_progress()
            with progress:
                task = progress.add_task("Converting webpages", total=len(urls))

                # Create tasks for all URLs
                tasks = [process_url(url) for url in urls]

                # Process with asyncio.as_completed for real-time progress
                for coro in asyncio.as_completed(tasks):
                    url, success, message, metadata = await coro

                    if success:
                        if message == "skipped":
                            skipped += 1
                        else:
                            successful += 1
                    else:
                        failed += 1
                        print_error(f"Failed: {url} - {message}")

                    progress.update(task, advance=1)

            # Print summary
            print_success(f"Converted {successful} webpages successfully")
            if skipped > 0:
                print_info(f"Skipped {skipped} existing files")
            if failed > 0:
                print_error(f"{failed} webpages failed to convert")
                raise typer.Exit(1)

    except typer.Exit:
        raise
    except Exception as e:
        if json_output:
            _write_json_line(
                {
                    "success": False,
                    "error": str(e),
                    "error_code": "BATCH_PROCESSING_ERROR",
                }
            )
        else:
            print_error(f"Failed to process webpages: {e}")
        raise typer.Exit(1) from None
