"""Gobbler Queue - Background job queue management.

This package provides SQLite-based job queue functionality for managing
background tasks like transcription, document conversion, and web crawling.

The queue system consists of:
- Database: Thread-safe SQLite database manager with WAL mode
- JobManager: High-level API for job lifecycle operations
- Worker: Background process that executes queued jobs
- Models: Job, JobStatus, JobType, and JobSummary data classes

Example usage:
    from gobbler_queue import JobManager, JobType

    manager = JobManager()
    job = manager.create_job(
        job_type=JobType.YOUTUBE,
        command="gobbler youtube https://youtube.com/watch?v=...",
        args={"url": "https://youtube.com/watch?v=..."}
    )
    print(f"Created job: {job.id}")

To run the background worker:
    python -m gobbler_queue
"""

from .database import Database
from .manager import JobManager
from .models import Job, JobStatus, JobSummary, JobType
from .worker import Worker

__version__ = "0.2.19"

__all__ = [
    "Database",
    "Job",
    "JobManager",
    "JobStatus",
    "JobSummary",
    "JobType",
    "Worker",
]
