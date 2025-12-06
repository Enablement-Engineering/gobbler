"""Queue management utilities using Redis and RQ."""

import logging
import subprocess
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

    Raises:
        ConnectionError: If Redis is not reachable
    """
    global _redis_conn

    if _redis_conn is None:
        config = get_config()
        redis_config = config.data.get("redis", {})
        host = redis_config.get("host", "localhost")
        port = redis_config.get("port", 6379)
        db = redis_config.get("db", 0)

        logger.info(f"Connecting to Redis at {host}:{port}")
        try:
            _redis_conn = redis.Redis(
                host=host,
                port=port,
                db=db,
                decode_responses=False,  # RQ needs bytes
                socket_connect_timeout=5,
                socket_timeout=5,
            )
            # Test connection
            _redis_conn.ping()
        except (redis.ConnectionError, redis.TimeoutError) as e:
            error_msg = (
                f"❌ Redis connection failed.\n\n"
                f"What went wrong:\n"
                f"   Cannot connect to Redis at {host}:{port}\n\n"
                f"Why this happened:\n"
                f"   • Redis service is not running\n"
                f"   • Docker services not started\n"
                f"   • Port {port} is blocked or in use\n\n"
                f"How to fix:\n"
                f"   1. Start services: `make start-docker`\n"
                f"   2. Check Redis: `docker ps | grep redis`\n"
                f"   3. View logs: `docker logs gobbler-redis`\n\n"
                f"Note: Background tasks require Redis to be running.\n"
                f"Original error: {str(e)}"
            )
            logger.error(error_msg)
            raise ConnectionError(error_msg) from e

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


def get_media_duration(file_path: str) -> float:
    """
    Get duration of audio/video file in seconds using ffprobe.

    Args:
        file_path: Path to media file

    Returns:
        Duration in seconds, or 0 if unable to determine

    Raises:
        RuntimeError: If ffprobe fails or is not available
    """
    try:
        result = subprocess.run(
            [
                "ffprobe",
                "-v", "quiet",
                "-show_entries", "format=duration",
                "-of", "default=noprint_wrappers=1:nokey=1",
                file_path
            ],
            capture_output=True,
            text=True,
            timeout=10
        )

        if result.returncode != 0:
            logger.warning(f"ffprobe failed for {file_path}: {result.stderr}")
            return 0

        duration_str = result.stdout.strip()
        if not duration_str:
            return 0

        return float(duration_str)

    except subprocess.TimeoutExpired:
        logger.warning(f"ffprobe timed out for {file_path}")
        return 0
    except FileNotFoundError:
        raise RuntimeError("ffprobe not found. Please install ffmpeg to enable duration-based estimation.")
    except (ValueError, TypeError) as e:
        logger.warning(f"Failed to parse duration for {file_path}: {e}")
        return 0
    except Exception as e:
        logger.warning(f"Unexpected error getting duration for {file_path}: {e}")
        return 0


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
        # Estimate based on audio/video duration, not file size
        # Real-time factors based on model size (measured on M-series Mac with CoreML):
        # - tiny: ~0.15x (6.7x faster than real-time)
        # - base: ~0.20x (5x faster than real-time)
        # - small: ~0.33x (3x faster than real-time) [confirmed from actual data]
        # - medium: ~0.50x (2x faster than real-time)
        # - large: ~0.80x (1.25x faster than real-time)

        model_speed_factors = {
            "tiny": 0.15,
            "base": 0.20,
            "small": 0.33,
            "medium": 0.50,
            "large": 0.80,
        }

        # Get audio duration from file path
        file_path = kwargs.get("file_path")
        model = kwargs.get("model", "small")

        if file_path:
            try:
                audio_duration = get_media_duration(file_path)
                if audio_duration > 0:
                    # Calculate processing time based on model speed factor
                    speed_factor = model_speed_factors.get(model, 0.33)
                    # Add 30 seconds overhead for model loading and initialization
                    estimated_time = int(audio_duration * speed_factor) + 30
                    logger.info(
                        f"Transcription estimate: {audio_duration:.0f}s audio × {speed_factor} "
                        f"({model} model) + 30s overhead = {estimated_time}s"
                    )
                    return estimated_time
            except Exception as e:
                logger.warning(f"Failed to get media duration, falling back to file size: {e}")

        # Fallback to old file size-based estimation if duration unavailable
        file_size_mb = kwargs.get("file_size_mb", 0)
        if file_size_mb > 0:
            logger.info(f"Using fallback file size estimation: {file_size_mb}MB")
            return int(file_size_mb * 6)

        # Default if no info available
        return 120

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
