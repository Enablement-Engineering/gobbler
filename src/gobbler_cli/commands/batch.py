"""Batch processing commands for multiple content items."""

from __future__ import annotations

import asyncio
import json
import shlex
import sys
from collections import Counter
from pathlib import Path
from typing import Annotated, Any, cast
from urllib.parse import parse_qs, urlparse

import typer

from gobbler_cli.commands.convert import (
    WEBPAGE_INVALID_URL_CODE,
    WEBPAGE_INVALID_URL_MESSAGE,
    WEBPAGE_INVALID_URL_SUGGESTION,
    _is_valid_webpage_url,
    _safe_youtube_failure_source,
)
from gobbler_cli.knowledge import (
    PREVIEW_ITEM_LIMIT,
    SECONDS_PER_AUDIO_FILE,
    SECONDS_PER_DOCUMENT,
    SECONDS_PER_WEBPAGE,
    SECONDS_PER_YOUTUBE_VIDEO,
    format_duration,
)
from gobbler_cli.output import add_json_contract, print_error, print_info, print_success
from gobbler_cli.progress import create_progress
from gobbler_core.utils.redaction import REDACTED, redact_value

YOUTUBE_PLAYLIST_INVALID_URL_MESSAGE = (
    "Invalid YouTube playlist URL: expected an absolute http:// or https:// YouTube playlist URL."
)
YOUTUBE_PLAYLIST_INVALID_URL_CODE = "YOUTUBE_PLAYLIST_INVALID_URL"
YOUTUBE_PLAYLIST_INVALID_URL_SUGGESTION = (
    "Provide a YouTube playlist URL like https://youtube.com/playlist?list=PLAYLIST_ID."
)


def _write_json_line(data: dict[str, Any]) -> None:
    """Write a JSON line to stdout for streaming output."""
    sys.stdout.write(json.dumps(add_json_contract(data), ensure_ascii=False) + "\n")
    sys.stdout.flush()


def _write_batch_webpage_queue_error(
    error: str,
    error_code: str,
    category: str = "queue_submission",
) -> None:
    """Write a stable JSON error for queued batch webpage submissions."""
    _write_json_line(
        {
            "type": "queue_error",
            "success": False,
            "error_code": error_code,
            "error": error,
            "summary": _batch_summary(1, 0, 1, 0, outcomes=Counter({category: 1})),
        }
    )


OUTCOME_CATEGORIES = (
    "completed",
    "skipped",
    "invalid_input",
    "provider_service",
    "filesystem_output",
    "queue_submission",
)

RETRY_GUIDANCE = {
    "invalid_input": "Fix the invalid inputs, then rerun the batch.",
    "provider_service": (
        "Retry failed items after checking provider availability and configuration."
    ),
    "filesystem_output": "Check output permissions and free space, then retry failed items.",
    "queue_submission": "Check the queue database and worker, then submit the batch again.",
}


def _batch_summary(
    total: int,
    successful: int,
    failed: int,
    skipped: int,
    *,
    outcomes: Counter[str] | None = None,
) -> dict[str, Any]:
    """Return the stable, categorized summary shape for batch events."""
    categorized = Counter(outcomes or {})
    categorized["completed"] = successful
    categorized["skipped"] = skipped
    summary: dict[str, Any] = {
        "total": total,
        "successful": successful,
        "failed": failed,
        "skipped": skipped,
        "outcomes": {category: categorized[category] for category in OUTCOME_CATEGORIES},
    }
    summary["retry_guidance"] = [
        {"category": category, "suggestion": RETRY_GUIDANCE[category]}
        for category in RETRY_GUIDANCE
        if categorized[category]
    ]
    return summary


def _failure_category(error: Exception) -> str:
    """Classify a conversion exception without exposing its message or source."""
    return "filesystem_output" if isinstance(error, OSError) else "provider_service"


def _safe_batch_webpage_failure_source(url: str) -> str:
    """Sanitize batch sources while preserving ordinary public URLs."""
    if not any(marker in url for marker in ("@", "?", "#")):
        return url
    try:
        parsed = urlparse(url)
        if parsed.scheme and parsed.hostname:
            return f"{parsed.scheme}://{parsed.hostname}"
    except ValueError:
        pass
    return REDACTED


def _safe_batch_webpage_error(message: str, url: str) -> str:
    """Remove the submitted URL before redacting provider diagnostic text."""
    return str(redact_value(message.replace(url, _safe_batch_webpage_failure_source(url))))


def _print_categorized_summary(summary: dict[str, Any]) -> None:
    """Print stable outcome category counts and safe retry guidance."""
    print_info("Batch summary:")
    outcomes = summary["outcomes"]
    for category in OUTCOME_CATEGORIES:
        print_info(f"  {category}: {outcomes[category]}")
    for guidance in summary["retry_guidance"]:
        print_info(f"Retry ({guidance['category']}): {guidance['suggestion']}")


def _invalid_input_summary(total: int) -> dict[str, Any]:
    """Return a terminal summary for a batch rejected before dispatch."""
    return _batch_summary(
        total,
        successful=0,
        failed=total,
        skipped=0,
        outcomes=Counter({"invalid_input": total}),
    )


def _directory_output_paths(files: list[Path], output_dir: Path) -> dict[Path, Path]:
    """Return deterministic output paths for directory batch inputs.

    Files that do not collide keep the historical ``<stem>.md`` name. When two
    or more selected inputs would use the same output name, include the source
    extension in the output name, e.g. ``report.pdf.md`` and ``report.docx.md``.
    """
    output_names = [f"{file_path.stem}.md" for file_path in files]
    output_name_counts = Counter(name.casefold() for name in output_names)
    colliding_names = {name for name, count in output_name_counts.items() if count > 1}

    paths_by_file: dict[Path, Path] = {}
    used_paths: set[str] = set()
    for file_path in sorted(files, key=str):
        output_name = (
            f"{file_path.name}.md"
            if f"{file_path.stem}.md".casefold() in colliding_names
            else f"{file_path.stem}.md"
        )
        output_path = output_dir / output_name
        output_path_key = output_path.as_posix().casefold()

        suffix = 2
        while output_path_key in used_paths:
            output_path = output_dir / f"{Path(output_name).stem}-{suffix}.md"
            output_path_key = output_path.as_posix().casefold()
            suffix += 1

        paths_by_file[file_path] = output_path
        used_paths.add(output_path_key)

    return paths_by_file


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


def _is_valid_youtube_playlist_url(url: str) -> bool:
    """Return whether a URL is a structurally valid YouTube playlist URL.

    Args:
        url: User-provided YouTube playlist URL.

    Returns:
        True when the URL is absolute HTTP(S), targets YouTube, and includes a playlist ID.
    """
    if not _is_valid_webpage_url(url):
        return False

    parsed = urlparse(url)
    hostname = (parsed.hostname or "").removeprefix("www.").lower()
    if hostname not in {"youtube.com", "m.youtube.com", "music.youtube.com"}:
        return False

    playlist_ids = parse_qs(parsed.query).get("list", [])
    return any(playlist_id.strip() for playlist_id in playlist_ids)


def _safe_youtube_playlist_failure_source(url: str) -> str:
    """Return a minimal authority-only identity for invalid playlist diagnostics."""
    if url.startswith("//"):
        return REDACTED

    safe_source = _safe_youtube_failure_source(url)
    if safe_source == REDACTED or "://" not in safe_source:
        return safe_source

    try:
        scheme, authority = safe_source.split("://", 1)
        authority = authority.rsplit("@", 1)[-1]
        parsed = urlparse(f"{scheme}://{authority}")
        hostname = parsed.hostname
        port = parsed.port
        if not scheme or not hostname:
            return REDACTED
    except Exception:
        return REDACTED
    else:
        host = f"[{hostname}]" if ":" in hostname else hostname
        safe_authority = f"{host}:{port}" if port is not None else host
        return f"{scheme}://{safe_authority}"


def _write_invalid_youtube_playlist_url_error(url: str, json_output: bool) -> None:
    """Write stable invalid-input diagnostics for a YouTube playlist URL."""
    if json_output:
        safe_source = _safe_youtube_playlist_failure_source(url)
        _write_json_line(
            {
                "type": "invalid_input",
                "success": False,
                "error_code": YOUTUBE_PLAYLIST_INVALID_URL_CODE,
                "error": YOUTUBE_PLAYLIST_INVALID_URL_MESSAGE,
                "url": safe_source,
                "source": safe_source,
                "suggestion": YOUTUBE_PLAYLIST_INVALID_URL_SUGGESTION,
            }
        )
        _write_json_line(
            {
                "type": "batch_complete",
                "success": False,
                "summary": _invalid_input_summary(1),
            }
        )
        return

    print_error(f"{YOUTUBE_PLAYLIST_INVALID_URL_MESSAGE} {YOUTUBE_PLAYLIST_INVALID_URL_SUGGESTION}")
    _print_categorized_summary(_invalid_input_summary(1))


def _validate_youtube_playlist_url(url: str, json_output: bool) -> None:
    """Reject invalid YouTube playlist URLs before extractor dispatch."""
    if _is_valid_youtube_playlist_url(url):
        return

    _write_invalid_youtube_playlist_url_error(url, json_output)
    raise typer.Exit(1)


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

    # Use json_output param or check output_format
    use_json = json_output or output_format == "json"
    start_time = time.time()

    try:
        _validate_youtube_playlist_url(url, use_json)

        import yt_dlp

        from gobbler_core.converters.youtube import convert_youtube_to_markdown

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
                        "summary": _batch_summary(len(videos), 0, 0, len(would_skip)),
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
        outcomes: Counter[str] = Counter()

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

                    def _sync_convert() -> tuple[str, dict[str, Any]]:
                        import asyncio as _asyncio

                        return _asyncio.run(
                            convert_youtube_to_markdown(
                                video_url=video["url"],
                                include_timestamps=timestamps,
                                language=language,
                            )
                        )

                    markdown, metadata = await asyncio.wait_for(
                        loop.run_in_executor(None, _sync_convert),
                        timeout=per_video_timeout,
                    )

                    # Write output
                    output_path.write_text(markdown, encoding="utf-8")
                    return (video, True, "success", {"output_file": str(output_path), **metadata})

                except TimeoutError:
                    outcomes["provider_service"] += 1
                    return (video, False, f"Timed out after {per_video_timeout}s", None)
                except Exception as e:
                    outcomes[_failure_category(e)] += 1
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
                    "summary": _batch_summary(
                        len(videos), successful, failed, skipped, outcomes=outcomes
                    ),
                    "output_dir": str(output_dir),
                    "processing_time_seconds": processing_time,
                    "success_details": success_details,
                    "failures": failures,
                }
            )
            if failed > 0:
                raise typer.Exit(1)
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
            _print_categorized_summary(
                _batch_summary(len(videos), successful, failed, skipped, outcomes=outcomes)
            )
            if failed > 0:
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
                raise typer.Exit(1)
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
                        "summary": _batch_summary(0, 0, 0, 0),
                        "message": f"No files matching pattern '{pattern}' found",
                    }
                )
            else:
                print_info(f"No files matching pattern '{pattern}' found in {input_dir}")
            return

        convertible_files = [
            file_path
            for file_path in files
            if (file_type or _detect_file_type(file_path)) in ("audio", "document")
        ]
        output_paths = _directory_output_paths(convertible_files, output_dir)

        # Handle dry run
        if dry_run:
            would_process = []
            would_skip = []
            for file_path in files:
                detected_type = file_type or _detect_file_type(file_path)
                output_path = output_paths.get(file_path, output_dir / f"{file_path.stem}.md")
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
                        "summary": _batch_summary(len(files), 0, 0, len(would_skip)),
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
        outcomes: Counter[str] = Counter()

        # Create semaphore for concurrency control
        semaphore = asyncio.Semaphore(concurrency)

        async def process_file(
            file_path: Path,
        ) -> tuple[Path, bool, str, dict[str, Any] | None]:
            """Process a single file. Returns (file_path, success, status, metadata)."""
            async with semaphore:
                # Determine file type
                detected_type = file_type or _detect_file_type(file_path)

                # Skip unknown types
                if detected_type not in ("audio", "document"):
                    return (file_path, True, "skipped_unknown", None)

                # Generate output filename
                output_path = output_paths[file_path]

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
                    outcomes[_failure_category(e)] += 1
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
                    "summary": _batch_summary(
                        len(files), successful, failed, skipped, outcomes=outcomes
                    ),
                }
            )
            if failed > 0:
                raise typer.Exit(1)
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
            _print_categorized_summary(
                _batch_summary(len(files), successful, failed, skipped, outcomes=outcomes)
            )
            if failed > 0:
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
    ] = cast("Path", ...),  # noqa: B008
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
    use_proxy: Annotated[
        bool,
        typer.Option(
            "--proxy/--no-proxy",
            help="Use configured Crawl4AI webpage proxy settings",
        ),
    ] = True,
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
        gobbler batch webpages urls.txt -o ./out --no-proxy
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
            use_proxy=use_proxy,
            skip_existing=skip_existing,
            json_output=json_output,
        )
    else:
        asyncio.run(
            _batch_webpages(
                input_file=input_file,
                output_dir=output_dir,
                concurrency=concurrency,
                timeout=timeout,
                selector=selector,
                use_proxy=use_proxy,
                skip_existing=skip_existing,
                json_output=json_output,
                dry_run=dry_run,
            )
        )


def _queue_batch_webpage_inputs(
    input_file: Path | None,
    output_dir: Path,
    json_output: bool,
) -> tuple[Path, Path, list[str], list[Path]]:
    """Validate and prepare durable queued batch webpage inputs."""
    if input_file is None or str(input_file) == "-":
        message = "Queueing batch webpages requires an input file path; stdin is supported inline."
        if json_output:
            _write_batch_webpage_queue_error(
                message, "BATCH_WEBPAGE_QUEUE_REQUIRES_FILE", "invalid_input"
            )
        else:
            print_error(message)
        raise typer.Exit(1)

    queue_input_file = input_file.expanduser().resolve()
    queue_output_dir = output_dir.expanduser().resolve()

    if not queue_input_file.exists():
        message = "Input file not found."
        if json_output:
            _write_batch_webpage_queue_error(
                message, "BATCH_WEBPAGE_INPUT_FILE_NOT_FOUND", "invalid_input"
            )
        else:
            print_error(f"Input file not found: {queue_input_file}")
        raise typer.Exit(1)

    urls = _read_urls(queue_input_file)
    if not urls:
        message = "No valid URLs found in input"
        if json_output:
            _write_batch_webpage_queue_error(message, "NO_URLS_FOUND", "invalid_input")
        else:
            print_error(message)
        raise typer.Exit(1)

    _validate_batch_webpage_urls(urls, json_output)
    planned_output_paths = _webpage_output_paths(urls, queue_output_dir)
    return queue_input_file, queue_output_dir, urls, planned_output_paths


def _queue_batch_webpages(
    input_file: Path | None,
    output_dir: Path,
    concurrency: int,
    timeout: int,
    selector: str | None,
    use_proxy: bool,
    skip_existing: bool,
    json_output: bool,
) -> None:
    """Queue the batch webpages job for background processing."""
    from gobbler_queue.manager import JobManager
    from gobbler_queue.models import JobType

    # Queue workers execute subprocess argv, so queued webpage batches need a
    # durable input file path rather than stdin-only URLs stored in job args.
    queue_input_file, queue_output_dir, urls, planned_output_paths = _queue_batch_webpage_inputs(
        input_file=input_file,
        output_dir=output_dir,
        json_output=json_output,
    )

    # Store URLs and planned outputs in args for queue inspection; pass the
    # input file in argv because workers execute the subprocess argv.
    args = {
        "urls": urls,
        "input_file": str(queue_input_file),
        "output_paths": [str(path) for path in planned_output_paths],
        "output_dir": str(queue_output_dir),
        "concurrency": concurrency,
        "timeout": timeout,
        "selector": selector,
        "use_proxy": use_proxy,
        "skip_existing": skip_existing,
    }

    argv = [
        "gobbler",
        "batch",
        "webpages",
        str(queue_input_file),
        "--output-dir",
        str(queue_output_dir),
        "--concurrency",
        str(concurrency),
        "--timeout",
        str(timeout),
    ]
    if selector:
        argv.extend(["--selector", selector])
    if not use_proxy:
        argv.append("--no-proxy")
    if not skip_existing:
        argv.append("--no-skip-existing")

    command = shlex.join(argv)

    try:
        manager = JobManager()
        job = manager.create_job(
            job_type=JobType.BATCH_WEBPAGE,
            command=command,
            args=args,
            argv=argv,
        )
        if json_output:
            _write_json_line(
                {
                    "type": "job_queued",
                    "success": True,
                    "job_id": job.id,
                    "job_type": JobType.BATCH_WEBPAGE.value,
                    "status": "pending",
                    "total_urls": len(urls),
                    "options": {
                        "concurrency": concurrency,
                        "timeout": timeout,
                        "selector": selector,
                        "use_proxy": use_proxy,
                        "skip_existing": skip_existing,
                    },
                    "summary": _batch_summary(
                        len(urls),
                        0,
                        0,
                        0,
                        outcomes=Counter({"queue_submission": 1}),
                    ),
                }
            )
            return

        print_success(f"Queued batch webpage job: {job.id}")
        print_info(f"Processing {len(urls)} URLs")
        print_info(f"Use 'gobbler jobs get {job.id}' to check progress")
        _print_categorized_summary(
            _batch_summary(len(urls), 0, 0, 0, outcomes=Counter({"queue_submission": 1}))
        )
    except Exception as e:
        if json_output:
            _write_batch_webpage_queue_error(
                "Failed to queue batch webpage job.",
                "BATCH_WEBPAGE_QUEUE_ERROR",
            )
        else:
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

    # Filter out empty lines and comments while preserving surrounding whitespace
    # on candidate URLs so validation can reject whitespace/control characters.
    urls = []
    for raw_line in lines:
        stripped = raw_line.strip()
        if stripped and not stripped.startswith("#"):
            urls.append(raw_line)

    return urls


def _invalid_webpage_urls(urls: list[str]) -> list[str]:
    """Return batch webpage URLs rejected by single-page webpage validation."""
    return [url for url in urls if not _is_valid_webpage_url(url)]


def _write_invalid_webpage_url_records(invalid_urls: list[str], json_output: bool) -> None:
    """Write stable invalid-input diagnostics for invalid batch webpage URLs."""
    if json_output:
        for url in invalid_urls:
            _write_json_line(
                {
                    "type": "invalid_input",
                    "success": False,
                    "error_code": WEBPAGE_INVALID_URL_CODE,
                    "error": WEBPAGE_INVALID_URL_MESSAGE,
                    "url": _safe_batch_webpage_failure_source(url),
                    "source": _safe_batch_webpage_failure_source(url),
                    "suggestion": WEBPAGE_INVALID_URL_SUGGESTION,
                }
            )
        return

    for url in invalid_urls:
        print_error(f"{WEBPAGE_INVALID_URL_MESSAGE} {url}")


def _validate_batch_webpage_urls(urls: list[str], json_output: bool) -> None:
    """Reject invalid batch webpage URLs before dry-run planning or dispatch."""
    invalid_urls = _invalid_webpage_urls(urls)
    if not invalid_urls:
        return

    _write_invalid_webpage_url_records(invalid_urls, json_output)
    summary = _invalid_input_summary(len(invalid_urls))
    if json_output:
        _write_json_line({"type": "batch_complete", "success": False, "summary": summary})
    else:
        _print_categorized_summary(summary)
    raise typer.Exit(1)


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

    # Use hostname, not netloc, so URL userinfo can never enter output paths.
    domain = (parsed.hostname or "unknown").lower()
    if domain.startswith("www."):
        domain = domain[4:]

    # Do not retain paths from credential- or token-bearing sources in output names.
    path = "" if any(marker in url for marker in ("@", "?", "#")) else parsed.path.strip("/")

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


def _webpage_output_paths(urls: list[str], output_dir: Path) -> list[Path]:
    """Return deterministic output paths for ordered batch webpage URLs.

    URLs that map to a unique sanitized name keep the historical ``<name>.md``
    filename. When multiple URLs would map to the same filename, keep the first
    occurrence unchanged and append a stable 1-based suffix to later entries,
    e.g. ``example.com.md``, ``example.com-2.md``, ``example.com-3.md``.
    Suffixes skip filenames reserved by any input URL's natural base path so
    historical names are not displaced by earlier duplicate entries.
    """
    base_paths = [output_dir / f"{_sanitize_url_to_filename(url)}.md" for url in urls]
    reserved_base_paths = {path.as_posix().casefold() for path in base_paths}

    output_paths: list[Path] = []
    used_paths: set[str] = set()

    for base_path in base_paths:
        output_path = base_path
        output_path_key = output_path.as_posix().casefold()
        filename_stem = base_path.stem

        suffix = 2
        while output_path_key in used_paths or (
            output_path_key in reserved_base_paths and output_path != base_path
        ):
            output_path = output_dir / f"{filename_stem}-{suffix}.md"
            output_path_key = output_path.as_posix().casefold()
            suffix += 1

        output_paths.append(output_path)
        used_paths.add(output_path_key)

    return output_paths


async def _batch_webpages(  # noqa: C901, PLR0912, PLR0915
    input_file: Path | None,
    output_dir: Path,
    concurrency: int,
    timeout: int,
    selector: str | None,  # noqa: ARG001 - Reserved for future CSS selector support
    skip_existing: bool,
    use_proxy: bool = True,
    json_output: bool = False,
    dry_run: bool = False,
) -> None:
    """Async implementation of batch webpage processing."""
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

        _validate_batch_webpage_urls(urls, json_output)
        output_paths = _webpage_output_paths(urls, output_dir)

        # Handle dry run
        if dry_run:
            would_process = []
            would_skip = []
            for url, output_path in zip(urls, output_paths, strict=True):
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
                        "summary": _batch_summary(len(urls), 0, 0, len(would_skip)),
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
                        console.print(f"  {i}. {item['url']} → {item['output']}")
                    if len(would_process) > PREVIEW_ITEM_LIMIT:
                        console.print(f"  ... and {len(would_process) - PREVIEW_ITEM_LIMIT} more")
                console.print()
            return

        # Create output directory
        output_dir.mkdir(parents=True, exist_ok=True)

        from gobbler_core.converters.webpage import convert_webpage_to_markdown

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
        outcomes: Counter[str] = Counter()

        # Create semaphore for concurrency control
        semaphore = asyncio.Semaphore(concurrency)

        async def process_url(
            url: str, output_path: Path
        ) -> tuple[str, Path, bool, str, dict[str, Any] | None]:
            """Process a single URL. Returns (url, output_path, success, message, metadata)."""
            async with semaphore:
                # Check if already exists
                if skip_existing and output_path.exists():
                    return (url, output_path, True, "skipped", None)

                try:
                    # Convert webpage to markdown
                    markdown_content, metadata = await convert_webpage_to_markdown(
                        url=url,
                        timeout=timeout,
                        use_proxy=use_proxy,
                    )

                    # Write output
                    output_path.write_text(markdown_content, encoding="utf-8")
                except Exception as e:
                    outcomes[_failure_category(e)] += 1
                    return (url, output_path, False, str(e), None)
                else:
                    return (url, output_path, True, "success", metadata)

        if json_output:
            # JSON output mode - no progress bar, stream JSON lines
            tasks = [
                process_url(url, output_path)
                for url, output_path in zip(urls, output_paths, strict=True)
            ]

            for coro in asyncio.as_completed(tasks):
                url, output_path, success, message, metadata = await coro

                if success:
                    if message == "skipped":
                        skipped += 1
                        _write_json_line(
                            {
                                "type": "item_skipped",
                                "url": url,
                                "output": str(output_path),
                                "reason": "already_exists",
                            }
                        )
                    else:
                        successful += 1
                        _write_json_line(
                            {
                                "type": "item_success",
                                "url": url,
                                "output": str(output_path),
                                "metadata": metadata,
                            }
                        )
                        results.append(
                            {
                                "url": url,
                                "output": str(output_path),
                                "success": True,
                                "metadata": metadata,
                            }
                        )
                else:
                    failed += 1
                    _write_json_line(
                        {
                            "type": "item_error",
                            "url": _safe_batch_webpage_failure_source(url),
                            "output": str(output_path),
                            "error": _safe_batch_webpage_error(message, url),
                        }
                    )
                    results.append(
                        {
                            "url": _safe_batch_webpage_failure_source(url),
                            "output": str(output_path),
                            "success": False,
                            "error": _safe_batch_webpage_error(message, url),
                        }
                    )

            # Final summary
            _write_json_line(
                {
                    "type": "batch_complete",
                    "success": failed == 0,
                    "summary": _batch_summary(
                        len(urls), successful, failed, skipped, outcomes=outcomes
                    ),
                }
            )
            if failed > 0:
                raise typer.Exit(1)
        else:
            # Normal progress bar mode
            progress = create_progress()
            with progress:
                task = progress.add_task("Converting webpages", total=len(urls))

                # Create tasks for all URLs
                tasks = [
                    process_url(url, output_path)
                    for url, output_path in zip(urls, output_paths, strict=True)
                ]

                # Process with asyncio.as_completed for real-time progress
                for coro in asyncio.as_completed(tasks):
                    url, _output_path, success, message, metadata = await coro

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
            _print_categorized_summary(
                _batch_summary(len(urls), successful, failed, skipped, outcomes=outcomes)
            )
            if failed > 0:
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
