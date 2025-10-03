"""Queue management utilities using Redis and RQ."""

import logging
from typing import Any, Dict, Optional

import redis
from rq import Queue, Worker
from rq.job import Job

from ..config import get_config

logger = logging.getLogger(__name__)

# Global Redis connection
_redis_conn: Optional[redis.Redis] = None


def get_redis_connection() -> redis.Redis:
    """
    Get or create Redis connection.

    Returns:
        Redis connection instance
    """
    global _redis_conn

    if _redis_conn is None:
        config = get_config()
        redis_config = config.data.get("redis", {})
        host = redis_config.get("host", "localhost")
        port = redis_config.get("port", 6379)
        db = redis_config.get("db", 0)

        logger.info(f"Connecting to Redis at {host}:{port}")
        _redis_conn = redis.Redis(
            host=host,
            port=port,
            db=db,
            decode_responses=False,  # RQ needs bytes
        )

    return _redis_conn


def get_queue(name: str = "default") -> Queue:
    """
    Get RQ queue by name.

    Args:
        name: Queue name (default, transcription, download, etc.)

    Returns:
        RQ Queue instance
    """
    conn = get_redis_connection()
    return Queue(name, connection=conn)


def estimate_task_duration(task_type: str, **kwargs: Any) -> int:
    """
    Estimate task duration in seconds based on task type and parameters.

    Args:
        task_type: Type of task (transcribe_audio, download_youtube, etc.)
        **kwargs: Task-specific parameters for estimation

    Returns:
        Estimated duration in seconds
    """
    if task_type == "transcribe_audio":
        # Estimate based on file size
        # Rough estimate: 1MB = ~6 seconds with faster-whisper on M-series
        file_size_mb = kwargs.get("file_size_mb", 0)
        return int(file_size_mb * 6)

    elif task_type == "download_youtube":
        # Estimate based on quality
        # Rough estimate: 360p = 1min, 720p = 2min, 1080p = 3min
        quality = kwargs.get("quality", "best")
        quality_map = {
            "360p": 60,
            "480p": 90,
            "720p": 120,
            "1080p": 180,
            "best": 180,
        }
        return quality_map.get(quality, 120)

    # Default conservative estimate
    return 120


def should_queue_task(task_type: str, auto_queue: bool = False, **kwargs: Any) -> bool:
    """
    Determine if task should be queued based on estimated duration.

    Args:
        task_type: Type of task
        auto_queue: If True, queue any task estimated > 105 seconds
        **kwargs: Task parameters for estimation

    Returns:
        True if task should be queued, False otherwise
    """
    if auto_queue:
        estimated_duration = estimate_task_duration(task_type, **kwargs)
        threshold = 105  # 1 minute 45 seconds
        should_queue = estimated_duration > threshold

        if should_queue:
            logger.info(
                f"Task {task_type} estimated at {estimated_duration}s "
                f"(threshold: {threshold}s) - will queue"
            )

        return should_queue

    return False


def get_job_info(job_id: str) -> Dict[str, Any]:
    """
    Get job information by ID.

    Args:
        job_id: RQ job ID

    Returns:
        Dictionary with job status and info
    """
    try:
        conn = get_redis_connection()
        job = Job.fetch(job_id, connection=conn)

        info = {
            "job_id": job_id,
            "status": job.get_status(),
            "created_at": job.created_at.isoformat() if job.created_at else None,
            "started_at": job.started_at.isoformat() if job.started_at else None,
            "ended_at": job.ended_at.isoformat() if job.ended_at else None,
        }

        if job.is_finished:
            info["result"] = job.result
        elif job.is_failed:
            info["error"] = str(job.exc_info)
        elif job.is_started:
            # Get progress if available
            progress = job.meta.get("progress", 0)
            info["progress"] = progress

        return info

    except Exception as e:
        logger.error(f"Failed to get job info for {job_id}: {e}")
        return {
            "job_id": job_id,
            "status": "not_found",
            "error": str(e),
        }


def list_jobs_in_queue(queue_name: str = "default", limit: int = 20) -> list:
    """
    List jobs in a queue.

    Args:
        queue_name: Name of queue
        limit: Maximum number of jobs to return

    Returns:
        List of job info dictionaries
    """
    try:
        queue = get_queue(queue_name)
        jobs = []

        # Get queued jobs
        for job in queue.jobs[:limit]:
            jobs.append({
                "job_id": job.id,
                "status": job.get_status(),
                "created_at": job.created_at.isoformat() if job.created_at else None,
                "func_name": job.func_name,
            })

        return jobs

    except Exception as e:
        logger.error(f"Failed to list jobs in queue {queue_name}: {e}")
        return []


def format_job_response(job: Job, task_type: str, **kwargs: Any) -> str:
    """
    Format job response for MCP tool return.

    Args:
        job: RQ Job instance
        task_type: Type of task
        **kwargs: Task parameters for duration estimation

    Returns:
        Formatted response string
    """
    estimated_duration = estimate_task_duration(task_type, **kwargs)
    estimated_minutes = max(1, estimated_duration // 60)

    return (
        f"Task queued successfully!\n\n"
        f"Job ID: {job.id}\n"
        f"Queue: {job.origin}\n"
        f"Estimated completion: ~{estimated_minutes} minute{'s' if estimated_minutes != 1 else ''}\n\n"
        f"Check status with: get_job_status(job_id=\"{job.id}\")\n"
        f"Or list all jobs with: list_jobs()"
    )
