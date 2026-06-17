"""Data models for the SQLite-based job queue system.

This module defines the core data structures used by the job queue,
including job status, types, and the Job dataclass with serialization support.
"""

import json
import shlex
import uuid
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from typing import Any


class JobStatus(StrEnum):
    """Status of a job in the queue."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class JobType(StrEnum):
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
        command: Display/legacy CLI command string.
        argv: Structured command arguments to execute, when available.
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
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    started_at: datetime | None = None
    completed_at: datetime | None = None
    worker_pid: int | None = None
    argv: list[str] | None = None

    @classmethod
    def create(
        cls,
        job_type: JobType,
        command: str | None = None,
        args: dict[str, Any] | None = None,
        argv: Sequence[str] | None = None,
    ) -> "Job":
        """Create a new job with a generated UUID.

        Args:
            job_type: The type of conversion job.
            command: Display/legacy CLI command string.
            args: Optional arguments for the job.
            argv: Optional structured command arguments to execute.

        Returns:
            A new Job instance with pending status.

        Raises:
            ValueError: If neither command nor argv is provided, or argv is empty.
            TypeError: If argv is not a sequence of strings.
        """
        normalized_argv = _normalize_argv(argv)
        resolved_command = _resolve_command(command, normalized_argv)

        return cls(
            id=str(uuid.uuid4()),
            job_type=job_type,
            status=JobStatus.PENDING,
            command=resolved_command,
            argv=normalized_argv,
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
            "argv": self.argv,
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
        argv = _normalize_argv(data.get("argv"))
        command = data.get("command")
        if command is not None and not isinstance(command, str):
            msg = "command must be a string"
            raise TypeError(msg)

        return cls(
            id=data["id"],
            job_type=JobType(data["job_type"]),
            status=JobStatus(data["status"]),
            command=_resolve_command(command, argv),
            argv=argv,
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


def _normalize_argv(argv: object) -> list[str] | None:
    """Return argv as a list of strings, or None when absent."""
    if argv is None:
        return None
    if isinstance(argv, str) or not isinstance(argv, Sequence):
        msg = "argv must be a sequence of strings"
        raise TypeError(msg)

    normalized: list[str] = []
    for arg in argv:
        if not isinstance(arg, str):
            msg = "argv must be a sequence of strings"
            raise TypeError(msg)
        normalized.append(arg)

    if not normalized:
        msg = "argv must contain at least one argument"
        raise ValueError(msg)

    return normalized


def _resolve_command(command: str | None, argv: list[str] | None) -> str:
    """Return a command string, deriving one from argv when needed."""
    if command is not None:
        return command
    if argv is None:
        msg = "command or argv is required"
        raise ValueError(msg)
    return shlex.join(argv)
