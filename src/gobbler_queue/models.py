"""Data models for the SQLite-based job queue system.

This module defines the core data structures used by the job queue,
including job status, types, and the Job dataclass with serialization support.
"""

import json
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from enum import Enum
from typing import Any


class JobStatus(str, Enum):
    """Status of a job in the queue."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class JobType(str, Enum):
    """Type of conversion job."""

    YOUTUBE = "youtube"
    AUDIO = "audio"
    DOCUMENT = "document"
    WEBPAGE = "webpage"
    BATCH_YOUTUBE = "batch_youtube"
    BATCH_WEBPAGE = "batch_webpage"
    BATCH_AUDIO = "batch_audio"
    BATCH_DOCUMENT = "batch_document"
    CRAWL = "crawl"


@dataclass(slots=True)
class Job:
    """Represents a job in the queue.

    Attributes:
        id: Unique identifier for the job (UUID).
        job_type: The type of conversion job.
        status: Current status of the job.
        command: Full CLI command to execute.
        args: Serialized arguments for the job.
        progress: Progress percentage (0-100).
        progress_message: Human-readable progress message.
        result: Serialized result data when completed.
        error: Error message if job failed.
        created_at: Timestamp when job was created.
        started_at: Timestamp when job started running.
        completed_at: Timestamp when job finished.
        worker_pid: Process ID of the worker handling this job.
    """

    id: str
    job_type: JobType
    status: JobStatus
    command: str
    args: dict[str, Any] = field(default_factory=dict)
    progress: int = 0
    progress_message: str = ""
    result: dict[str, Any] | None = None
    error: str | None = None
    created_at: datetime = field(default_factory=datetime.utcnow)
    started_at: datetime | None = None
    completed_at: datetime | None = None
    worker_pid: int | None = None

    @classmethod
    def create(
        cls,
        job_type: JobType,
        command: str,
        args: dict[str, Any] | None = None,
    ) -> "Job":
        """Create a new job with a generated UUID.

        Args:
            job_type: The type of conversion job.
            command: Full CLI command to execute.
            args: Optional arguments for the job.

        Returns:
            A new Job instance with pending status.
        """
        return cls(
            id=str(uuid.uuid4()),
            job_type=job_type,
            status=JobStatus.PENDING,
            command=command,
            args=args or {},
        )

    @property
    def is_terminal(self) -> bool:
        """Check if the job is in a terminal state.

        Returns:
            True if job is completed, failed, or cancelled.
        """
        return self.status in (
            JobStatus.COMPLETED,
            JobStatus.FAILED,
            JobStatus.CANCELLED,
        )

    @property
    def duration(self) -> timedelta | None:
        """Calculate the duration of the job.

        Returns:
            Time between started_at and completed_at, or None if not applicable.
        """
        if self.started_at is None:
            return None
        end_time = self.completed_at or datetime.now(UTC)
        return end_time - self.started_at

    def to_dict(self) -> dict[str, Any]:
        """Serialize the job to a dictionary.

        Returns:
            Dictionary representation suitable for JSON serialization.
        """
        return {
            "id": self.id,
            "job_type": self.job_type.value,
            "status": self.status.value,
            "command": self.command,
            "args": self.args,
            "progress": self.progress,
            "progress_message": self.progress_message,
            "result": self.result,
            "error": self.error,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "worker_pid": self.worker_pid,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Job":
        """Deserialize a job from a dictionary.

        Args:
            data: Dictionary containing job data.

        Returns:
            A Job instance.
        """
        return cls(
            id=data["id"],
            job_type=JobType(data["job_type"]),
            status=JobStatus(data["status"]),
            command=data["command"],
            args=data.get("args", {}),
            progress=data.get("progress", 0),
            progress_message=data.get("progress_message", ""),
            result=data.get("result"),
            error=data.get("error"),
            created_at=_parse_datetime(data.get("created_at")) or datetime.now(UTC),
            started_at=_parse_datetime(data.get("started_at")),
            completed_at=_parse_datetime(data.get("completed_at")),
            worker_pid=data.get("worker_pid"),
        )

    def to_json(self) -> str:
        """Serialize the job to a JSON string.

        Returns:
            JSON string representation of the job.
        """
        return json.dumps(self.to_dict())

    @classmethod
    def from_json(cls, json_str: str) -> "Job":
        """Deserialize a job from a JSON string.

        Args:
            json_str: JSON string containing job data.

        Returns:
            A Job instance.
        """
        return cls.from_dict(json.loads(json_str))


@dataclass(slots=True, frozen=True)
class JobSummary:
    """Lightweight summary of a job for list views.

    Attributes:
        id: Unique identifier for the job.
        job_type: The type of conversion job.
        status: Current status of the job.
        progress: Progress percentage (0-100).
        progress_message: Human-readable progress message.
        created_at: Timestamp when job was created.
        error: Error message if job failed (truncated).
    """

    id: str
    job_type: JobType
    status: JobStatus
    progress: int
    progress_message: str
    created_at: datetime
    error: str | None = None

    @classmethod
    def from_job(cls, job: Job) -> "JobSummary":
        """Create a summary from a full Job instance.

        Args:
            job: The full Job instance.

        Returns:
            A JobSummary with key fields.
        """
        # Truncate error message for list views
        max_error_length = 100
        error = job.error
        if error and len(error) > max_error_length:
            error = error[:97] + "..."

        return cls(
            id=job.id,
            job_type=job.job_type,
            status=job.status,
            progress=job.progress,
            progress_message=job.progress_message,
            created_at=job.created_at,
            error=error,
        )

    def to_dict(self) -> dict[str, Any]:
        """Serialize the summary to a dictionary.

        Returns:
            Dictionary representation suitable for JSON serialization.
        """
        return {
            "id": self.id,
            "job_type": self.job_type.value,
            "status": self.status.value,
            "progress": self.progress,
            "progress_message": self.progress_message,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "error": self.error,
        }


def _parse_datetime(value: str | None) -> datetime | None:
    """Parse an ISO format datetime string.

    Args:
        value: ISO format datetime string or None.

    Returns:
        Parsed datetime or None.
    """
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    return datetime.fromisoformat(value)
