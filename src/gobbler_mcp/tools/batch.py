"""Batch processing tools.

Tools for processing multiple files/URLs in batches:
- batch_transcribe_youtube_playlist: Extract transcripts from YouTube playlists
- batch_fetch_webpages: Convert multiple web pages to markdown
- batch_transcribe_directory: Transcribe all audio/video files in a directory
- batch_convert_documents: Convert all documents in a directory to markdown
- get_batch_progress: Check progress of running batch operations
"""

import logging
from typing import Optional

from fastmcp import FastMCP

from ..batch.file_batch import process_audio_batch, process_document_batch, scan_directory
from ..batch.progress_tracker import ProgressTracker
from ..batch.webpage_batch import process_webpage_batch
from ..batch.youtube_batch import process_youtube_batch, get_playlist_videos
from ..constants import (
    MAX_BATCH_URLS,
    MIN_TIMEOUT,
    MAX_TIMEOUT,
    MAX_BATCH_CONCURRENCY_WEBPAGE,
    MAX_BATCH_CONCURRENCY_AUDIO,
    MAX_BATCH_CONCURRENCY_DOCUMENT,
    AUTO_QUEUE_VIDEO_THRESHOLD,
    AUTO_QUEUE_URL_THRESHOLD,
    AUTO_QUEUE_FILE_THRESHOLD,
    AUTO_QUEUE_SIZE_THRESHOLD_MB,
    DEFAULT_YOUTUBE_DELAY,
    DEFAULT_JITTER_RANGE,
    MAX_RETRIES,
)
from ..utils.queue import get_queue

logger = logging.getLogger(__name__)


def register_tools(mcp: FastMCP):
    """Register batch processing tools with the MCP server."""

    def _batch_transcribe_youtube_playlist_task(
        playlist_url: str,
        output_dir: str,
        include_timestamps: bool = False,
        language: str = "auto",
        max_videos: int = 100,
        concurrency: int = 2,
        skip_existing: bool = True,
        delay_between_requests: float = 1.5,
        jitter_range: float = 1.0,
        max_retries: int = 3,
    ) -> str:
        """Internal task for batch YouTube playlist processing with rate limiting."""
        import asyncio

        # Run async batch processing with rate limiting
        summary = asyncio.run(
            process_youtube_batch(
                playlist_url=playlist_url,
                output_dir=output_dir,
                include_timestamps=include_timestamps,
                language=language,
                max_videos=max_videos,
                concurrency=concurrency,
                skip_existing=skip_existing,
                delay_between_requests=delay_between_requests,
                jitter_range=jitter_range,
                max_retries=max_retries,
            )
        )

        return summary.format_report()

    @mcp.tool()
    async def batch_transcribe_youtube_playlist(
        playlist_url: str,
        output_dir: str,
        include_timestamps: bool = False,
        language: str = "auto",
        max_videos: int = 100,
        concurrency: int = 2,
        skip_existing: bool = True,
        auto_queue: bool = False,
        delay_between_requests: float = DEFAULT_YOUTUBE_DELAY,
        jitter_range: float = DEFAULT_JITTER_RANGE,
        max_retries: int = MAX_RETRIES,
    ) -> str:
        """
        Extract transcripts from all videos in a YouTube playlist with rate limiting.

        Processes videos with controlled concurrency and respectful rate limiting to avoid
        triggering YouTube's anti-bot measures. Uses delays, jitter, and exponential backoff
        for a more human-like request pattern.

        Args:
            playlist_url: YouTube playlist URL (youtube.com/playlist?list=...)
            output_dir: Directory to save markdown transcripts (must be absolute path)
            include_timestamps: Include timestamp markers in transcripts (default: False)
            language: Transcript language code or 'auto' (default: 'auto')
            max_videos: Maximum number of videos to process (default: 100, max: 500)
            concurrency: Number of videos to process concurrently (default: 2, max: 10) - lower is safer
            skip_existing: Skip videos that already have output files (default: True)
            auto_queue: Queue batch if >10 videos (default: False)
            delay_between_requests: Fixed delay in seconds between requests (default: 1.5)
            jitter_range: Random 0-N second jitter added to delay for variation (default: 1.0)
            max_retries: Maximum retry attempts with exponential backoff (default: 3)

        Returns:
            Batch summary report with statistics and file list

        Rate Limiting Strategy:
            - Each request waits delay_between_requests + random(0, jitter_range) seconds
            - Example: 1.5s + random(0-1s) = 1.5-2.5s between requests
            - Failed requests retry with exponential backoff (1s, 2s, 4s, ...)
            - Lower concurrency (1-2) is safer than higher values
        """
        try:
            from pathlib import Path

            # Validate output directory
            output_path = Path(output_dir)
            if not output_path.is_absolute():
                return f"Error: output_dir must be an absolute path. Got: {output_dir}"

            # Get video count for queueing decision
            try:
                videos = await get_playlist_videos(playlist_url, max_videos)
                video_count = len(videos)
            except ValueError as e:
                return str(e)

            # Check if should queue (>10 videos and auto_queue enabled)
            if auto_queue and video_count > AUTO_QUEUE_VIDEO_THRESHOLD:
                queue = get_queue("default")
                job = queue.enqueue(
                    _batch_transcribe_youtube_playlist_task,
                    playlist_url=playlist_url,
                    output_dir=output_dir,
                    include_timestamps=include_timestamps,
                    language=language,
                    max_videos=max_videos,
                    concurrency=concurrency,
                    skip_existing=skip_existing,
                    delay_between_requests=delay_between_requests,
                    jitter_range=jitter_range,
                    max_retries=max_retries,
                    job_timeout="2h",
                )

                # Calculate estimated time based on rate limiting
                # Average delay per video = delay + (jitter/2)
                avg_delay_per_video = delay_between_requests + (jitter_range / 2.0)
                # Add transcript fetch time (~5-10s per video, use 7s average)
                time_per_video = avg_delay_per_video + 7.0
                # Account for concurrency
                total_seconds = (video_count * time_per_video) / concurrency
                estimated_minutes = int(total_seconds / 60)

                return (
                    f"Batch queued successfully!\n\n"
                    f"Playlist: {video_count} videos found\n"
                    f"Job ID: {job.id}\n"
                    f"Queue: {job.origin}\n"
                    f"Rate limiting: {delay_between_requests}s + {jitter_range}s jitter, concurrency={concurrency}\n"
                    f"Estimated completion: ~{estimated_minutes} minutes ({int(total_seconds / 60 / 60)}h {estimated_minutes % 60}m)\n\n"
                    f"Check status with: get_job_status(job_id=\"{job.id}\")\n"
                    f"Or list all jobs with: list_jobs()\n\n"
                    f"💡 Tip: You can continue working while this runs in the background!"
                )

            # Execute synchronously with rate limiting
            summary = await process_youtube_batch(
                playlist_url=playlist_url,
                output_dir=output_dir,
                include_timestamps=include_timestamps,
                language=language,
                max_videos=max_videos,
                concurrency=concurrency,
                skip_existing=skip_existing,
                delay_between_requests=delay_between_requests,
                jitter_range=jitter_range,
                max_retries=max_retries,
            )

            return summary.format_report()

        except ValueError as e:
            return str(e)
        except Exception as e:
            logger.error(f"Unexpected error in batch_transcribe_youtube_playlist: {e}", exc_info=True)
            return f"Failed to process playlist: {str(e)}"

    def _batch_fetch_webpages_task(
        urls: list,
        output_dir: str,
        include_images: bool = True,
        timeout: int = 30,
        concurrency: int = 5,
        skip_existing: bool = True,
    ) -> str:
        """Internal task for batch webpage processing."""
        import asyncio

        summary = asyncio.run(
            process_webpage_batch(
                urls=urls,
                output_dir=output_dir,
                include_images=include_images,
                timeout=timeout,
                concurrency=concurrency,
                skip_existing=skip_existing,
            )
        )

        return summary.format_report()

    @mcp.tool()
    async def batch_fetch_webpages(
        urls: list[str],
        output_dir: str,
        include_images: bool = True,
        timeout: int = 30,
        concurrency: int = 5,
        skip_existing: bool = True,
        auto_queue: bool = False,
    ) -> str:
        """
        Convert multiple web pages to markdown format.

        Processes URLs with controlled concurrency to avoid overwhelming target servers.
        Automatically generates filenames from page titles or URLs.
        All results are saved to the output directory.

        Args:
            urls: List of web page URLs to convert (max: 100 URLs per batch)
            output_dir: Directory to save markdown files (must be absolute path)
            include_images: Include image references in markdown (default: True)
            timeout: Request timeout per page in seconds (default: 30, max: 120)
            concurrency: Number of pages to process concurrently (default: 5, max: 10)
            skip_existing: Skip URLs that already have output files (default: True)
            auto_queue: Queue batch if >10 URLs (default: False)

        Returns:
            Batch summary report with statistics and file list
        """
        try:
            from pathlib import Path

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

            # Check if should queue
            if auto_queue and len(urls) > AUTO_QUEUE_URL_THRESHOLD:
                queue = get_queue("default")
                job = queue.enqueue(
                    _batch_fetch_webpages_task,
                    urls=urls,
                    output_dir=output_dir,
                    include_images=include_images,
                    timeout=timeout,
                    concurrency=concurrency,
                    skip_existing=skip_existing,
                    job_timeout="2h",
                )

                estimated_minutes = len(urls) * 1  # Rough estimate: 1 min per URL
                return (
                    f"Batch queued successfully!\n\n"
                    f"URLs: {len(urls)} pages\n"
                    f"Job ID: {job.id}\n"
                    f"Queue: {job.origin}\n"
                    f"Estimated completion: ~{estimated_minutes} minutes\n\n"
                    f"Check status with: get_job_status(job_id=\"{job.id}\")\n"
                    f"Or list all jobs with: list_jobs()"
                )

            # Execute synchronously
            summary = await process_webpage_batch(
                urls=urls,
                output_dir=output_dir,
                include_images=include_images,
                timeout=timeout,
                concurrency=concurrency,
                skip_existing=skip_existing,
            )

            return summary.format_report()

        except Exception as e:
            logger.error(f"Unexpected error in batch_fetch_webpages: {e}", exc_info=True)
            return f"Failed to process webpages: {str(e)}"

    def _batch_transcribe_directory_task(
        input_dir: str,
        output_dir: str = None,
        model: str = "small",
        language: str = "auto",
        pattern: str = "*",
        recursive: bool = False,
        concurrency: int = 2,
        skip_existing: bool = True,
    ) -> str:
        """Internal task for batch directory transcription."""
        import asyncio

        summary = asyncio.run(
            process_audio_batch(
                input_dir=input_dir,
                output_dir=output_dir,
                model=model,
                language=language,
                pattern=pattern,
                recursive=recursive,
                concurrency=concurrency,
                skip_existing=skip_existing,
            )
        )

        return summary.format_report()

    @mcp.tool()
    async def batch_transcribe_directory(
        input_dir: str,
        output_dir: Optional[str] = None,
        model: str = "small",
        language: str = "auto",
        pattern: str = "*",
        recursive: bool = False,
        concurrency: int = 2,
        skip_existing: bool = True,
        auto_queue: bool = True,
    ) -> str:
        """
        Transcribe all audio/video files in a directory.

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
            skip_existing: Skip files with existing transcript files (default: True)
            auto_queue: Queue batch if >10 files or >500MB total (default: True)

        Returns:
            Batch summary report with statistics and file list
        """
        try:
            from pathlib import Path

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

            # Count files for queueing decision
            try:
                files = scan_directory(input_dir, pattern, recursive, file_type="audio")
                file_count = len(files)
            except ValueError as e:
                return str(e)

            # Check if should queue (auto-queue for >10 files or files >500MB total)
            total_size_mb = sum(f.stat().st_size for f in files) / 1024 / 1024
            should_queue = auto_queue and (file_count > AUTO_QUEUE_FILE_THRESHOLD or total_size_mb > AUTO_QUEUE_SIZE_THRESHOLD_MB)

            if should_queue:
                queue = get_queue("transcription")
                job = queue.enqueue(
                    _batch_transcribe_directory_task,
                    input_dir=input_dir,
                    output_dir=output_dir,
                    model=model,
                    language=language,
                    pattern=pattern,
                    recursive=recursive,
                    concurrency=concurrency,
                    skip_existing=skip_existing,
                    job_timeout="24h",  # 24 hours for very large files
                )

                estimated_minutes = file_count * 5  # Rough estimate: 5 min per file
                return (
                    f"Batch queued successfully!\n\n"
                    f"Files found: {file_count} audio/video files\n"
                    f"Job ID: {job.id}\n"
                    f"Queue: {job.origin}\n"
                    f"Estimated completion: ~{estimated_minutes} minutes\n\n"
                    f"Check status with: get_job_status(job_id=\"{job.id}\")\n"
                    f"Or list all jobs with: list_jobs()"
                )

            # Execute synchronously
            summary = await process_audio_batch(
                input_dir=input_dir,
                output_dir=output_dir,
                model=model,
                language=language,
                pattern=pattern,
                recursive=recursive,
                concurrency=concurrency,
                skip_existing=skip_existing,
            )

            return summary.format_report()

        except ValueError as e:
            return str(e)
        except Exception as e:
            logger.error(f"Unexpected error in batch_transcribe_directory: {e}", exc_info=True)
            return f"Failed to transcribe directory: {str(e)}"

    def _batch_convert_documents_task(
        input_dir: str,
        output_dir: str = None,
        enable_ocr: bool = True,
        pattern: str = "*",
        recursive: bool = False,
        concurrency: int = 3,
        skip_existing: bool = True,
    ) -> str:
        """Internal task for batch document conversion."""
        import asyncio

        summary = asyncio.run(
            process_document_batch(
                input_dir=input_dir,
                output_dir=output_dir,
                enable_ocr=enable_ocr,
                pattern=pattern,
                recursive=recursive,
                concurrency=concurrency,
                skip_existing=skip_existing,
            )
        )

        return summary.format_report()

    @mcp.tool()
    async def batch_convert_documents(
        input_dir: str,
        output_dir: Optional[str] = None,
        enable_ocr: bool = True,
        pattern: str = "*",
        recursive: bool = False,
        concurrency: int = 3,
        skip_existing: bool = True,
        auto_queue: bool = False,
    ) -> str:
        """
        Convert all documents in a directory to markdown.

        Supports PDF, DOCX, PPTX, XLSX with optional OCR for scanned documents.
        All results are saved to the output directory.

        Args:
            input_dir: Directory containing documents (must be absolute path)
            output_dir: Directory for markdown files (default: same as input_dir)
            enable_ocr: Enable OCR for scanned documents (default: True)
            pattern: Glob pattern for file matching (default: '*' for all supported formats)
            recursive: Search subdirectories (default: False)
            concurrency: Number of documents to process concurrently (default: 3, max: 5)
            skip_existing: Skip documents with existing markdown files (default: True)
            auto_queue: Queue batch if >10 documents (default: False)

        Returns:
            Batch summary report with statistics and file list
        """
        try:
            from pathlib import Path

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

            # Count files for queueing decision
            try:
                files = scan_directory(input_dir, pattern, recursive, file_type="document")
                file_count = len(files)
            except ValueError as e:
                return str(e)

            # Check if should queue
            if auto_queue and file_count > AUTO_QUEUE_FILE_THRESHOLD:
                queue = get_queue("default")
                job = queue.enqueue(
                    _batch_convert_documents_task,
                    input_dir=input_dir,
                    output_dir=output_dir,
                    enable_ocr=enable_ocr,
                    pattern=pattern,
                    recursive=recursive,
                    concurrency=concurrency,
                    skip_existing=skip_existing,
                    job_timeout="3h",
                )

                estimated_minutes = file_count * 3  # Rough estimate: 3 min per document
                return (
                    f"Batch queued successfully!\n\n"
                    f"Documents found: {file_count} files\n"
                    f"Job ID: {job.id}\n"
                    f"Queue: {job.origin}\n"
                    f"Estimated completion: ~{estimated_minutes} minutes\n\n"
                    f"Check status with: get_job_status(job_id=\"{job.id}\")\n"
                    f"Or list all jobs with: list_jobs()"
                )

            # Execute synchronously
            summary = await process_document_batch(
                input_dir=input_dir,
                output_dir=output_dir,
                enable_ocr=enable_ocr,
                pattern=pattern,
                recursive=recursive,
                concurrency=concurrency,
                skip_existing=skip_existing,
            )

            return summary.format_report()

        except ValueError as e:
            return str(e)
        except Exception as e:
            logger.error(f"Unexpected error in batch_convert_documents: {e}", exc_info=True)
            return f"Failed to convert documents: {str(e)}"

    @mcp.tool()
    async def get_batch_progress(batch_id: str) -> str:
        """
        Get real-time progress for a running batch operation.

        Provides detailed progress information including current item, success/failure
        counts, and any errors encountered.

        Args:
            batch_id: Batch operation ID returned when batch was started

        Returns:
            Progress report with:
            - Current status (running/completed/failed)
            - Items processed / total items
            - Success and failure counts
            - Current item being processed
            - Recent errors (if any)
        """
        try:
            tracker = ProgressTracker(batch_id)
            progress = await tracker.get_progress()

            if not progress:
                return f"Batch not found: {batch_id}\n\nBatch may have expired (24 hour retention) or ID is incorrect."

            return tracker.format_progress_report(progress)

        except Exception as e:
            logger.error(f"Error getting batch progress: {e}", exc_info=True)
            return f"Failed to get batch progress: {str(e)}"
