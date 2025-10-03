"""Main MCP server implementation using FastMCP."""

import logging
from contextlib import asynccontextmanager
from typing import Optional

import httpx
from fastmcp import FastMCP
from youtube_transcript_api import (
    NoTranscriptFound,
    TranscriptsDisabled,
    VideoUnavailable,
)

from .config import get_config
from .converters import (
    convert_audio_to_markdown,
    convert_document_to_markdown,
    convert_webpage_to_markdown,
    convert_youtube_to_markdown,
)
from .utils import save_markdown_file, validate_output_path
from .utils.health import ServiceHealth
from .utils.queue import (
    estimate_task_duration,
    format_job_response,
    get_job_info,
    get_queue,
    list_jobs_in_queue,
    should_queue_task,
)

# Configure logging to stderr only (required for stdio transport)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler()],
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastMCP):  # type: ignore
    """
    Application lifespan manager.

    Handles initialization and cleanup of resources.
    """
    # Startup
    logger.info("Starting Gobbler MCP server...")
    config = get_config()
    logger.info(f"Configuration loaded from {config.config_path}")

    # Check service health at startup (don't fail if unavailable)
    async with ServiceHealth() as health:
        service_urls = {
            "Crawl4AI": config.get_service_url("crawl4ai"),
            "Docling": config.get_service_url("docling"),
            "Whisper": config.get_service_url("whisper"),
        }
        health_status = await health.check_all_services(service_urls)

        available = [name for name, status in health_status.items() if status]
        unavailable = [name for name, status in health_status.items() if not status]

        if available:
            logger.info(f"Available services: {', '.join(available)}")
        if unavailable:
            logger.warning(
                f"Unavailable services: {', '.join(unavailable)}. "
                "Some tools will not work until services are started."
            )

    logger.info("Gobbler MCP server started successfully")

    yield

    # Shutdown
    logger.info("Shutting down Gobbler MCP server...")


# Initialize FastMCP server
mcp = FastMCP("gobbler-mcp", lifespan=lifespan)


@mcp.tool()
async def transcribe_youtube(
    video_url: str,
    include_timestamps: bool = False,
    language: str = "auto",
    output_file: Optional[str] = None,
) -> str:
    """
    Extract YouTube video transcript and convert to clean markdown format.

    Uses official YouTube transcript API for fast, accurate results. Works without
    Docker containers. Returns markdown with YAML frontmatter containing metadata
    about the video and transcript.

    Args:
        video_url: YouTube video URL (youtube.com/watch?v=ID or youtu.be/ID format)
        include_timestamps: Include timestamp markers in the transcript (default: False)
        language: Transcript language code (ISO 639-1) or 'auto' for video default (default: 'auto')
        output_file: Optional directory path or full file path to save markdown. If a directory is provided, the file will be named using the video title.

    Returns:
        Markdown text with YAML frontmatter if output_file not provided,
        or success message with file path if output_file provided
    """
    try:
        # Convert to markdown
        markdown, metadata = await convert_youtube_to_markdown(
            video_url=video_url,
            include_timestamps=include_timestamps,
            language=language,
        )

        # Handle output
        if output_file:
            import os
            from pathlib import Path

            output_path = Path(output_file)

            # If output_file is a directory or doesn't have .md extension, use video title
            if output_path.is_dir() or not output_file.endswith('.md'):
                # Get title from metadata and sanitize for filename
                title = metadata.get('title', f"video_{metadata['video_id']}")
                # Remove invalid filename characters
                safe_title = "".join(c for c in title if c.isalnum() or c in (' ', '-', '_')).strip()
                safe_title = safe_title.replace(' ', '_')

                # Construct the full path
                if output_path.is_dir():
                    output_file = str(output_path / f"{safe_title}.md")
                else:
                    # It's a directory path provided as string
                    output_file = os.path.join(output_file, f"{safe_title}.md")

            # Validate output path
            error = validate_output_path(output_file)
            if error:
                return f"Error: {error}"

            # Save to file
            success = await save_markdown_file(output_file, markdown)
            if success:
                return f"Transcript saved to: {output_file}"
            else:
                return f"Failed to write file: Permission denied for {output_file}"
        else:
            # Return markdown directly
            return markdown

    except ValueError as e:
        return str(e)
    except VideoUnavailable:
        return (
            "Video not found: The video may be private, deleted, or the URL is incorrect."
        )
    except TranscriptsDisabled:
        return (
            "No transcript available for this video. The video may not have captions, "
            "or they may be disabled. To transcribe anyway, use transcribe_audio with the video file."
        )
    except NoTranscriptFound as e:
        return (
            f"Transcript not available in language '{language}'. {str(e)}. "
            "Use language='auto' for default."
        )
    except Exception as e:
        logger.error(f"Unexpected error in transcribe_youtube: {e}", exc_info=True)
        return f"Failed to extract transcript: {str(e)}"


@mcp.tool()
async def fetch_webpage(
    url: str,
    include_images: bool = True,
    timeout: int = 30,
    output_file: Optional[str] = None,
) -> str:
    """
    Convert web page content to clean markdown format.

    Fetches HTML via Crawl4AI and converts to structured markdown, preserving
    document structure, headings, links, code blocks, and basic formatting. Handles
    JavaScript-rendered content via browser automation. Requires Crawl4AI Docker container.

    Args:
        url: The full HTTP/HTTPS URL of the web page to convert
        include_images: Include image alt text and references in markdown output (default: True)
        timeout: Request timeout in seconds (default: 30, max: 120)
        output_file: Optional absolute path to save markdown file (includes frontmatter)

    Returns:
        Markdown text with YAML frontmatter if output_file not provided,
        or success message with file path if output_file provided
    """
    try:
        # Validate timeout
        if timeout < 5 or timeout > 120:
            return "Error: timeout must be between 5 and 120 seconds"

        # Convert to markdown
        markdown, metadata = await convert_webpage_to_markdown(
            url=url,
            include_images=include_images,
            timeout=timeout,
        )

        # Handle output
        if output_file:
            error = validate_output_path(output_file)
            if error:
                return f"Error: {error}"

            success = await save_markdown_file(output_file, markdown)
            if success:
                return f"Web page saved to: {output_file}"
            else:
                return f"Failed to write file: Permission denied for {output_file}"
        else:
            return markdown

    except httpx.ConnectError:
        return (
            "Crawl4AI service unavailable. The service may not be running. "
            "Start with: docker-compose up -d crawl4ai"
        )
    except httpx.TimeoutException:
        return (
            f"Failed to fetch URL: Connection timeout after {timeout} seconds. "
            "The target server may be slow or the URL may be inaccessible. "
            "To increase timeout, use the timeout parameter (maximum 120 seconds)."
        )
    except httpx.HTTPStatusError as e:
        status_code = e.response.status_code
        if status_code == 404:
            return f"HTTP 404: Page not found at {url}"
        elif status_code >= 500:
            return f"HTTP {status_code}: Server error at {url}. The target server may be experiencing issues."
        else:
            return f"HTTP {status_code}: Failed to fetch {url}"
    except RuntimeError as e:
        error_msg = str(e)
        if "not yet implemented" in error_msg:
            return error_msg
        # Crawl4AI errors
        return f"Crawl4AI error: {error_msg}"
    except Exception as e:
        logger.error(f"Unexpected error in fetch_webpage: {e}", exc_info=True)
        return f"Failed to convert web page: {str(e)}"


@mcp.tool()
async def convert_document(
    file_path: str,
    enable_ocr: bool = True,
    output_file: Optional[str] = None,
) -> str:
    """
    Convert document files (PDF, DOCX, PPTX, XLSX) to clean markdown format.

    Preserves structure including tables, headings, lists, and code blocks. Supports
    OCR for scanned documents. Requires Docling Docker container.

    Args:
        file_path: Absolute path to the document file to convert
        enable_ocr: Enable OCR for scanned documents (slower but handles image-based PDFs, default: True)
        output_file: Optional absolute path to save markdown file (includes frontmatter)

    Returns:
        Markdown text with YAML frontmatter if output_file not provided,
        or success message with file path if output_file provided
    """
    try:
        # Convert to markdown
        markdown, metadata = await convert_document_to_markdown(
            file_path=file_path,
            enable_ocr=enable_ocr,
        )

        # Handle output
        if output_file:
            error = validate_output_path(output_file)
            if error:
                return f"Error: {error}"

            success = await save_markdown_file(output_file, markdown)
            if success:
                return f"Document saved to: {output_file}"
            else:
                return f"Failed to write file: Permission denied for {output_file}"
        else:
            return markdown

    except ValueError as e:
        # File validation errors
        return str(e)
    except RuntimeError as e:
        # Service unavailable or not implemented
        if "not yet implemented" in str(e):
            return str(e)
        return f"Docling service unavailable. The service may not be running. Start with: docker-compose up -d docling"
    except Exception as e:
        logger.error(f"Unexpected error in convert_document: {e}", exc_info=True)
        return f"Failed to convert document: {str(e)}"


def _download_youtube_video_task(
    video_url: str,
    output_dir: str,
    quality: str = "best",
    format: str = "mp4",
) -> str:
    """Internal download function for both sync and queue execution."""
    import yt_dlp
    from pathlib import Path

    # Validate output directory
    output_path = Path(output_dir)
    if not output_path.is_absolute():
        return f"Error: output_dir must be an absolute path. Got: {output_dir}"

    # Create directory if it doesn't exist
    output_path.mkdir(parents=True, exist_ok=True)

    # Get video info first to get title
    ydl_opts_info = {
        'quiet': True,
        'no_warnings': True,
    }

    with yt_dlp.YoutubeDL(ydl_opts_info) as ydl:
        info = ydl.extract_info(video_url, download=False)
        title = info.get('title', 'video')
        # Sanitize title for filename
        safe_title = "".join(c for c in title if c.isalnum() or c in (' ', '-', '_')).strip()
        safe_title = safe_title.replace(' ', '_')

    # Configure download options
    quality_format = {
        'best': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',
        '1080p': 'bestvideo[height<=1080][ext=mp4]+bestaudio[ext=m4a]/best[height<=1080][ext=mp4]/best',
        '720p': 'bestvideo[height<=720][ext=mp4]+bestaudio[ext=m4a]/best[height<=720][ext=mp4]/best',
        '480p': 'bestvideo[height<=480][ext=mp4]+bestaudio[ext=m4a]/best[height<=480][ext=mp4]/best',
        '360p': 'bestvideo[height<=360][ext=mp4]+bestaudio[ext=m4a]/best[height<=360][ext=mp4]/best',
    }

    selected_format = quality_format.get(quality, quality_format['best'])

    ydl_opts = {
        'format': selected_format,
        'outtmpl': str(output_path / f'{safe_title}.%(ext)s'),
        'merge_output_format': format,
        'quiet': False,
        'no_warnings': False,
    }

    # Download video
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        ydl.download([video_url])

    # Find the downloaded file
    output_file = output_path / f'{safe_title}.{format}'
    if output_file.exists():
        file_size_mb = output_file.stat().st_size / 1024 / 1024
        return f"Video downloaded successfully to: {output_file}\nFile size: {file_size_mb:.1f} MB"
    else:
        return f"Download completed but file not found at expected location: {output_file}"


@mcp.tool()
async def download_youtube_video(
    video_url: str,
    output_dir: str,
    quality: str = "best",
    format: str = "mp4",
    auto_queue: bool = False,
) -> str:
    """
    Download YouTube video to local file.

    Downloads video using yt-dlp with configurable quality and format.
    Automatically sanitizes filenames and creates output directory if needed.

    Args:
        video_url: YouTube video URL (youtube.com/watch?v=ID or youtu.be/ID format)
        output_dir: Directory to save the downloaded video (must be absolute path)
        quality: Video quality - 'best', '1080p', '720p', '480p', '360p' (default: 'best')
        format: Output format - 'mp4', 'webm', 'mkv' (default: 'mp4')
        auto_queue: Automatically queue task if estimated duration > 1:45 (default: False)

    Returns:
        Success message with path to downloaded file.
        If queued: Returns job_id and estimated completion time.
    """
    try:
        # Check if should queue
        if should_queue_task("download_youtube", auto_queue, quality=quality):
            # Queue the task
            queue = get_queue("download")
            job = queue.enqueue(
                _download_youtube_video_task,
                video_url=video_url,
                output_dir=output_dir,
                quality=quality,
                format=format,
                job_timeout="20m",
            )
            return format_job_response(job, "download_youtube", quality=quality)

        # Execute synchronously (run in thread to avoid blocking)
        import asyncio
        return await asyncio.to_thread(_download_youtube_video_task, video_url, output_dir, quality, format)

    except Exception as e:
        logger.error(f"Unexpected error in download_youtube_video: {e}", exc_info=True)
        return f"Failed to download video: {str(e)}"


async def _transcribe_audio_task(
    file_path: str,
    model: str = "small",
    language: str = "auto",
    output_file: Optional[str] = None,
) -> str:
    """Internal transcription function for both sync and queue execution."""
    # Convert to markdown
    markdown, metadata = await convert_audio_to_markdown(
        file_path=file_path,
        model=model,
        language=language,
    )

    # Handle output
    if output_file:
        error = validate_output_path(output_file)
        if error:
            return f"Error: {error}"

        success = await save_markdown_file(output_file, markdown)
        if success:
            return f"Transcript saved to: {output_file}"
        else:
            return f"Failed to write file: Permission denied for {output_file}"
    else:
        return markdown


@mcp.tool()
async def transcribe_audio(
    file_path: str,
    model: str = "small",
    language: str = "auto",
    output_file: Optional[str] = None,
    auto_queue: bool = False,
) -> str:
    """
    Transcribe audio and video files to text using OpenAI Whisper.

    Supports multiple audio/video formats with automatic format detection via ffmpeg.
    Configurable model size for speed/accuracy tradeoff. Uses faster-whisper with
    Metal/CoreML acceleration on M-series Macs for optimal performance.

    Args:
        file_path: Absolute path to the audio or video file to transcribe
        model: Whisper model size - larger = more accurate but slower (default: 'small', options: tiny, base, small, medium, large)
        language: Audio language code (ISO 639-1) or 'auto' for automatic detection (default: 'auto')
        output_file: Optional absolute path to save markdown file (includes frontmatter)
        auto_queue: Automatically queue task if estimated duration > 1:45 (default: False)

    Returns:
        Markdown text with YAML frontmatter if output_file not provided,
        or success message with file path if output_file provided.
        If queued: Returns job_id and estimated completion time.
    """
    try:
        import os
        from pathlib import Path

        # Validate file exists first
        if not Path(file_path).exists():
            return f"Error: File not found: {file_path}"

        # Get file size for queue estimation
        file_size_mb = os.path.getsize(file_path) / 1024 / 1024

        # Check if should queue
        if should_queue_task("transcribe_audio", auto_queue, file_size_mb=file_size_mb):
            # Queue the task
            queue = get_queue("transcription")
            job = queue.enqueue(
                _transcribe_audio_task,
                file_path=file_path,
                model=model,
                language=language,
                output_file=output_file,
                job_timeout="30m",
            )
            return format_job_response(job, "transcribe_audio", file_size_mb=file_size_mb)

        # Execute synchronously
        return await _transcribe_audio_task(file_path, model, language, output_file)

    except ValueError as e:
        # File validation errors
        return str(e)
    except RuntimeError as e:
        # Service unavailable or not implemented
        if "not yet implemented" in str(e):
            return str(e)
        return f"Whisper service unavailable. The service may not be running. Start with: docker-compose up -d whisper"
    except Exception as e:
        logger.error(f"Unexpected error in transcribe_audio: {e}", exc_info=True)
        return f"Failed to transcribe audio: {str(e)}"


@mcp.tool()
async def get_job_status(job_id: str) -> str:
    """
    Check status and result of a queued job.

    Retrieves current status, progress, and result (if completed) for a job
    that was queued via auto_queue flag.

    Args:
        job_id: Job ID returned when task was queued

    Returns:
        Job status information including:
        - Current status (queued/started/finished/failed)
        - Progress information
        - Result (if completed)
        - Error message (if failed)
    """
    try:
        job_info = get_job_info(job_id)
        if job_info is None:
            return f"Job not found: {job_id}"

        # Format response based on status
        status = job_info["status"]
        result = [f"Job ID: {job_id}", f"Status: {status}"]

        if status == "queued":
            position = job_info.get("queue_position", "unknown")
            result.append(f"Queue position: {position}")
            result.append("Waiting to start...")

        elif status == "started":
            result.append("Job is currently running...")
            if job_info.get("progress"):
                result.append(f"Progress: {job_info['progress']}")

        elif status == "finished":
            result.append("✅ Job completed successfully")
            if job_info.get("result"):
                result.append(f"\nResult:\n{job_info['result']}")

        elif status == "failed":
            result.append("❌ Job failed")
            if job_info.get("error"):
                result.append(f"Error: {job_info['error']}")

        return "\n".join(result)

    except Exception as e:
        logger.error(f"Error getting job status: {e}", exc_info=True)
        return f"Failed to get job status: {str(e)}"


@mcp.tool()
async def list_jobs(queue_name: str = "default", limit: int = 20) -> str:
    """
    List jobs in a queue.

    Shows recent jobs in the specified queue with their current status.
    Useful for monitoring background tasks.

    Args:
        queue_name: Queue to list jobs from (default: 'default', options: 'transcription', 'download')
        limit: Maximum number of jobs to return (default: 20, max: 100)

    Returns:
        List of jobs with status, ID, and created time
    """
    try:
        if limit > 100:
            limit = 100

        jobs = list_jobs_in_queue(queue_name, limit)

        if not jobs:
            return f"No jobs found in queue '{queue_name}'"

        result = [f"Jobs in queue '{queue_name}' (showing up to {limit}):\n"]

        for job_data in jobs:
            status_icon = {
                "queued": "⏳",
                "started": "🔄",
                "finished": "✅",
                "failed": "❌",
            }.get(job_data["status"], "❓")

            result.append(
                f"{status_icon} {job_data['status'].upper()}: {job_data['id']}"
            )
            result.append(f"   Created: {job_data['created_at']}")

            if job_data["status"] == "queued" and job_data.get("queue_position"):
                result.append(f"   Position: {job_data['queue_position']}")

            result.append("")

        return "\n".join(result)

    except Exception as e:
        logger.error(f"Error listing jobs: {e}", exc_info=True)
        return f"Failed to list jobs: {str(e)}"
