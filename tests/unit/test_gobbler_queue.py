"""Unit tests for the SQLite-based job queue system.

Tests cover:
- Job, JobStatus, JobType, JobSummary models
- Database creation, WAL mode, connection handling
- JobManager CRUD operations and lifecycle management
"""
# ruff: noqa: DTZ001, S108

import json
import threading
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import patch

import pytest

from gobbler_queue.database import Database
from gobbler_queue.manager import JobManager
from gobbler_queue.models import Job, JobStatus, JobSummary, JobType

# =============================================================================
# Model Tests
# =============================================================================


class TestJobStatus:
    """Test JobStatus enum."""

    def test_status_values(self):
        """Test all status values are defined."""
        assert JobStatus.PENDING.value == "pending"
        assert JobStatus.RUNNING.value == "running"
        assert JobStatus.COMPLETED.value == "completed"
        assert JobStatus.FAILED.value == "failed"
        assert JobStatus.CANCELLED.value == "cancelled"

    def test_status_is_string_enum(self):
        """Test that JobStatus is a StrEnum (str() returns value)."""
        assert isinstance(JobStatus.PENDING.value, str)
        # StrEnum: str() returns the value directly
        assert str(JobStatus.PENDING) == "pending"


class TestJobType:
    """Test JobType enum."""

    def test_type_values(self):
        """Test all job type values are defined."""
        assert JobType.YOUTUBE.value == "youtube"
        assert JobType.AUDIO.value == "audio"
        assert JobType.DOCUMENT.value == "document"
        assert JobType.WEBPAGE.value == "webpage"
        assert JobType.BATCH_YOUTUBE.value == "batch_youtube"
        assert JobType.BATCH_WEBPAGE.value == "batch_webpage"
        assert JobType.BATCH_AUDIO.value == "batch_audio"
        assert JobType.BATCH_DOCUMENT.value == "batch_document"
        assert JobType.CRAWL.value == "crawl"


class TestJob:
    """Test Job dataclass."""

    def test_create_job(self):
        """Test Job.create() factory method."""
        job = Job.create(
            job_type=JobType.YOUTUBE,
            command="gobbler youtube https://youtube.com/watch?v=abc",
            args={"url": "https://youtube.com/watch?v=abc"},
        )

        assert job.id is not None
        assert len(job.id) == 36  # UUID format
        assert job.job_type == JobType.YOUTUBE
        assert job.status == JobStatus.PENDING
        assert job.command == "gobbler youtube https://youtube.com/watch?v=abc"
        assert job.args == {"url": "https://youtube.com/watch?v=abc"}
        assert job.progress == 0
        assert job.progress_message == ""
        assert job.result is None
        assert job.error is None
        assert job.created_at is not None
        assert job.started_at is None
        assert job.completed_at is None
        assert job.worker_pid is None

    def test_create_job_without_args(self):
        """Test Job.create() without optional args."""
        job = Job.create(
            job_type=JobType.AUDIO,
            command="gobbler audio /path/to/file.mp3",
        )

        assert job.args == {}

    def test_job_is_terminal_pending(self):
        """Test is_terminal for pending job."""
        job = Job.create(job_type=JobType.YOUTUBE, command="test")
        assert job.is_terminal is False

    def test_job_is_terminal_running(self):
        """Test is_terminal for running job."""
        job = Job(
            id="test-id",
            job_type=JobType.YOUTUBE,
            status=JobStatus.RUNNING,
            command="test",
        )
        assert job.is_terminal is False

    def test_job_is_terminal_completed(self):
        """Test is_terminal for completed job."""
        job = Job(
            id="test-id",
            job_type=JobType.YOUTUBE,
            status=JobStatus.COMPLETED,
            command="test",
        )
        assert job.is_terminal is True

    def test_job_is_terminal_failed(self):
        """Test is_terminal for failed job."""
        job = Job(
            id="test-id",
            job_type=JobType.YOUTUBE,
            status=JobStatus.FAILED,
            command="test",
        )
        assert job.is_terminal is True

    def test_job_is_terminal_cancelled(self):
        """Test is_terminal for cancelled job."""
        job = Job(
            id="test-id",
            job_type=JobType.YOUTUBE,
            status=JobStatus.CANCELLED,
            command="test",
        )
        assert job.is_terminal is True

    def test_job_duration_not_started(self):
        """Test duration when job hasn't started."""
        job = Job.create(job_type=JobType.YOUTUBE, command="test")
        assert job.duration is None

    def test_job_duration_running(self):
        """Test duration for running job."""
        started = datetime.now(UTC) - timedelta(minutes=5)
        job = Job(
            id="test-id",
            job_type=JobType.YOUTUBE,
            status=JobStatus.RUNNING,
            command="test",
            started_at=started,
        )
        duration = job.duration
        assert duration is not None
        assert duration.total_seconds() >= 300  # At least 5 minutes

    def test_job_duration_completed(self):
        """Test duration for completed job."""
        started = datetime(2025, 1, 1, 10, 0, 0)
        completed = datetime(2025, 1, 1, 10, 5, 30)
        job = Job(
            id="test-id",
            job_type=JobType.YOUTUBE,
            status=JobStatus.COMPLETED,
            command="test",
            started_at=started,
            completed_at=completed,
        )
        duration = job.duration
        assert duration is not None
        assert duration.total_seconds() == 330  # 5 minutes 30 seconds

    def test_job_to_dict(self):
        """Test Job serialization to dictionary."""
        created = datetime(2025, 1, 1, 10, 0, 0)
        started = datetime(2025, 1, 1, 10, 0, 5)
        completed = datetime(2025, 1, 1, 10, 5, 0)

        job = Job(
            id="test-uuid",
            job_type=JobType.DOCUMENT,
            status=JobStatus.COMPLETED,
            command="gobbler document test.pdf",
            args={"file": "test.pdf"},
            progress=100,
            progress_message="Complete",
            result={"output": "/path/to/output.md"},
            error=None,
            created_at=created,
            started_at=started,
            completed_at=completed,
            worker_pid=12345,
        )

        data = job.to_dict()

        assert data["id"] == "test-uuid"
        assert data["job_type"] == "document"
        assert data["status"] == "completed"
        assert data["command"] == "gobbler document test.pdf"
        assert data["args"] == {"file": "test.pdf"}
        assert data["progress"] == 100
        assert data["progress_message"] == "Complete"
        assert data["result"] == {"output": "/path/to/output.md"}
        assert data["error"] is None
        assert data["created_at"] == "2025-01-01T10:00:00"
        assert data["started_at"] == "2025-01-01T10:00:05"
        assert data["completed_at"] == "2025-01-01T10:05:00"
        assert data["worker_pid"] == 12345

    def test_job_from_dict(self):
        """Test Job deserialization from dictionary."""
        data = {
            "id": "test-uuid",
            "job_type": "webpage",
            "status": "failed",
            "command": "gobbler webpage https://example.com",
            "args": {"url": "https://example.com"},
            "progress": 50,
            "progress_message": "Fetching content",
            "result": None,
            "error": "Connection timeout",
            "created_at": "2025-01-01T12:00:00",
            "started_at": "2025-01-01T12:00:01",
            "completed_at": "2025-01-01T12:00:30",
            "worker_pid": 54321,
        }

        job = Job.from_dict(data)

        assert job.id == "test-uuid"
        assert job.job_type == JobType.WEBPAGE
        assert job.status == JobStatus.FAILED
        assert job.command == "gobbler webpage https://example.com"
        assert job.args == {"url": "https://example.com"}
        assert job.progress == 50
        assert job.progress_message == "Fetching content"
        assert job.result is None
        assert job.error == "Connection timeout"
        assert job.created_at == datetime(2025, 1, 1, 12, 0, 0)
        assert job.started_at == datetime(2025, 1, 1, 12, 0, 1)
        assert job.completed_at == datetime(2025, 1, 1, 12, 0, 30)
        assert job.worker_pid == 54321

    def test_job_from_dict_minimal(self):
        """Test Job deserialization with minimal data."""
        data = {
            "id": "min-uuid",
            "job_type": "audio",
            "status": "pending",
            "command": "test",
        }

        job = Job.from_dict(data)

        assert job.id == "min-uuid"
        assert job.job_type == JobType.AUDIO
        assert job.status == JobStatus.PENDING
        assert job.args == {}
        assert job.progress == 0
        assert job.progress_message == ""

    def test_job_to_json(self):
        """Test Job serialization to JSON string."""
        job = Job.create(job_type=JobType.YOUTUBE, command="test")
        json_str = job.to_json()

        assert isinstance(json_str, str)
        data = json.loads(json_str)
        assert data["job_type"] == "youtube"
        assert data["status"] == "pending"

    def test_job_from_json(self):
        """Test Job deserialization from JSON string."""
        json_str = json.dumps(
            {
                "id": "json-uuid",
                "job_type": "crawl",
                "status": "running",
                "command": "gobbler crawl https://example.com",
            }
        )

        job = Job.from_json(json_str)

        assert job.id == "json-uuid"
        assert job.job_type == JobType.CRAWL
        assert job.status == JobStatus.RUNNING

    def test_job_roundtrip_serialization(self):
        """Test that Job survives to_dict -> from_dict roundtrip."""
        original = Job(
            id="roundtrip-uuid",
            job_type=JobType.BATCH_YOUTUBE,
            status=JobStatus.COMPLETED,
            command="gobbler batch-youtube playlist.txt",
            args={"playlist": "playlist.txt", "output_dir": "/tmp"},
            progress=100,
            progress_message="All done",
            result={"files": ["a.md", "b.md"]},
            error=None,
            created_at=datetime(2025, 1, 1, 0, 0, 0),
            started_at=datetime(2025, 1, 1, 0, 0, 1),
            completed_at=datetime(2025, 1, 1, 0, 10, 0),
            worker_pid=99999,
        )

        restored = Job.from_dict(original.to_dict())

        assert restored.id == original.id
        assert restored.job_type == original.job_type
        assert restored.status == original.status
        assert restored.command == original.command
        assert restored.args == original.args
        assert restored.progress == original.progress
        assert restored.progress_message == original.progress_message
        assert restored.result == original.result
        assert restored.error == original.error
        assert restored.created_at == original.created_at
        assert restored.started_at == original.started_at
        assert restored.completed_at == original.completed_at
        assert restored.worker_pid == original.worker_pid


class TestJobSummary:
    """Test JobSummary dataclass."""

    def test_create_summary_from_job(self):
        """Test JobSummary.from_job() factory method."""
        job = Job(
            id="summary-test",
            job_type=JobType.AUDIO,
            status=JobStatus.RUNNING,
            command="test",
            progress=45,
            progress_message="Transcribing audio",
            created_at=datetime(2025, 1, 1, 10, 0, 0),
            error=None,
        )

        summary = JobSummary.from_job(job)

        assert summary.id == "summary-test"
        assert summary.job_type == JobType.AUDIO
        assert summary.status == JobStatus.RUNNING
        assert summary.progress == 45
        assert summary.progress_message == "Transcribing audio"
        assert summary.created_at == datetime(2025, 1, 1, 10, 0, 0)
        assert summary.error is None

    def test_summary_truncates_long_error(self):
        """Test that JobSummary truncates long error messages."""
        long_error = "A" * 200  # 200 character error message
        job = Job(
            id="error-test",
            job_type=JobType.WEBPAGE,
            status=JobStatus.FAILED,
            command="test",
            created_at=datetime.now(UTC),
            error=long_error,
        )

        summary = JobSummary.from_job(job)

        assert len(summary.error) == 100  # 97 chars + "..."
        assert summary.error.endswith("...")

    def test_summary_keeps_short_error(self):
        """Test that JobSummary keeps short error messages intact."""
        short_error = "Connection refused"
        job = Job(
            id="error-test",
            job_type=JobType.WEBPAGE,
            status=JobStatus.FAILED,
            command="test",
            created_at=datetime.now(UTC),
            error=short_error,
        )

        summary = JobSummary.from_job(job)

        assert summary.error == short_error

    def test_summary_to_dict(self):
        """Test JobSummary serialization to dictionary."""
        summary = JobSummary(
            id="dict-test",
            job_type=JobType.DOCUMENT,
            status=JobStatus.COMPLETED,
            progress=100,
            progress_message="Done",
            created_at=datetime(2025, 1, 1, 12, 0, 0),
            error=None,
        )

        data = summary.to_dict()

        assert data["id"] == "dict-test"
        assert data["job_type"] == "document"
        assert data["status"] == "completed"
        assert data["progress"] == 100
        assert data["progress_message"] == "Done"
        assert data["created_at"] == "2025-01-01T12:00:00"
        assert data["error"] is None


# =============================================================================
# Database Tests
# =============================================================================


class TestDatabase:
    """Test Database class."""

    def test_default_db_path(self):
        """Test default database path."""
        db = Database()
        assert db.db_path == Path.home() / ".local" / "share" / "gobbler" / "jobs.db"

    def test_custom_db_path(self, tmp_path):
        """Test custom database path."""
        custom_path = tmp_path / "custom" / "test.db"
        db = Database(db_path=custom_path)
        assert db.db_path == custom_path

    def test_initialize_creates_tables(self, tmp_path):
        """Test that initialize creates the jobs table."""
        db_path = tmp_path / "test.db"
        db = Database(db_path=db_path)
        db.initialize()

        # Verify table exists
        with db.connect() as conn:
            cursor = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='jobs'"
            )
            result = cursor.fetchone()
            assert result is not None
            assert result[0] == "jobs"

    def test_initialize_creates_indexes(self, tmp_path):
        """Test that initialize creates indexes."""
        db_path = tmp_path / "test.db"
        db = Database(db_path=db_path)
        db.initialize()

        # Verify indexes exist
        with db.connect() as conn:
            cursor = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='index' AND name LIKE 'idx_jobs_%'"
            )
            indexes = [row[0] for row in cursor.fetchall()]
            assert "idx_jobs_status" in indexes
            assert "idx_jobs_created" in indexes

    def test_initialize_is_idempotent(self, tmp_path):
        """Test that initialize can be called multiple times."""
        db_path = tmp_path / "test.db"
        db = Database(db_path=db_path)

        # Call initialize multiple times
        db.initialize()
        db.initialize()
        db.initialize()

        # Should not raise any errors
        with db.connect() as conn:
            cursor = conn.execute("SELECT COUNT(*) FROM jobs")
            assert cursor.fetchone()[0] == 0

    def test_wal_mode_enabled(self, tmp_path):
        """Test that WAL mode is enabled."""
        db_path = tmp_path / "test.db"
        db = Database(db_path=db_path)
        db.initialize()

        with db.connect() as conn:
            cursor = conn.execute("PRAGMA journal_mode")
            mode = cursor.fetchone()[0]
            assert mode.lower() == "wal"

    def test_creates_parent_directories(self, tmp_path):
        """Test that database creates parent directories."""
        db_path = tmp_path / "deep" / "nested" / "path" / "test.db"
        db = Database(db_path=db_path)
        db.initialize()

        assert db_path.parent.exists()
        assert db_path.exists()

    def test_execute_insert(self, tmp_path):
        """Test execute with INSERT statement."""
        db_path = tmp_path / "test.db"
        db = Database(db_path=db_path)
        db.initialize()

        cursor = db.execute(
            "INSERT INTO jobs (id, job_type, status, command) VALUES (?, ?, ?, ?)",
            ("test-id", "youtube", "pending", "test command"),
        )

        assert cursor.rowcount == 1

    def test_fetch_one_found(self, tmp_path):
        """Test fetch_one when row exists."""
        db_path = tmp_path / "test.db"
        db = Database(db_path=db_path)
        db.initialize()

        db.execute(
            "INSERT INTO jobs (id, job_type, status, command) VALUES (?, ?, ?, ?)",
            ("test-id", "youtube", "pending", "test command"),
        )

        row = db.fetch_one("SELECT * FROM jobs WHERE id = ?", ("test-id",))

        assert row is not None
        assert row["id"] == "test-id"
        assert row["job_type"] == "youtube"
        assert row["status"] == "pending"

    def test_fetch_one_not_found(self, tmp_path):
        """Test fetch_one when row doesn't exist."""
        db_path = tmp_path / "test.db"
        db = Database(db_path=db_path)
        db.initialize()

        row = db.fetch_one("SELECT * FROM jobs WHERE id = ?", ("nonexistent",))

        assert row is None

    def test_fetch_all(self, tmp_path):
        """Test fetch_all returns all matching rows."""
        db_path = tmp_path / "test.db"
        db = Database(db_path=db_path)
        db.initialize()

        # Insert multiple jobs
        for i in range(3):
            db.execute(
                "INSERT INTO jobs (id, job_type, status, command) VALUES (?, ?, ?, ?)",
                (f"test-{i}", "youtube", "pending", f"command {i}"),
            )

        rows = db.fetch_all("SELECT * FROM jobs WHERE status = ?", ("pending",))

        assert len(rows) == 3

    def test_fetch_all_empty(self, tmp_path):
        """Test fetch_all with no matching rows."""
        db_path = tmp_path / "test.db"
        db = Database(db_path=db_path)
        db.initialize()

        rows = db.fetch_all("SELECT * FROM jobs WHERE status = ?", ("running",))

        assert len(rows) == 0

    def test_connect_context_manager_commits(self, tmp_path):
        """Test that connect context manager commits on success."""
        db_path = tmp_path / "test.db"
        db = Database(db_path=db_path)
        db.initialize()

        with db.connect() as conn:
            conn.execute(
                "INSERT INTO jobs (id, job_type, status, command) VALUES (?, ?, ?, ?)",
                ("commit-test", "audio", "pending", "test"),
            )

        # Should be committed
        row = db.fetch_one("SELECT * FROM jobs WHERE id = ?", ("commit-test",))
        assert row is not None

    def test_connect_context_manager_rollback_on_error(self, tmp_path):
        """Test that connect context manager rolls back on error."""
        db_path = tmp_path / "test.db"
        db = Database(db_path=db_path)
        db.initialize()

        try:
            with db.connect() as conn:
                conn.execute(
                    "INSERT INTO jobs (id, job_type, status, command) VALUES (?, ?, ?, ?)",
                    ("rollback-test", "audio", "pending", "test"),
                )
                # Force an error
                msg = "Test error"
                raise ValueError(msg)
        except ValueError:
            pass

        # Should be rolled back
        row = db.fetch_one("SELECT * FROM jobs WHERE id = ?", ("rollback-test",))
        assert row is None

    def test_close_connection(self, tmp_path):
        """Test closing database connection."""
        db_path = tmp_path / "test.db"
        db = Database(db_path=db_path)
        db.initialize()

        # Access connection to create it
        with db.connect():
            pass

        # Close it
        db.close()

        # Connection should be cleared
        assert not hasattr(db._local, "connection") or db._local.connection is None

    def test_thread_local_connections(self, tmp_path):
        """Test that connections are thread-local."""
        db_path = tmp_path / "test.db"
        db = Database(db_path=db_path)
        db.initialize()

        connections = []

        def get_connection():
            with db.connect() as conn:
                connections.append(id(conn))

        # Run in two different threads
        t1 = threading.Thread(target=get_connection)
        t2 = threading.Thread(target=get_connection)
        t1.start()
        t2.start()
        t1.join()
        t2.join()

        # Each thread should have its own connection
        assert len(connections) == 2
        assert connections[0] != connections[1]


# =============================================================================
# JobManager Tests
# =============================================================================


@pytest.fixture
def job_manager(tmp_path):
    """Create a JobManager with a temporary database."""
    db_path = tmp_path / "jobs.db"
    db = Database(db_path=db_path)
    manager = JobManager(database=db)
    yield manager
    # Clean up database connection
    db.close()


class TestJobManagerCreate:
    """Test JobManager.create_job()."""

    def test_create_job_basic(self, job_manager):
        """Test creating a basic job."""
        job = job_manager.create_job(
            job_type=JobType.YOUTUBE,
            command="gobbler youtube https://youtube.com/watch?v=test",
        )

        assert job.id is not None
        assert job.job_type == JobType.YOUTUBE
        assert job.status == JobStatus.PENDING
        assert job.command == "gobbler youtube https://youtube.com/watch?v=test"

    def test_create_job_with_args(self, job_manager):
        """Test creating a job with arguments."""
        args = {"url": "https://example.com", "output": "/tmp/output.md"}
        job = job_manager.create_job(
            job_type=JobType.WEBPAGE,
            command="gobbler webpage https://example.com",
            args=args,
        )

        assert job.args == args

    def test_create_job_persisted(self, job_manager):
        """Test that created job is persisted to database."""
        job = job_manager.create_job(
            job_type=JobType.AUDIO,
            command="gobbler audio test.mp3",
        )

        # Retrieve from database
        retrieved = job_manager.get_job(job.id)

        assert retrieved is not None
        assert retrieved.id == job.id
        assert retrieved.job_type == job.job_type
        assert retrieved.status == job.status

    def test_create_multiple_jobs(self, job_manager):
        """Test creating multiple jobs."""
        jobs = []
        for i in range(5):
            job = job_manager.create_job(
                job_type=JobType.DOCUMENT,
                command=f"gobbler document file{i}.pdf",
            )
            jobs.append(job)

        # All jobs should have unique IDs
        ids = [j.id for j in jobs]
        assert len(set(ids)) == 5


class TestJobManagerGet:
    """Test JobManager.get_job()."""

    def test_get_existing_job(self, job_manager):
        """Test getting an existing job."""
        created = job_manager.create_job(
            job_type=JobType.YOUTUBE,
            command="test",
        )

        retrieved = job_manager.get_job(created.id)

        assert retrieved is not None
        assert retrieved.id == created.id

    def test_get_nonexistent_job(self, job_manager):
        """Test getting a job that doesn't exist."""
        result = job_manager.get_job("nonexistent-uuid")
        assert result is None

    def test_get_job_with_all_fields(self, job_manager):
        """Test that get_job retrieves all fields correctly."""
        # Create a job and update various fields
        job = job_manager.create_job(
            job_type=JobType.AUDIO,
            command="test command",
            args={"file": "test.mp3", "model": "base"},
        )
        job_manager.start_job(job.id, worker_pid=12345)
        job_manager.update_progress(job.id, 50, "Processing...")
        job_manager.complete_job(job.id, {"output": "/path/to/output.md"})

        retrieved = job_manager.get_job(job.id)

        assert retrieved.id == job.id
        assert retrieved.job_type == JobType.AUDIO
        assert retrieved.status == JobStatus.COMPLETED
        assert retrieved.command == "test command"
        assert retrieved.args == {"file": "test.mp3", "model": "base"}
        assert retrieved.progress == 100
        assert retrieved.result == {"output": "/path/to/output.md"}
        assert retrieved.worker_pid == 12345
        assert retrieved.started_at is not None
        assert retrieved.completed_at is not None


class TestJobManagerList:
    """Test JobManager.list_jobs()."""

    def test_list_empty(self, job_manager):
        """Test listing jobs when none exist."""
        jobs = job_manager.list_jobs()
        assert jobs == []

    def test_list_all_jobs(self, job_manager):
        """Test listing all jobs."""
        for i in range(3):
            job_manager.create_job(
                job_type=JobType.YOUTUBE,
                command=f"test {i}",
            )

        jobs = job_manager.list_jobs()
        assert len(jobs) == 3

    def test_list_returns_summaries(self, job_manager):
        """Test that list_jobs returns JobSummary objects."""
        job_manager.create_job(job_type=JobType.YOUTUBE, command="test")

        jobs = job_manager.list_jobs()

        assert len(jobs) == 1
        assert isinstance(jobs[0], JobSummary)

    def test_list_filter_by_status(self, job_manager):
        """Test filtering jobs by status."""
        job1 = job_manager.create_job(job_type=JobType.YOUTUBE, command="test1")
        job2 = job_manager.create_job(job_type=JobType.YOUTUBE, command="test2")
        job_manager.start_job(job1.id, worker_pid=1)

        pending_jobs = job_manager.list_jobs(status=JobStatus.PENDING)
        running_jobs = job_manager.list_jobs(status=JobStatus.RUNNING)

        assert len(pending_jobs) == 1
        assert pending_jobs[0].id == job2.id
        assert len(running_jobs) == 1
        assert running_jobs[0].id == job1.id

    def test_list_filter_by_type(self, job_manager):
        """Test filtering jobs by type."""
        job_manager.create_job(job_type=JobType.YOUTUBE, command="test1")
        job_manager.create_job(job_type=JobType.AUDIO, command="test2")
        job_manager.create_job(job_type=JobType.YOUTUBE, command="test3")

        youtube_jobs = job_manager.list_jobs(job_type=JobType.YOUTUBE)
        audio_jobs = job_manager.list_jobs(job_type=JobType.AUDIO)

        assert len(youtube_jobs) == 2
        assert len(audio_jobs) == 1

    def test_list_filter_by_status_and_type(self, job_manager):
        """Test filtering by both status and type."""
        job1 = job_manager.create_job(job_type=JobType.YOUTUBE, command="test1")
        job_manager.create_job(job_type=JobType.YOUTUBE, command="test2")
        job_manager.create_job(job_type=JobType.AUDIO, command="test3")
        job_manager.start_job(job1.id, worker_pid=1)

        jobs = job_manager.list_jobs(
            status=JobStatus.PENDING,
            job_type=JobType.YOUTUBE,
        )

        assert len(jobs) == 1

    def test_list_with_limit(self, job_manager):
        """Test limiting number of results."""
        for i in range(10):
            job_manager.create_job(job_type=JobType.YOUTUBE, command=f"test {i}")

        jobs = job_manager.list_jobs(limit=5)

        assert len(jobs) == 5

    def test_list_with_offset(self, job_manager):
        """Test offset for pagination."""
        for i in range(10):
            job_manager.create_job(job_type=JobType.YOUTUBE, command=f"test {i}")

        # Get page 1 (first 5)
        page1 = job_manager.list_jobs(limit=5, offset=0)
        # Get page 2 (next 5)
        page2 = job_manager.list_jobs(limit=5, offset=5)

        assert len(page1) == 5
        assert len(page2) == 5
        # Should be different jobs
        page1_ids = {j.id for j in page1}
        page2_ids = {j.id for j in page2}
        assert page1_ids.isdisjoint(page2_ids)

    def test_list_order_by_created_at_desc(self, job_manager):
        """Test that jobs are ordered by created_at descending."""
        job_ids = []
        for i in range(3):
            job = job_manager.create_job(job_type=JobType.YOUTUBE, command=f"test {i}")
            job_ids.append(job.id)
            time.sleep(0.01)  # Small delay to ensure different timestamps

        jobs = job_manager.list_jobs()

        # Most recent job should be first
        assert jobs[0].id == job_ids[2]
        assert jobs[2].id == job_ids[0]


class TestJobManagerUpdateStatus:
    """Test JobManager.update_status()."""

    def test_update_status_basic(self, job_manager):
        """Test basic status update."""
        job = job_manager.create_job(job_type=JobType.YOUTUBE, command="test")

        result = job_manager.update_status(job.id, JobStatus.RUNNING)

        assert result is True
        retrieved = job_manager.get_job(job.id)
        assert retrieved.status == JobStatus.RUNNING

    def test_update_status_with_error(self, job_manager):
        """Test status update with error message."""
        job = job_manager.create_job(job_type=JobType.YOUTUBE, command="test")

        result = job_manager.update_status(
            job.id,
            JobStatus.FAILED,
            error="Connection timeout",
        )

        assert result is True
        retrieved = job_manager.get_job(job.id)
        assert retrieved.status == JobStatus.FAILED
        assert retrieved.error == "Connection timeout"

    def test_update_status_sets_completed_at_for_terminal(self, job_manager):
        """Test that terminal states set completed_at."""
        job = job_manager.create_job(job_type=JobType.YOUTUBE, command="test")

        job_manager.update_status(job.id, JobStatus.COMPLETED)

        retrieved = job_manager.get_job(job.id)
        assert retrieved.completed_at is not None

    def test_update_status_nonexistent_job(self, job_manager):
        """Test updating status of nonexistent job."""
        result = job_manager.update_status("nonexistent", JobStatus.RUNNING)
        assert result is False


class TestJobManagerUpdateProgress:
    """Test JobManager.update_progress()."""

    def test_update_progress_basic(self, job_manager):
        """Test basic progress update."""
        job = job_manager.create_job(job_type=JobType.AUDIO, command="test")
        job_manager.start_job(job.id, worker_pid=1)

        result = job_manager.update_progress(job.id, 50)

        assert result is True
        retrieved = job_manager.get_job(job.id)
        assert retrieved.progress == 50

    def test_update_progress_with_message(self, job_manager):
        """Test progress update with message."""
        job = job_manager.create_job(job_type=JobType.AUDIO, command="test")
        job_manager.start_job(job.id, worker_pid=1)

        result = job_manager.update_progress(job.id, 75, "Transcribing audio...")

        assert result is True
        retrieved = job_manager.get_job(job.id)
        assert retrieved.progress == 75
        assert retrieved.progress_message == "Transcribing audio..."

    def test_update_progress_clamps_to_zero(self, job_manager):
        """Test that negative progress is clamped to 0."""
        job = job_manager.create_job(job_type=JobType.AUDIO, command="test")

        job_manager.update_progress(job.id, -10)

        retrieved = job_manager.get_job(job.id)
        assert retrieved.progress == 0

    def test_update_progress_clamps_to_hundred(self, job_manager):
        """Test that progress over 100 is clamped to 100."""
        job = job_manager.create_job(job_type=JobType.AUDIO, command="test")

        job_manager.update_progress(job.id, 150)

        retrieved = job_manager.get_job(job.id)
        assert retrieved.progress == 100

    def test_update_progress_nonexistent_job(self, job_manager):
        """Test updating progress of nonexistent job."""
        result = job_manager.update_progress("nonexistent", 50)
        assert result is False


class TestJobManagerStartJob:
    """Test JobManager.start_job()."""

    def test_start_job(self, job_manager):
        """Test starting a job."""
        job = job_manager.create_job(job_type=JobType.YOUTUBE, command="test")

        result = job_manager.start_job(job.id, worker_pid=12345)

        assert result is True
        retrieved = job_manager.get_job(job.id)
        assert retrieved.status == JobStatus.RUNNING
        assert retrieved.started_at is not None
        assert retrieved.worker_pid == 12345

    def test_start_nonexistent_job(self, job_manager):
        """Test starting a nonexistent job."""
        result = job_manager.start_job("nonexistent", worker_pid=12345)
        assert result is False


class TestJobManagerCompleteJob:
    """Test JobManager.complete_job()."""

    def test_complete_job(self, job_manager):
        """Test completing a job."""
        job = job_manager.create_job(job_type=JobType.YOUTUBE, command="test")
        job_manager.start_job(job.id, worker_pid=1)

        result = job_manager.complete_job(job.id, {"output": "/tmp/video.md"})

        assert result is True
        retrieved = job_manager.get_job(job.id)
        assert retrieved.status == JobStatus.COMPLETED
        assert retrieved.progress == 100
        assert retrieved.result == {"output": "/tmp/video.md"}
        assert retrieved.completed_at is not None

    def test_complete_nonexistent_job(self, job_manager):
        """Test completing a nonexistent job."""
        result = job_manager.complete_job("nonexistent", {"output": "test"})
        assert result is False


class TestJobManagerFailJob:
    """Test JobManager.fail_job()."""

    def test_fail_job(self, job_manager):
        """Test failing a job."""
        job = job_manager.create_job(job_type=JobType.YOUTUBE, command="test")
        job_manager.start_job(job.id, worker_pid=1)

        result = job_manager.fail_job(job.id, "Network error: connection refused")

        assert result is True
        retrieved = job_manager.get_job(job.id)
        assert retrieved.status == JobStatus.FAILED
        assert retrieved.error == "Network error: connection refused"
        assert retrieved.completed_at is not None

    def test_fail_nonexistent_job(self, job_manager):
        """Test failing a nonexistent job."""
        result = job_manager.fail_job("nonexistent", "error")
        assert result is False


class TestJobManagerCancelJob:
    """Test JobManager.cancel_job()."""

    def test_cancel_pending_job(self, job_manager):
        """Test cancelling a pending job."""
        job = job_manager.create_job(job_type=JobType.YOUTUBE, command="test")

        result = job_manager.cancel_job(job.id)

        assert result is True
        retrieved = job_manager.get_job(job.id)
        assert retrieved.status == JobStatus.CANCELLED
        assert retrieved.completed_at is not None

    def test_cancel_running_job(self, job_manager):
        """Test cancelling a running job (with mock SIGTERM)."""
        job = job_manager.create_job(job_type=JobType.YOUTUBE, command="test")
        job_manager.start_job(job.id, worker_pid=99999)

        with patch("os.kill") as mock_kill:
            result = job_manager.cancel_job(job.id)

            assert result is True
            mock_kill.assert_called_once()
            retrieved = job_manager.get_job(job.id)
            assert retrieved.status == JobStatus.CANCELLED

    def test_cancel_completed_job(self, job_manager):
        """Test that cancelling a completed job returns False."""
        job = job_manager.create_job(job_type=JobType.YOUTUBE, command="test")
        job_manager.complete_job(job.id, {"output": "test"})

        result = job_manager.cancel_job(job.id)

        assert result is False
        retrieved = job_manager.get_job(job.id)
        assert retrieved.status == JobStatus.COMPLETED

    def test_cancel_nonexistent_job(self, job_manager):
        """Test cancelling a nonexistent job."""
        result = job_manager.cancel_job("nonexistent")
        assert result is False

    def test_cancel_handles_process_not_found(self, job_manager):
        """Test that cancel handles ProcessLookupError gracefully."""
        job = job_manager.create_job(job_type=JobType.YOUTUBE, command="test")
        job_manager.start_job(job.id, worker_pid=99999)

        with patch("os.kill", side_effect=ProcessLookupError):
            result = job_manager.cancel_job(job.id)

            # Should still mark as cancelled
            assert result is True
            retrieved = job_manager.get_job(job.id)
            assert retrieved.status == JobStatus.CANCELLED


class TestJobManagerClearJobs:
    """Test JobManager.clear_jobs()."""

    def test_clear_all_jobs(self, job_manager):
        """Test clearing all jobs."""
        for i in range(5):
            job_manager.create_job(job_type=JobType.YOUTUBE, command=f"test {i}")

        count = job_manager.clear_jobs()

        assert count == 5
        jobs = job_manager.list_jobs()
        assert len(jobs) == 0

    def test_clear_jobs_by_status(self, job_manager):
        """Test clearing jobs by status."""
        job1 = job_manager.create_job(job_type=JobType.YOUTUBE, command="test1")
        job2 = job_manager.create_job(job_type=JobType.YOUTUBE, command="test2")
        job_manager.complete_job(job1.id, {})

        count = job_manager.clear_jobs(status=JobStatus.COMPLETED)

        assert count == 1
        jobs = job_manager.list_jobs()
        assert len(jobs) == 1
        assert jobs[0].id == job2.id

    def test_clear_old_jobs(self, job_manager):
        """Test clearing jobs older than N days."""
        # Create a job and manually set old created_at
        job = job_manager.create_job(job_type=JobType.YOUTUBE, command="test")

        old_date = (datetime.now(UTC) - timedelta(days=10)).isoformat()
        job_manager.database.execute(
            "UPDATE jobs SET created_at = ? WHERE id = ?",
            (old_date, job.id),
        )

        # Create a new job
        job_manager.create_job(job_type=JobType.YOUTUBE, command="new test")

        count = job_manager.clear_jobs(older_than_days=7)

        assert count == 1
        jobs = job_manager.list_jobs()
        assert len(jobs) == 1

    def test_clear_jobs_no_match(self, job_manager):
        """Test clearing jobs when none match criteria."""
        job_manager.create_job(job_type=JobType.YOUTUBE, command="test")

        count = job_manager.clear_jobs(status=JobStatus.FAILED)

        assert count == 0


class TestJobManagerGetPendingJobs:
    """Test JobManager.get_pending_jobs()."""

    def test_get_pending_jobs(self, job_manager):
        """Test getting pending jobs."""
        job1 = job_manager.create_job(job_type=JobType.YOUTUBE, command="test1")
        job2 = job_manager.create_job(job_type=JobType.YOUTUBE, command="test2")
        job_manager.start_job(job1.id, worker_pid=1)

        pending = job_manager.get_pending_jobs()

        assert len(pending) == 1
        assert pending[0].id == job2.id

    def test_get_pending_jobs_returns_full_job(self, job_manager):
        """Test that get_pending_jobs returns full Job objects."""
        job_manager.create_job(job_type=JobType.YOUTUBE, command="test")

        pending = job_manager.get_pending_jobs()

        assert len(pending) == 1
        assert isinstance(pending[0], Job)

    def test_get_pending_jobs_fifo_order(self, job_manager):
        """Test that pending jobs are returned in FIFO order."""
        ids = []
        for i in range(3):
            job = job_manager.create_job(job_type=JobType.YOUTUBE, command=f"test {i}")
            ids.append(job.id)
            time.sleep(0.01)

        pending = job_manager.get_pending_jobs()

        # Oldest job should be first
        assert pending[0].id == ids[0]
        assert pending[1].id == ids[1]
        assert pending[2].id == ids[2]

    def test_get_pending_jobs_with_limit(self, job_manager):
        """Test limiting pending jobs."""
        for i in range(10):
            job_manager.create_job(job_type=JobType.YOUTUBE, command=f"test {i}")

        pending = job_manager.get_pending_jobs(limit=3)

        assert len(pending) == 3

    def test_get_pending_jobs_empty(self, job_manager):
        """Test getting pending jobs when none exist."""
        pending = job_manager.get_pending_jobs()
        assert pending == []


class TestJobManagerCountJobs:
    """Test JobManager.count_jobs()."""

    def test_count_all_jobs(self, job_manager):
        """Test counting all jobs."""
        job1 = job_manager.create_job(job_type=JobType.YOUTUBE, command="test1")
        job2 = job_manager.create_job(job_type=JobType.YOUTUBE, command="test2")
        job_manager.start_job(job1.id, worker_pid=1)
        job_manager.complete_job(job2.id, {})

        counts = job_manager.count_jobs()

        assert counts["pending"] == 0
        assert counts["running"] == 1
        assert counts["completed"] == 1
        assert counts["failed"] == 0
        assert counts["cancelled"] == 0
        assert counts["total"] == 2

    def test_count_by_status(self, job_manager):
        """Test counting jobs by specific status."""
        for i in range(5):
            job_manager.create_job(job_type=JobType.YOUTUBE, command=f"test {i}")

        counts = job_manager.count_jobs(status=JobStatus.PENDING)

        assert counts["count"] == 5

    def test_count_empty_database(self, job_manager):
        """Test counting with no jobs."""
        counts = job_manager.count_jobs()

        assert counts["total"] == 0
        for status in JobStatus:
            assert counts[status.value] == 0


class TestJobManagerEdgeCases:
    """Test edge cases and error handling."""

    def test_job_with_unicode_command(self, job_manager):
        """Test job with unicode characters in command."""
        job = job_manager.create_job(
            job_type=JobType.YOUTUBE,
            command="gobbler youtube '日本語タイトル'",
            args={"title": "日本語タイトル"},
        )

        retrieved = job_manager.get_job(job.id)
        assert retrieved.command == "gobbler youtube '日本語タイトル'"
        assert retrieved.args == {"title": "日本語タイトル"}

    def test_job_with_large_args(self, job_manager):
        """Test job with large args dictionary."""
        large_args = {f"key_{i}": f"value_{i}" * 100 for i in range(100)}
        job = job_manager.create_job(
            job_type=JobType.BATCH_YOUTUBE,
            command="test",
            args=large_args,
        )

        retrieved = job_manager.get_job(job.id)
        assert retrieved.args == large_args

    def test_job_with_nested_result(self, job_manager):
        """Test job with deeply nested result."""
        job = job_manager.create_job(job_type=JobType.CRAWL, command="test")

        nested_result = {
            "level1": {
                "level2": {
                    "level3": {
                        "data": [1, 2, 3],
                        "nested_list": [[1, 2], [3, 4]],
                    }
                }
            }
        }
        job_manager.complete_job(job.id, nested_result)

        retrieved = job_manager.get_job(job.id)
        assert retrieved.result == nested_result

    def test_concurrent_job_updates(self, job_manager):
        """Test concurrent updates to the same job."""
        job = job_manager.create_job(job_type=JobType.AUDIO, command="test")
        errors = []

        def update_progress(progress):
            try:
                job_manager.update_progress(job.id, progress, f"Progress: {progress}%")
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=update_progress, args=(i * 10,)) for i in range(10)]

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # No errors should occur due to WAL mode
        assert len(errors) == 0

        # Job should still be retrievable
        retrieved = job_manager.get_job(job.id)
        assert retrieved is not None

    def test_special_characters_in_error(self, job_manager):
        """Test job with special characters in error message."""
        job = job_manager.create_job(job_type=JobType.WEBPAGE, command="test")

        error_msg = "Error: <script>alert('XSS')</script> & special chars: \"'\\"
        job_manager.fail_job(job.id, error_msg)

        retrieved = job_manager.get_job(job.id)
        assert retrieved.error == error_msg

    def test_empty_result_dict(self, job_manager):
        """Test completing job with empty result dict."""
        job = job_manager.create_job(job_type=JobType.YOUTUBE, command="test")

        job_manager.complete_job(job.id, {})

        retrieved = job_manager.get_job(job.id)
        assert retrieved.result == {}
