"""Job management endpoints."""

import logging
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from redis import Redis
from rq import Queue
from rq.job import Job

from ..auth import verify_api_key
from ..models import JobStatus, JobStatusResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/jobs", tags=["jobs"])


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
            detail="Redis service unavailable. Job management requires Redis.",
        )


def get_job(job_id: str, redis_conn: Redis) -> Job:
    """Get job by ID.

    Args:
        job_id: Job identifier
        redis_conn: Redis connection

    Returns:
        Job instance

    Raises:
        HTTPException: If job not found
    """
    try:
        job = Job.fetch(job_id, connection=redis_conn)
        return job
    except Exception as e:
        logger.error(f"Failed to fetch job {job_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Job not found: {job_id}",
        )


def map_job_status(rq_status: str) -> JobStatus:
    """Map RQ job status to API JobStatus.

    Args:
        rq_status: RQ job status string

    Returns:
        JobStatus enum value
    """
    status_map = {
        "queued": JobStatus.QUEUED,
        "started": JobStatus.STARTED,
        "finished": JobStatus.FINISHED,
        "failed": JobStatus.FAILED,
        "canceled": JobStatus.CANCELED,
    }
    return status_map.get(rq_status, JobStatus.QUEUED)


@router.get("/{job_id}", response_model=JobStatusResponse)
async def get_job_status(
    job_id: str,
    api_key: str = Depends(verify_api_key),
) -> JobStatusResponse:
    """Get job status and result.

    Retrieve the current status of a job, including result if completed,
    error if failed, and progress information if available.

    Args:
        job_id: Job identifier
        api_key: API key for authentication

    Returns:
        JobStatusResponse with job information

    Raises:
        HTTPException: If job not found or retrieval fails
    """
    try:
        redis_conn = get_redis_connection()
        job = get_job(job_id, redis_conn)

        # Get job metadata
        job_status = map_job_status(job.get_status())
        result = job.result if job.is_finished else None
        error = job.exc_info if job.is_failed else None

        # Parse timestamps
        created_at = datetime.fromtimestamp(job.created_at.timestamp()) if job.created_at else None
        started_at = datetime.fromtimestamp(job.started_at.timestamp()) if job.started_at else None
        ended_at = datetime.fromtimestamp(job.ended_at.timestamp()) if job.ended_at else None

        # Get progress information from job meta
        progress: dict[str, Any] | None = job.meta.get("progress") if job.meta else None

        return JobStatusResponse(
            job_id=job_id,
            status=job_status,
            queue=job.origin,
            result=result,
            error=error,
            created_at=created_at,
            started_at=started_at,
            ended_at=ended_at,
            progress=progress,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error in get_job_status: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get job status: {str(e)}",
        )


@router.delete("/{job_id}")
async def cancel_job(
    job_id: str,
    api_key: str = Depends(verify_api_key),
) -> dict[str, str]:
    """Cancel a running or queued job.

    Cancel a job that is currently running or waiting in the queue.
    Jobs that have already finished cannot be canceled.

    Args:
        job_id: Job identifier
        api_key: API key for authentication

    Returns:
        Success message

    Raises:
        HTTPException: If job not found or cancellation fails
    """
    try:
        redis_conn = get_redis_connection()
        job = get_job(job_id, redis_conn)

        # Check if job can be canceled
        if job.is_finished:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot cancel a finished job",
            )

        if job.is_failed:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot cancel a failed job",
            )

        # Cancel the job
        job.cancel()

        return {
            "message": f"Job {job_id} canceled successfully",
            "job_id": job_id,
            "status": "canceled",
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error in cancel_job: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to cancel job: {str(e)}",
        )


@router.get("", response_model=list[JobStatusResponse])
async def list_jobs(
    queue_name: str = "default",
    limit: int = 50,
    api_key: str = Depends(verify_api_key),
) -> list[JobStatusResponse]:
    """List recent jobs in a queue.

    Retrieve a list of recent jobs from a specific queue, including
    both queued and finished jobs.

    Args:
        queue_name: Queue name (default, transcription)
        limit: Maximum number of jobs to return
        api_key: API key for authentication

    Returns:
        List of JobStatusResponse objects

    Raises:
        HTTPException: If queue access fails
    """
    try:
        redis_conn = get_redis_connection()
        queue = Queue(queue_name, connection=redis_conn)

        jobs: list[JobStatusResponse] = []

        # Get queued jobs
        for job in queue.get_jobs()[:limit]:
            jobs.append(
                JobStatusResponse(
                    job_id=job.id,
                    status=map_job_status(job.get_status()),
                    queue=job.origin,
                    result=job.result if job.is_finished else None,
                    error=job.exc_info if job.is_failed else None,
                    created_at=datetime.fromtimestamp(job.created_at.timestamp()) if job.created_at else None,
                    started_at=datetime.fromtimestamp(job.started_at.timestamp()) if job.started_at else None,
                    ended_at=datetime.fromtimestamp(job.ended_at.timestamp()) if job.ended_at else None,
                    progress=job.meta.get("progress") if job.meta else None,
                )
            )

        # Get finished jobs
        for job_id in queue.finished_job_registry.get_job_ids()[:limit - len(jobs)]:
            try:
                job = Job.fetch(job_id, connection=redis_conn)
                jobs.append(
                    JobStatusResponse(
                        job_id=job.id,
                        status=JobStatus.FINISHED,
                        queue=job.origin,
                        result=job.result,
                        error=None,
                        created_at=datetime.fromtimestamp(job.created_at.timestamp()) if job.created_at else None,
                        started_at=datetime.fromtimestamp(job.started_at.timestamp()) if job.started_at else None,
                        ended_at=datetime.fromtimestamp(job.ended_at.timestamp()) if job.ended_at else None,
                        progress=job.meta.get("progress") if job.meta else None,
                    )
                )
            except Exception:
                continue

        return jobs

    except Exception as e:
        logger.error(f"Unexpected error in list_jobs: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list jobs: {str(e)}",
        )
