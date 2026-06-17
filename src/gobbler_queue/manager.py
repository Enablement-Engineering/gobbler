"""Job manager for the SQLite-based job queue.

This module provides the JobManager class which handles all job lifecycle
operations including creation, status updates, progress tracking, and cleanup.
"""

import contextlib
import errno
import json
import os
import signal
import sqlite3
from collections.abc import Callable, Sequence
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
        """Claim a pending job and mark it as running with the worker's process ID.

        Args:
            job_id: The unique identifier of the job.
            worker_pid: Process ID of the worker handling this job.

        Returns:
            True if the pending job was claimed, False if it was not found or
            already claimed.
        """
        cursor = self.database.execute(
            """
            UPDATE jobs
            SET status = ?, started_at = ?, worker_pid = ?
            WHERE id = ? AND status = ?
            """,
            (
                JobStatus.RUNNING.value,
                datetime.now(UTC).isoformat(),
                worker_pid,
                job_id,
                JobStatus.PENDING.value,
            ),
        )
        return cursor.rowcount > 0

    def recover_stale_running_jobs(
        self,
        stale_after: timedelta,
        *,
        now: datetime | None = None,
        is_pid_alive: Callable[[int], bool] | None = None,
    ) -> int:
        """Requeue stale running jobs whose worker process is gone.

        A running job is recovered only when it has both a started_at timestamp
        and worker_pid, has been running for at least stale_after, and the
        worker PID is no longer alive. Recovery does not signal any process; it
        only moves the job back to pending and clears the running-worker fields.

        Args:
            stale_after: Minimum running duration before a job can be recovered.
            now: Optional current time for deterministic age checks.
            is_pid_alive: Optional process liveness checker for deterministic or
                platform-specific checks.

        Returns:
            Number of jobs requeued from running to pending.

        Raises:
            ValueError: If stale_after is not positive.
        """
        if stale_after <= timedelta(0):
            msg = "stale_after must be positive"
            raise ValueError(msg)

        current_time = self._normalize_timestamp(now or datetime.now(UTC))
        pid_is_alive = is_pid_alive or self._is_process_alive

        rows = self.database.fetch_all(
            """
            SELECT * FROM jobs
            WHERE status = ?
              AND started_at IS NOT NULL
              AND worker_pid IS NOT NULL
            ORDER BY started_at ASC
            """,
            (JobStatus.RUNNING.value,),
        )

        recovered = 0
        for row in rows:
            job = self._row_to_job(row)
            if job.started_at is None or job.worker_pid is None:
                continue

            started_at = self._normalize_timestamp(job.started_at)
            if current_time - started_at < stale_after:
                continue

            if pid_is_alive(job.worker_pid):
                continue

            cursor = self.database.execute(
                """
                UPDATE jobs
                SET status = ?, started_at = NULL, worker_pid = NULL
                WHERE id = ?
                  AND status = ?
                  AND started_at = ?
                  AND worker_pid = ?
                """,
                (
                    JobStatus.PENDING.value,
                    job.id,
                    JobStatus.RUNNING.value,
                    row["started_at"],
                    row["worker_pid"],
                ),
            )
            recovered += cursor.rowcount

        return recovered

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
            WHERE id = ? AND status != ?
            """,
            (
                JobStatus.COMPLETED.value,
                json.dumps(result),
                datetime.now(UTC).isoformat(),
                job_id,
                JobStatus.CANCELLED.value,
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
            WHERE id = ? AND status != ?
            """,
            (
                JobStatus.FAILED.value,
                error,
                datetime.now(UTC).isoformat(),
                job_id,
                JobStatus.CANCELLED.value,
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
        signal_pid: int | None = None
        cancelled = False

        with self.database.connect() as conn:
            # Take a write lock before reading state so a pending job cannot be
            # claimed by a worker between the read and cancellation update.
            conn.execute("BEGIN IMMEDIATE")
            row = conn.execute(
                "SELECT status, worker_pid FROM jobs WHERE id = ?",
                (job_id,),
            ).fetchone()
            if row is None:
                return False

            status = JobStatus(row["status"])
            if status in (JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.CANCELLED):
                return False

            cursor = conn.execute(
                """
                UPDATE jobs
                SET status = ?, completed_at = ?, worker_pid = NULL
                WHERE id = ? AND status IN (?, ?)
                """,
                (
                    JobStatus.CANCELLED.value,
                    datetime.now(UTC).isoformat(),
                    job_id,
                    JobStatus.PENDING.value,
                    JobStatus.RUNNING.value,
                ),
            )
            cancelled = cursor.rowcount > 0
            if cancelled and status == JobStatus.RUNNING and row["worker_pid"] is not None:
                signal_pid = int(row["worker_pid"])

        # Signal after committing cancellation so worker result writes cannot
        # race back over the terminal status.
        if signal_pid is not None:
            with contextlib.suppress(OSError, ProcessLookupError):
                os.kill(signal_pid, signal.SIGTERM)

        return cancelled

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
    def _normalize_timestamp(value: datetime) -> datetime:
        """Return a timezone-aware UTC datetime."""
        if value.tzinfo is None:
            return value.replace(tzinfo=UTC)
        return value.astimezone(UTC)

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

    @staticmethod
    def _is_process_alive(pid: int) -> bool:
        """Check whether a PID appears to be alive without sending a signal."""
        if pid <= 0:
            return False

        alive = True
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            alive = False
        except PermissionError:
            alive = True
        except OSError as exc:
            if exc.errno == errno.ESRCH:
                alive = False
            elif exc.errno == errno.EPERM:
                alive = True

        return alive

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
