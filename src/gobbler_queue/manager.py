"""Job manager for the SQLite-based job queue.

This module provides the JobManager class which handles all job lifecycle
operations including creation, status updates, progress tracking, and cleanup.
"""

import contextlib
import json
import os
import signal
import sqlite3
from collections.abc import Sequence
from datetime import UTC, datetime, timedelta
from typing import Any

from .database import Database
from .models import Job, JobStatus, JobSummary, JobType


class JobManager:
    """Manages job lifecycle in the queue.

    Provides methods for creating, updating, querying, and cleaning up jobs.
    All operations use parameterized queries to prevent SQL injection.

    Attributes:
        database: The Database instance for persistence.
    """

    def __init__(self, database: Database | None = None) -> None:
        """Initialize the job manager.

        Args:
            database: Optional Database instance. If not provided,
                creates a default Database with the standard path.
        """
        self.database = database or Database()
        self.database.initialize()

    def create_job(
        self,
        job_type: JobType,
        command: str | None = None,
        args: dict[str, Any] | None = None,
        argv: Sequence[str] | None = None,
    ) -> Job:
        """Create a new job in pending status.

        Args:
            job_type: The type of conversion job.
            command: Display/legacy CLI command string.
            args: Optional arguments for the job.
            argv: Optional structured command arguments to execute.

        Returns:
            The newly created Job instance.
        """
        job = Job.create(job_type=job_type, command=command, args=args, argv=argv)

        self.database.execute(
            """
            INSERT INTO jobs (
                id, job_type, status, command, argv_json, args_json,
                progress, progress_message, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                job.id,
                job.job_type.value,
                job.status.value,
                job.command,
                json.dumps(job.argv) if job.argv is not None else None,
                json.dumps(job.args) if job.args else None,
                job.progress,
                job.progress_message,
                job.created_at.isoformat(),
            ),
        )

        return job

    def get_job(self, job_id: str) -> Job | None:
        """Retrieve a job by its ID.

        Args:
            job_id: The unique identifier of the job.

        Returns:
            The Job instance if found, None otherwise.
        """
        row = self.database.fetch_one(
            "SELECT * FROM jobs WHERE id = ?",
            (job_id,),
        )

        if row is None:
            return None

        return self._row_to_job(row)

    def list_jobs(
        self,
        status: JobStatus | None = None,
        job_type: JobType | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[JobSummary]:
        """List jobs with optional filters.

        Args:
            status: Optional filter by job status.
            job_type: Optional filter by job type.
            limit: Maximum number of jobs to return (default 50).
            offset: Number of jobs to skip (default 0).

        Returns:
            List of JobSummary instances matching the criteria.
        """
        query = "SELECT * FROM jobs WHERE 1=1"
        params: list[Any] = []

        if status is not None:
            query += " AND status = ?"
            params.append(status.value)

        if job_type is not None:
            query += " AND job_type = ?"
            params.append(job_type.value)

        query += " ORDER BY created_at DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])

        rows = self.database.fetch_all(query, tuple(params))

        return [JobSummary.from_job(self._row_to_job(row)) for row in rows]

    def update_status(
        self,
        job_id: str,
        status: JobStatus,
        error: str | None = None,
    ) -> bool:
        """Update a job's status.

        Args:
            job_id: The unique identifier of the job.
            status: The new status to set.
            error: Optional error message (typically for failed status).

        Returns:
            True if the job was updated, False if not found.
        """
        query = "UPDATE jobs SET status = ?"
        params: list[Any] = [status.value]

        if error is not None:
            query += ", error = ?"
            params.append(error)

        # Set completed_at for terminal states
        if status in (JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.CANCELLED):
            query += ", completed_at = ?"
            params.append(datetime.now(UTC).isoformat())

        query += " WHERE id = ?"
        params.append(job_id)

        cursor = self.database.execute(query, tuple(params))
        return cursor.rowcount > 0

    def update_progress(
        self,
        job_id: str,
        progress: int,
        message: str | None = None,
    ) -> bool:
        """Update a job's progress.

        Args:
            job_id: The unique identifier of the job.
            progress: Progress percentage (0-100).
            message: Optional human-readable progress message.

        Returns:
            True if the job was updated, False if not found.
        """
        # Clamp progress to valid range
        progress = max(0, min(100, progress))

        if message is not None:
            cursor = self.database.execute(
                "UPDATE jobs SET progress = ?, progress_message = ? WHERE id = ?",
                (progress, message, job_id),
            )
        else:
            cursor = self.database.execute(
                "UPDATE jobs SET progress = ? WHERE id = ?",
                (progress, job_id),
            )

        return cursor.rowcount > 0

    def start_job(self, job_id: str, worker_pid: int) -> bool:
        """Mark a job as running with the worker's process ID.

        Args:
            job_id: The unique identifier of the job.
            worker_pid: Process ID of the worker handling this job.

        Returns:
            True if the job was updated, False if not found.
        """
        cursor = self.database.execute(
            """
            UPDATE jobs
            SET status = ?, started_at = ?, worker_pid = ?
            WHERE id = ?
            """,
            (
                JobStatus.RUNNING.value,
                datetime.now(UTC).isoformat(),
                worker_pid,
                job_id,
            ),
        )
        return cursor.rowcount > 0

    def complete_job(self, job_id: str, result: dict[str, Any]) -> bool:
        """Mark a job as completed with its result.

        Args:
            job_id: The unique identifier of the job.
            result: Result data from the job execution.

        Returns:
            True if the job was updated, False if not found.
        """
        cursor = self.database.execute(
            """
            UPDATE jobs
            SET status = ?, result_json = ?, progress = 100, completed_at = ?
            WHERE id = ?
            """,
            (
                JobStatus.COMPLETED.value,
                json.dumps(result),
                datetime.now(UTC).isoformat(),
                job_id,
            ),
        )
        return cursor.rowcount > 0

    def fail_job(self, job_id: str, error: str) -> bool:
        """Mark a job as failed with an error message.

        Args:
            job_id: The unique identifier of the job.
            error: Error message describing the failure.

        Returns:
            True if the job was updated, False if not found.
        """
        cursor = self.database.execute(
            """
            UPDATE jobs
            SET status = ?, error = ?, completed_at = ?
            WHERE id = ?
            """,
            (
                JobStatus.FAILED.value,
                error,
                datetime.now(UTC).isoformat(),
                job_id,
            ),
        )
        return cursor.rowcount > 0

    def cancel_job(self, job_id: str) -> bool:
        """Cancel a job, sending SIGTERM if it's running.

        If the job is currently running with a worker process,
        sends SIGTERM to attempt graceful termination.

        Args:
            job_id: The unique identifier of the job.

        Returns:
            True if the job was cancelled, False if not found.
        """
        # First, get the job to check if it's running
        job = self.get_job(job_id)
        if job is None:
            return False

        # If job is already in terminal state, nothing to do
        if job.is_terminal:
            return False

        # If running with a worker, try to terminate it
        if job.status == JobStatus.RUNNING and job.worker_pid is not None:
            with contextlib.suppress(OSError, ProcessLookupError):
                os.kill(job.worker_pid, signal.SIGTERM)

        # Update status to cancelled
        cursor = self.database.execute(
            """
            UPDATE jobs
            SET status = ?, completed_at = ?
            WHERE id = ?
            """,
            (
                JobStatus.CANCELLED.value,
                datetime.now(UTC).isoformat(),
                job_id,
            ),
        )
        return cursor.rowcount > 0

    def clear_jobs(
        self,
        status: JobStatus | None = None,
        older_than_days: int | None = None,
    ) -> int:
        """Delete jobs matching the specified criteria.

        Args:
            status: Optional filter by job status. If None, matches all statuses.
            older_than_days: Optional filter for jobs older than this many days.
                Uses the created_at timestamp.

        Returns:
            Number of jobs deleted.
        """
        query = "DELETE FROM jobs WHERE 1=1"
        params: list[Any] = []

        if status is not None:
            query += " AND status = ?"
            params.append(status.value)

        if older_than_days is not None:
            cutoff = datetime.now(UTC) - timedelta(days=older_than_days)
            query += " AND created_at < ?"
            params.append(cutoff.isoformat())

        cursor = self.database.execute(query, tuple(params))
        return cursor.rowcount

    def get_pending_jobs(self, limit: int = 10) -> list[Job]:
        """Get pending jobs for workers to process.

        Jobs are returned in FIFO order (oldest first).

        Args:
            limit: Maximum number of jobs to return (default 10).

        Returns:
            List of pending Job instances.
        """
        rows = self.database.fetch_all(
            """
            SELECT * FROM jobs
            WHERE status = ?
            ORDER BY created_at ASC
            LIMIT ?
            """,
            (JobStatus.PENDING.value, limit),
        )

        return [self._row_to_job(row) for row in rows]

    def count_jobs(self, status: JobStatus | None = None) -> dict[str, int]:
        """Count jobs by status.

        Args:
            status: Optional filter by specific status. If None,
                returns counts for all statuses.

        Returns:
            Dictionary mapping status names to counts.
            If status is specified, returns {"count": N}.
            Otherwise returns counts for all statuses plus "total".
        """
        if status is not None:
            row = self.database.fetch_one(
                "SELECT COUNT(*) as count FROM jobs WHERE status = ?",
                (status.value,),
            )
            return {"count": row["count"] if row else 0}

        # Get counts for all statuses
        rows = self.database.fetch_all(
            """
            SELECT status, COUNT(*) as count
            FROM jobs
            GROUP BY status
            """
        )

        result: dict[str, int] = {s.value: 0 for s in JobStatus}
        total = 0

        for row in rows:
            result[row["status"]] = row["count"]
            total += row["count"]

        result["total"] = total
        return result

    def _row_to_job(self, row: sqlite3.Row) -> Job:
        """Convert a database row to a Job instance.

        Args:
            row: SQLite Row object from a query.

        Returns:
            A Job instance populated from the row data.
        """
        args = {}
        if row["args_json"]:
            args = json.loads(row["args_json"])

        argv = None
        row_keys = set(row.keys())
        if "argv_json" in row_keys and row["argv_json"]:
            argv = self._parse_argv_json(row["argv_json"])

        result = None
        if row["result_json"]:
            result = json.loads(row["result_json"])

        return Job(
            id=row["id"],
            job_type=JobType(row["job_type"]),
            status=JobStatus(row["status"]),
            command=row["command"],
            argv=argv,
            args=args,
            progress=row["progress"] or 0,
            progress_message=row["progress_message"] or "",
            result=result,
            error=row["error"],
            created_at=self._parse_timestamp(row["created_at"]) or datetime.now(UTC),
            started_at=self._parse_timestamp(row["started_at"]),
            completed_at=self._parse_timestamp(row["completed_at"]),
            worker_pid=row["worker_pid"],
        )

    @staticmethod
    def _parse_timestamp(value: str | None) -> datetime | None:
        """Parse an ISO format timestamp string.

        Args:
            value: ISO format timestamp string or None.

        Returns:
            Parsed datetime in UTC or None.
        """
        if value is None:
            return None
        if isinstance(value, datetime):
            return value
        return datetime.fromisoformat(value)

    @staticmethod
    def _parse_argv_json(value: str) -> list[str]:
        """Parse stored argv JSON into a list of strings."""
        raw_argv = json.loads(value)
        if not isinstance(raw_argv, list):
            msg = "Stored argv_json must be a JSON array"
            raise TypeError(msg)

        argv: list[str] = []
        for arg in raw_argv:
            if not isinstance(arg, str):
                msg = "Stored argv_json must contain only strings"
                raise TypeError(msg)
            argv.append(arg)

        return argv

    def close(self) -> None:
        """Close the database connection."""
        self.database.close()

    def __enter__(self) -> "JobManager":
        """Enter context manager."""
        return self

    def __exit__(self, *args: object) -> None:
        """Exit context manager and close database."""
        self.close()

    def __del__(self) -> None:
        """Destructor to close database when object is garbage collected."""
        self.close()
