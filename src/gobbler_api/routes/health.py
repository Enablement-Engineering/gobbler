"""Health check endpoints."""

import time
from typing import Any

import httpx
from fastapi import APIRouter, Depends

from ..auth import verify_api_key
from ..models import HealthResponse

router = APIRouter(tags=["health"])

# Track service start time
START_TIME = time.time()


async def check_service_health(url: str, timeout: int = 5) -> bool:
    """Check if a service is healthy.

    Args:
        url: Service health check URL
        timeout: Request timeout in seconds

    Returns:
        True if service is healthy, False otherwise
    """
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(url, timeout=timeout)
            return response.status_code == 200
    except Exception:
        return False


@router.get("/health", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    """Health check endpoint.

    Returns service status, version, uptime, and availability of dependent services.
    Does not require authentication.

    Returns:
        HealthResponse with service status information
    """
    uptime = time.time() - START_TIME

    # Check dependent services
    services = {
        "crawl4ai": await check_service_health("http://localhost:11235/health"),
        "docling": await check_service_health("http://localhost:5001/health"),
        "redis": await check_service_health("http://localhost:6380/"),
    }

    # Get queue stats if Redis is available
    queue_stats: dict[str, Any] | None = None
    if services["redis"]:
        try:
            from rq import Queue
            from redis import Redis

            redis_conn = Redis(host="localhost", port=6380)
            default_queue = Queue("default", connection=redis_conn)
            transcription_queue = Queue("transcription", connection=redis_conn)

            queue_stats = {
                "default": {
                    "queued": len(default_queue),
                    "started": default_queue.started_job_registry.count,
                    "finished": default_queue.finished_job_registry.count,
                    "failed": default_queue.failed_job_registry.count,
                },
                "transcription": {
                    "queued": len(transcription_queue),
                    "started": transcription_queue.started_job_registry.count,
                    "finished": transcription_queue.finished_job_registry.count,
                    "failed": transcription_queue.failed_job_registry.count,
                },
            }
        except Exception:
            pass

    return HealthResponse(
        status="healthy",
        version="0.1.0",
        uptime_seconds=uptime,
        services=services,
        queue_stats=queue_stats,
    )


@router.get("/ping")
async def ping() -> dict[str, str]:
    """Simple ping endpoint.

    Returns:
        Pong message
    """
    return {"message": "pong"}
