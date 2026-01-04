"""SQLite database management module for the job queue.

This module provides a thread-safe SQLite database interface for managing
background job state, with support for WAL mode for better concurrency.
"""

import sqlite3
import threading
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any


class Database:
    """Thread-safe SQLite database manager for the job queue.

    Handles connection management, schema initialization, and provides
    convenient methods for executing queries and fetching results.

    Attributes:
        db_path: Path to the SQLite database file.
    """

    DEFAULT_DB_PATH = Path.home() / ".local" / "share" / "gobbler" / "jobs.db"

    # Schema definition
    SCHEMA = """
    CREATE TABLE IF NOT EXISTS jobs (
        id TEXT PRIMARY KEY,
        job_type TEXT NOT NULL,
        status TEXT NOT NULL DEFAULT 'pending',
        command TEXT NOT NULL,
        args_json TEXT,
        progress INTEGER DEFAULT 0,
        progress_message TEXT,
        result_json TEXT,
        error TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        started_at TIMESTAMP,
        completed_at TIMESTAMP,
        worker_pid INTEGER
    );

    CREATE INDEX IF NOT EXISTS idx_jobs_status ON jobs(status);
    CREATE INDEX IF NOT EXISTS idx_jobs_created ON jobs(created_at DESC);
    """

    def __init__(self, db_path: Path | None = None) -> None:
        """Initialize the database manager.

        Args:
            db_path: Path to the SQLite database file. If not provided,
                uses the default path at ~/.local/share/gobbler/jobs.db
        """
        self.db_path = db_path or self.DEFAULT_DB_PATH
        self._local = threading.local()

    def _ensure_directory(self) -> None:
        """Create parent directories for the database file if they don't exist."""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

    def _get_connection(self) -> sqlite3.Connection:
        """Get or create a thread-local database connection.

        Returns:
            A SQLite connection configured for this thread.
        """
        if not hasattr(self._local, "connection") or self._local.connection is None:
            self._ensure_directory()
            conn = sqlite3.connect(
                str(self.db_path),
                check_same_thread=False,
                timeout=30.0,
            )
            # Enable WAL mode for better concurrency
            conn.execute("PRAGMA journal_mode=WAL")
            # Use Row factory for dict-like access
            conn.row_factory = sqlite3.Row
            self._local.connection = conn
        return self._local.connection

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        """Context manager for getting a database connection.

        Provides a connection that automatically commits on success
        or rolls back on exception.

        Yields:
            A SQLite connection configured with Row factory.

        Example:
            with db.connect() as conn:
                conn.execute("INSERT INTO jobs ...")
        """
        conn = self._get_connection()
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise

    def initialize(self) -> None:
        """Create tables and indexes if they don't exist.

        This method is idempotent and safe to call multiple times.
        It will create the jobs table and necessary indexes using
        the schema defined in the SCHEMA class attribute.
        """
        with self.connect() as conn:
            conn.executescript(self.SCHEMA)

    def execute(
        self,
        query: str,
        params: tuple[Any, ...] | None = None,
    ) -> sqlite3.Cursor:
        """Execute a single SQL query.

        Args:
            query: The SQL query to execute.
            params: Optional tuple of parameters for the query.

        Returns:
            The cursor after executing the query.

        Example:
            db.execute(
                "UPDATE jobs SET status = ? WHERE id = ?",
                ("running", job_id)
            )
        """
        with self.connect() as conn:
            if params:
                return conn.execute(query, params)
            return conn.execute(query)

    def fetch_one(
        self,
        query: str,
        params: tuple[Any, ...] | None = None,
    ) -> sqlite3.Row | None:
        """Fetch a single row from the database.

        Args:
            query: The SQL query to execute.
            params: Optional tuple of parameters for the query.

        Returns:
            A Row object if a row is found, None otherwise.
            The Row object supports both index and key-based access.

        Example:
            row = db.fetch_one("SELECT * FROM jobs WHERE id = ?", (job_id,))
            if row:
                print(row["status"])
        """
        with self.connect() as conn:
            cursor = conn.execute(query, params) if params else conn.execute(query)
            return cursor.fetchone()

    def fetch_all(
        self,
        query: str,
        params: tuple[Any, ...] | None = None,
    ) -> list[sqlite3.Row]:
        """Fetch all rows matching the query.

        Args:
            query: The SQL query to execute.
            params: Optional tuple of parameters for the query.

        Returns:
            A list of Row objects. Each Row supports both index
            and key-based access.

        Example:
            rows = db.fetch_all(
                "SELECT * FROM jobs WHERE status = ?",
                ("pending",)
            )
            for row in rows:
                print(row["id"], row["command"])
        """
        with self.connect() as conn:
            cursor = conn.execute(query, params) if params else conn.execute(query)
            return cursor.fetchall()

    def close(self) -> None:
        """Close the thread-local database connection if it exists."""
        if hasattr(self._local, "connection") and self._local.connection is not None:
            self._local.connection.close()
            self._local.connection = None

    def __enter__(self) -> "Database":
        """Enter context manager."""
        return self

    def __exit__(self, *args: object) -> None:
        """Exit context manager and close connection."""
        self.close()

    def __del__(self) -> None:
        """Destructor to close connection when object is garbage collected."""
        self.close()
