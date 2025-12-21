"""Server-Sent Events (SSE) endpoints for real-time updates."""

import asyncio
import json
import logging
from datetime import datetime
from typing import AsyncGenerator

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from redis import Redis
from rq.job import Job

from ..auth import verify_api_key
from ..models import EventMessage

logger = logging.getLogger(__name__)

router = APIRouter(tags=["events"])


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
            status_code=503,
            detail="Redis service unavailable. Events require Redis.",
        )


async def event_generator(
    job_id: str,
    redis_conn: Redis,
) -> AsyncGenerator[str, None]:
    """Generate Server-Sent Events for job progress.

    Args:
        job_id: Job identifier to monitor
        redis_conn: Redis connection

    Yields:
        SSE formatted event strings
    """
    try:
        # Fetch the job
        job = Job.fetch(job_id, connection=redis_conn)

        # Send initial status
        event = EventMessage(
            event="job_status",
            data={
                "job_id": job_id,
                "status": job.get_status(),
                "queue": job.origin,
            },
            timestamp=datetime.utcnow(),
        )
        yield f"data: {event.model_dump_json()}\n\n"

        # Poll for updates
        while not job.is_finished and not job.is_failed:
            await asyncio.sleep(1)

            # Refresh job
            job.refresh()

            # Get progress from job meta
            progress = job.meta.get("progress") if job.meta else None

            # Send progress update
            event = EventMessage(
                event="job_progress",
                data={
                    "job_id": job_id,
                    "status": job.get_status(),
                    "progress": progress,
                },
                timestamp=datetime.utcnow(),
            )
            yield f"data: {event.model_dump_json()}\n\n"

        # Send final status
        final_event = EventMessage(
            event="job_complete" if job.is_finished else "job_failed",
            data={
                "job_id": job_id,
                "status": job.get_status(),
                "result": job.result if job.is_finished else None,
                "error": job.exc_info if job.is_failed else None,
            },
            timestamp=datetime.utcnow(),
        )
        yield f"data: {final_event.model_dump_json()}\n\n"

    except Exception as e:
        logger.error(f"Error in event generator: {e}", exc_info=True)
        error_event = EventMessage(
            event="error",
            data={
                "job_id": job_id,
                "error": str(e),
            },
            timestamp=datetime.utcnow(),
        )
        yield f"data: {error_event.model_dump_json()}\n\n"


@router.get("/events/{job_id}")
async def stream_job_events(
    job_id: str,
    api_key: str = Depends(verify_api_key),
) -> StreamingResponse:
    """Stream real-time job progress events via Server-Sent Events (SSE).

    Subscribe to job progress updates using Server-Sent Events. The endpoint
    will stream progress updates until the job completes or fails.

    Args:
        job_id: Job identifier to monitor
        api_key: API key for authentication

    Returns:
        StreamingResponse with SSE events

    Raises:
        HTTPException: If job not found or Redis unavailable

    Example:
        ```javascript
        const eventSource = new EventSource('/events/job-123');
        eventSource.onmessage = (event) => {
            const data = JSON.parse(event.data);
            console.log('Job status:', data.status);
        };
        ```
    """
    try:
        redis_conn = get_redis_connection()

        # Verify job exists
        try:
            Job.fetch(job_id, connection=redis_conn)
        except Exception:
            raise HTTPException(
                status_code=404,
                detail=f"Job not found: {job_id}",
            )

        return StreamingResponse(
            event_generator(job_id, redis_conn),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",  # Disable nginx buffering
            },
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error in stream_job_events: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to stream events: {str(e)}",
        )


@router.get("/events")
async def stream_all_events(
    queue_name: str = "default",
    api_key: str = Depends(verify_api_key),
) -> StreamingResponse:
    """Stream real-time events for all jobs in a queue via Server-Sent Events (SSE).

    Subscribe to events for all jobs in a specific queue. This endpoint
    broadcasts updates for any job activity in the queue.

    Args:
        queue_name: Queue name to monitor (default, transcription)
        api_key: API key for authentication

    Returns:
        StreamingResponse with SSE events

    Raises:
        HTTPException: If Redis unavailable

    Example:
        ```javascript
        const eventSource = new EventSource('/events?queue_name=default');
        eventSource.onmessage = (event) => {
            const data = JSON.parse(event.data);
            console.log('Queue event:', data.event, data.data);
        };
        ```
    """
    async def queue_event_generator() -> AsyncGenerator[str, None]:
        """Generate events for all jobs in queue."""
        try:
            redis_conn = get_redis_connection()

            # Send initial ping
            ping_event = EventMessage(
                event="ping",
                data={"queue": queue_name},
                timestamp=datetime.utcnow(),
            )
            yield f"data: {ping_event.model_dump_json()}\n\n"

            # Poll for queue updates
            while True:
                await asyncio.sleep(2)

                # Send periodic ping to keep connection alive
                ping_event = EventMessage(
                    event="ping",
                    data={"queue": queue_name},
                    timestamp=datetime.utcnow(),
                )
                yield f"data: {ping_event.model_dump_json()}\n\n"

        except Exception as e:
            logger.error(f"Error in queue event generator: {e}", exc_info=True)
            error_event = EventMessage(
                event="error",
                data={"error": str(e)},
                timestamp=datetime.utcnow(),
            )
            yield f"data: {error_event.model_dump_json()}\n\n"

    try:
        return StreamingResponse(
            queue_event_generator(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
        )

    except Exception as e:
        logger.error(f"Unexpected error in stream_all_events: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to stream events: {str(e)}",
        )
