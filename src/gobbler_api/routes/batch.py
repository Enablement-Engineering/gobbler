"""Batch processing endpoints."""

import logging
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from rq import Queue
from redis import Redis

from ..auth import verify_api_key
from ..models import BatchConvertRequest, BatchJobResponse, ConversionType, JobStatus

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/batch", tags=["batch"])


def get_redis_connection() -> Redis:
    """Get Redis connection.

    Returns:
        Redis connection instance

    Raises:
        HTTPException: If Redis is unavailable
    """
    try:
        redis_conn = Redis(host="localhost", port=6380, decode_responses=True)
        redis_conn.ping()
        return redis_conn
    except Exception as e:
        logger.error(f"Failed to connect to Redis: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Redis service unavailable. Batch processing requires Redis.",
        )


def _batch_youtube_task(
    items: list[dict],
    output_dir: str,
    skip_existing: bool,
) -> str:
    """Internal task for batch YouTube processing."""
    import asyncio
    from gobbler_mcp.batch.youtube_batch import process_youtube_batch, get_playlist_videos

    # Extract playlist URL or video URLs
    playlist_url = items[0].get("playlist_url") if items else None
    video_urls = [item.get("video_url") for item in items if "video_url" in item]

    if playlist_url:
        # Process playlist
        summary = asyncio.run(
            process_youtube_batch(
                playlist_url=playlist_url,
                output_dir=output_dir,
                include_timestamps=items[0].get("include_timestamps", False),
                language=items[0].get("language", "auto"),
                max_videos=items[0].get("max_videos", 100),
                concurrency=items[0].get("concurrency", 2),
                skip_existing=skip_existing,
            )
        )
    else:
        # Process individual videos (not implemented yet)
        raise NotImplementedError("Batch processing of individual videos not yet supported")

    return summary.format_report()


def _batch_webpage_task(
    items: list[dict],
    output_dir: str,
    concurrency: int,
    skip_existing: bool,
) -> str:
    """Internal task for batch webpage processing."""
    import asyncio
    from gobbler_mcp.batch.webpage_batch import process_webpage_batch

    urls = [item.get("url") for item in items]
    include_images = items[0].get("include_images", True)
    timeout = items[0].get("timeout", 30)

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


def _batch_audio_task(
    items: list[dict],
    output_dir: str,
    concurrency: int,
    skip_existing: bool,
) -> str:
    """Internal task for batch audio processing."""
    import asyncio
    from gobbler_mcp.batch.file_batch import process_audio_batch

    input_dir = items[0].get("input_dir")
    model = items[0].get("model", "small")
    language = items[0].get("language", "auto")
    pattern = items[0].get("pattern", "*")
    recursive = items[0].get("recursive", False)

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


def _batch_document_task(
    items: list[dict],
    output_dir: str,
    concurrency: int,
    skip_existing: bool,
) -> str:
    """Internal task for batch document processing."""
    import asyncio
    from gobbler_mcp.batch.file_batch import process_document_batch

    input_dir = items[0].get("input_dir")
    enable_ocr = items[0].get("enable_ocr", True)
    pattern = items[0].get("pattern", "*")
    recursive = items[0].get("recursive", False)

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


@router.post("", response_model=BatchJobResponse)
async def create_batch_job(
    request: BatchConvertRequest,
    api_key: str = Depends(verify_api_key),
) -> BatchJobResponse:
    """Create a batch conversion job.

    Submit a batch of items for conversion. The job will be queued and processed
    asynchronously. Use the returned job_id to check status and retrieve results.

    Args:
        request: Batch conversion parameters
        api_key: API key for authentication

    Returns:
        BatchJobResponse with job information

    Raises:
        HTTPException: If job creation fails
    """
    try:
        # Validate items
        if not request.items:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="items list cannot be empty",
            )

        # Get Redis connection and queue
        redis_conn = get_redis_connection()
        queue_name = "transcription" if request.conversion_type == ConversionType.AUDIO else "default"
        queue = Queue(queue_name, connection=redis_conn)

        # Determine which task function to use
        if request.conversion_type == ConversionType.YOUTUBE:
            task_func = _batch_youtube_task
            timeout = "2h"
        elif request.conversion_type == ConversionType.WEBPAGE:
            task_func = _batch_webpage_task
            timeout = "2h"
        elif request.conversion_type == ConversionType.AUDIO:
            task_func = _batch_audio_task
            timeout = "24h"
        elif request.conversion_type == ConversionType.DOCUMENT:
            task_func = _batch_document_task
            timeout = "3h"
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unsupported conversion type: {request.conversion_type}",
            )

        # Enqueue the job
        job = queue.enqueue(
            task_func,
            items=request.items,
            output_dir=request.output_dir,
            concurrency=request.concurrency,
            skip_existing=request.skip_existing,
            job_timeout=timeout,
        )

        # Calculate estimated completion
        item_count = len(request.items)
        if request.conversion_type == ConversionType.YOUTUBE:
            estimated_minutes = (item_count * 7) // request.concurrency
        elif request.conversion_type == ConversionType.WEBPAGE:
            estimated_minutes = item_count
        elif request.conversion_type == ConversionType.AUDIO:
            estimated_minutes = item_count * 5
        elif request.conversion_type == ConversionType.DOCUMENT:
            estimated_minutes = item_count * 3
        else:
            estimated_minutes = item_count

        estimated_completion = f"~{estimated_minutes} minutes"

        return BatchJobResponse(
            job_id=job.id,
            status=JobStatus.QUEUED,
            queue=queue_name,
            item_count=item_count,
            estimated_completion=estimated_completion,
            created_at=datetime.utcnow(),
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error in create_batch_job: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create batch job: {str(e)}",
        )
