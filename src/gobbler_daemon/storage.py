"""SQLite fallback storage for job state when Redis is unavailable.

Provides persistent job state tracking using SQLite as a fallback
when Redis is not available or accessible.
"""

import asyncio
import logging
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class JobStorage:
    """
    SQLite-based job state storage.

    Provides fallback storage for job state when Redis is unavailable.
    Thread-safe using connection pool and asyncio locks.
    """

    def __init__(self, db_path: Optional[Path] = None) -> None:
        """
        Initialize job storage.

        Args:
            db_path: Path to SQLite database file.
                    Defaults to ~/.cache/gobbler/jobs.db
        """
        if db_path is None:
            db_path = Path.home() / ".cache" / "gobbler" / "jobs.db"

        self.db_path = Path(db_path)
        self._lock = asyncio.Lock()
        self._initialized = False

    async def start(self) -> None:
        """Initialize the database."""
        async with self._lock:
            if self._initialized:
                return

            # Ensure directory exists
            self.db_path.parent.mkdir(parents=True, exist_ok=True)

            # Create tables
            await self._create_tables()

            self._initialized = True
            logger.info(f"Job storage initialized at {self.db_path}")

    async def stop(self) -> None:
        """Close the database."""
        async with self._lock:
            self._initialized = False
            logger.info("Job storage stopped")

    async def _create_tables(self) -> None:
        """Create database tables if they don't exist."""

        def _create():
            conn = sqlite3.connect(str(self.db_path))
            cursor = conn.cursor()

            # Jobs table
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS jobs (
                    job_id TEXT PRIMARY KEY,
                    status TEXT NOT NULL,
                    converter TEXT NOT NULL,
                    input_data TEXT,
                    result TEXT,
                    error TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    started_at TEXT,
                    completed_at TEXT
                )
            """
            )

            # Job metadata table (for arbitrary key-value pairs)
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS job_metadata (
                    job_id TEXT NOT NULL,
                    key TEXT NOT NULL,
                    value TEXT,
                    PRIMARY KEY (job_id, key),
                    FOREIGN KEY (job_id) REFERENCES jobs(job_id) ON DELETE CASCADE
                )
            """
            )

            # Index for faster status queries
            cursor.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_jobs_status
                ON jobs(status)
            """
            )

            # Index for faster timestamp queries
            cursor.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_jobs_created_at
                ON jobs(created_at)
            """
            )

            conn.commit()
            conn.close()

        # Run in thread pool to avoid blocking
        await asyncio.get_event_loop().run_in_executor(None, _create)

    async def create_job(
        self, job_id: str, converter: str, input_data: Optional[str] = None
    ) -> None:
        """
        Create a new job.

        Args:
            job_id: Unique job identifier
            converter: Converter type (youtube, audio, etc.)
            input_data: Optional input data (JSON string)
        """
        async with self._lock:
            now = datetime.now().isoformat()

            def _insert():
                conn = sqlite3.connect(str(self.db_path))
                cursor = conn.cursor()
                cursor.execute(
                    """
                    INSERT INTO jobs
                    (job_id, status, converter, input_data, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                """,
                    (job_id, "queued", converter, input_data, now, now),
                )
                conn.commit()
                conn.close()

            await asyncio.get_event_loop().run_in_executor(None, _insert)
            logger.debug(f"Created job {job_id} in storage")

    async def update_job_status(
        self,
        job_id: str,
        status: str,
        result: Optional[str] = None,
        error: Optional[str] = None,
    ) -> None:
        """
        Update job status.

        Args:
            job_id: Job identifier
            status: New status (queued, started, finished, failed)
            result: Optional result data (JSON string)
            error: Optional error message
        """
        async with self._lock:
            now = datetime.now().isoformat()

            def _update():
                conn = sqlite3.connect(str(self.db_path))
                cursor = conn.cursor()

                # Update based on status
                if status == "started":
                    cursor.execute(
                        """
                        UPDATE jobs
                        SET status = ?, started_at = ?, updated_at = ?
                        WHERE job_id = ?
                    """,
                        (status, now, now, job_id),
                    )
                elif status == "finished":
                    cursor.execute(
                        """
                        UPDATE jobs
                        SET status = ?, result = ?, completed_at = ?, updated_at = ?
                        WHERE job_id = ?
                    """,
                        (status, result, now, now, job_id),
                    )
                elif status == "failed":
                    cursor.execute(
                        """
                        UPDATE jobs
                        SET status = ?, error = ?, completed_at = ?, updated_at = ?
                        WHERE job_id = ?
                    """,
                        (status, error, now, now, job_id),
                    )
                else:
                    cursor.execute(
                        """
                        UPDATE jobs
                        SET status = ?, updated_at = ?
                        WHERE job_id = ?
                    """,
                        (status, now, job_id),
                    )

                conn.commit()
                conn.close()

            await asyncio.get_event_loop().run_in_executor(None, _update)
            logger.debug(f"Updated job {job_id} status to {status}")

    async def get_job(self, job_id: str) -> Optional[Dict[str, Any]]:
        """
        Get job by ID.

        Args:
            job_id: Job identifier

        Returns:
            Job data dictionary or None if not found
        """
        async with self._lock:

            def _fetch():
                conn = sqlite3.connect(str(self.db_path))
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()

                cursor.execute(
                    """
                    SELECT * FROM jobs WHERE job_id = ?
                """,
                    (job_id,),
                )

                row = cursor.fetchone()
                conn.close()

                if row:
                    return dict(row)
                return None

            return await asyncio.get_event_loop().run_in_executor(None, _fetch)

    async def list_jobs(
        self, status: Optional[str] = None, limit: int = 100
    ) -> List[Dict[str, Any]]:
        """
        List jobs with optional status filter.

        Args:
            status: Optional status filter
            limit: Maximum number of jobs to return

        Returns:
            List of job dictionaries
        """
        async with self._lock:

            def _fetch():
                conn = sqlite3.connect(str(self.db_path))
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()

                if status:
                    cursor.execute(
                        """
                        SELECT * FROM jobs
                        WHERE status = ?
                        ORDER BY created_at DESC
                        LIMIT ?
                    """,
                        (status, limit),
                    )
                else:
                    cursor.execute(
                        """
                        SELECT * FROM jobs
                        ORDER BY created_at DESC
                        LIMIT ?
                    """,
                        (limit,),
                    )

                rows = cursor.fetchall()
                conn.close()

                return [dict(row) for row in rows]

            return await asyncio.get_event_loop().run_in_executor(None, _fetch)

    async def delete_job(self, job_id: str) -> None:
        """
        Delete a job.

        Args:
            job_id: Job identifier
        """
        async with self._lock:

            def _delete():
                conn = sqlite3.connect(str(self.db_path))
                cursor = conn.cursor()
                cursor.execute("DELETE FROM jobs WHERE job_id = ?", (job_id,))
                conn.commit()
                conn.close()

            await asyncio.get_event_loop().run_in_executor(None, _delete)
            logger.debug(f"Deleted job {job_id}")

    async def set_metadata(self, job_id: str, key: str, value: str) -> None:
        """
        Set job metadata.

        Args:
            job_id: Job identifier
            key: Metadata key
            value: Metadata value
        """
        async with self._lock:

            def _insert():
                conn = sqlite3.connect(str(self.db_path))
                cursor = conn.cursor()
                cursor.execute(
                    """
                    INSERT OR REPLACE INTO job_metadata
                    (job_id, key, value)
                    VALUES (?, ?, ?)
                """,
                    (job_id, key, value),
                )
                conn.commit()
                conn.close()

            await asyncio.get_event_loop().run_in_executor(None, _insert)

    async def get_metadata(self, job_id: str, key: str) -> Optional[str]:
        """
        Get job metadata.

        Args:
            job_id: Job identifier
            key: Metadata key

        Returns:
            Metadata value or None if not found
        """
        async with self._lock:

            def _fetch():
                conn = sqlite3.connect(str(self.db_path))
                cursor = conn.cursor()
                cursor.execute(
                    """
                    SELECT value FROM job_metadata
                    WHERE job_id = ? AND key = ?
                """,
                    (job_id, key),
                )
                row = cursor.fetchone()
                conn.close()
                return row[0] if row else None

            return await asyncio.get_event_loop().run_in_executor(None, _fetch)

    async def cleanup_old_jobs(self, days: int = 7) -> int:
        """
        Clean up jobs older than specified days.

        Args:
            days: Number of days to keep

        Returns:
            Number of jobs deleted
        """
        async with self._lock:

            def _cleanup():
                conn = sqlite3.connect(str(self.db_path))
                cursor = conn.cursor()

                # Calculate cutoff date
                from datetime import timedelta

                cutoff = (datetime.now() - timedelta(days=days)).isoformat()

                # Delete old completed/failed jobs
                cursor.execute(
                    """
                    DELETE FROM jobs
                    WHERE status IN ('finished', 'failed')
                    AND completed_at < ?
                """,
                    (cutoff,),
                )

                deleted = cursor.rowcount
                conn.commit()
                conn.close()
                return deleted

            deleted = await asyncio.get_event_loop().run_in_executor(None, _cleanup)
            logger.info(f"Cleaned up {deleted} old jobs")
            return deleted
