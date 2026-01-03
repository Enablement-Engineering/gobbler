"""Unit tests for job queue MCP tools.

Tests the queue tools module with mocked JobManager.
All tests run without requiring actual database or queue system.
"""

import sys
from datetime import datetime
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from fastmcp import FastMCP

# Mock the problematic audio module before any gobbler_mcp imports
sys.modules["gobbler_mcp.converters.audio"] = MagicMock()

from gobbler_mcp.tools.queue import register_tools
from gobbler_queue.models import Job, JobStatus, JobSummary, JobType


@pytest.fixture
def mcp():
    """Create a FastMCP instance with queue tools registered."""
    mcp_server = FastMCP("test-queue")
    register_tools(mcp_server)
    return mcp_server


@pytest.fixture
def mock_job_manager():
    """Create a mock JobManager instance."""
    return MagicMock()


def create_mock_job(
    job_id: str = "test-job-123",
    status: JobStatus = JobStatus.PENDING,
    job_type: JobType = JobType.YOUTUBE,
    progress: int = 0,
    progress_message: str = "",
    result: Any | None = None,
    error: str | None = None,
    created_at: datetime | None = None,
    started_at: datetime | None = None,
    completed_at: datetime | None = None,
) -> Job:
    """Create a mock Job instance with specified attributes."""
    return Job(
        id=job_id,
        job_type=job_type,
        status=status,
        command="gobbler youtube https://example.com",
        args={},
        progress=progress,
        progress_message=progress_message,
        result=result,
        error=error,
        created_at=created_at or datetime(2025, 1, 1, 12, 0, 0),
        started_at=started_at,
        completed_at=completed_at,
    )


def create_mock_job_summary(
    job_id: str = "test-job-123",
    status: JobStatus = JobStatus.PENDING,
    job_type: JobType = JobType.YOUTUBE,
    progress: int = 0,
    progress_message: str = "",
    error: str | None = None,
    created_at: datetime | None = None,
) -> JobSummary:
    """Create a mock JobSummary instance with specified attributes."""
    return JobSummary(
        id=job_id,
        job_type=job_type,
        status=status,
        progress=progress,
        progress_message=progress_message,
        created_at=created_at or datetime(2025, 1, 1, 12, 0, 0),
        error=error,
    )


class TestGetJobStatus:
    """Tests for get_job_status tool."""

    @pytest.mark.asyncio
    async def test_pending_job(self, mcp, mock_job_manager):
        """Test get_job_status returns correct info for pending job."""
        job = create_mock_job(
            job_id="pending-123",
            status=JobStatus.PENDING,
        )
        mock_job_manager.get_job.return_value = job

        with patch(
            "gobbler_queue.manager.JobManager",
            return_value=mock_job_manager,
        ):
            tool = mcp._tool_manager._tools["get_job_status"]
            result = await tool.fn(job_id="pending-123")

        assert "Job ID: pending-123" in result
        assert "Status: PENDING" in result
        assert "Waiting to start..." in result
        mock_job_manager.get_job.assert_called_once_with("pending-123")

    @pytest.mark.asyncio
    async def test_running_job_without_progress(self, mcp, mock_job_manager):
        """Test get_job_status returns correct info for running job without progress."""
        job = create_mock_job(
            job_id="running-123",
            status=JobStatus.RUNNING,
            started_at=datetime(2025, 1, 1, 12, 5, 0),
        )
        mock_job_manager.get_job.return_value = job

        with patch(
            "gobbler_queue.manager.JobManager",
            return_value=mock_job_manager,
        ):
            tool = mcp._tool_manager._tools["get_job_status"]
            result = await tool.fn(job_id="running-123")

        assert "Job ID: running-123" in result
        assert "Status: RUNNING" in result
        assert "Job is currently running..." in result
        assert "Started: 2025-01-01T12:05:00" in result

    @pytest.mark.asyncio
    async def test_running_job_with_progress(self, mcp, mock_job_manager):
        """Test get_job_status returns progress info for running job."""
        job = create_mock_job(
            job_id="running-456",
            status=JobStatus.RUNNING,
            progress=50,
            progress_message="Downloading video...",
            started_at=datetime(2025, 1, 1, 12, 5, 0),
        )
        mock_job_manager.get_job.return_value = job

        with patch(
            "gobbler_queue.manager.JobManager",
            return_value=mock_job_manager,
        ):
            tool = mcp._tool_manager._tools["get_job_status"]
            result = await tool.fn(job_id="running-456")

        assert "Status: RUNNING" in result
        assert "Progress: 50%" in result
        assert "Current: Downloading video..." in result

    @pytest.mark.asyncio
    async def test_completed_job_without_result(self, mcp, mock_job_manager):
        """Test get_job_status returns correct info for completed job without result."""
        job = create_mock_job(
            job_id="completed-123",
            status=JobStatus.COMPLETED,
            started_at=datetime(2025, 1, 1, 12, 5, 0),
            completed_at=datetime(2025, 1, 1, 12, 10, 0),
        )
        mock_job_manager.get_job.return_value = job

        with patch(
            "gobbler_queue.manager.JobManager",
            return_value=mock_job_manager,
        ):
            tool = mcp._tool_manager._tools["get_job_status"]
            result = await tool.fn(job_id="completed-123")

        assert "Job ID: completed-123" in result
        assert "Status: COMPLETED" in result
        assert "Job completed successfully" in result
        assert "Finished: 2025-01-01T12:10:00" in result

    @pytest.mark.asyncio
    async def test_completed_job_with_result(self, mcp, mock_job_manager):
        """Test get_job_status returns result for completed job."""
        job = create_mock_job(
            job_id="completed-456",
            status=JobStatus.COMPLETED,
            result="Video transcribed successfully to /output/video.md",
            started_at=datetime(2025, 1, 1, 12, 5, 0),
            completed_at=datetime(2025, 1, 1, 12, 10, 0),
        )
        mock_job_manager.get_job.return_value = job

        with patch(
            "gobbler_queue.manager.JobManager",
            return_value=mock_job_manager,
        ):
            tool = mcp._tool_manager._tools["get_job_status"]
            result = await tool.fn(job_id="completed-456")

        assert "Status: COMPLETED" in result
        assert "Result:" in result
        assert "Video transcribed successfully" in result

    @pytest.mark.asyncio
    async def test_failed_job_without_error(self, mcp, mock_job_manager):
        """Test get_job_status returns correct info for failed job without error message."""
        job = create_mock_job(
            job_id="failed-123",
            status=JobStatus.FAILED,
            started_at=datetime(2025, 1, 1, 12, 5, 0),
            completed_at=datetime(2025, 1, 1, 12, 6, 0),
        )
        mock_job_manager.get_job.return_value = job

        with patch(
            "gobbler_queue.manager.JobManager",
            return_value=mock_job_manager,
        ):
            tool = mcp._tool_manager._tools["get_job_status"]
            result = await tool.fn(job_id="failed-123")

        assert "Job ID: failed-123" in result
        assert "Status: FAILED" in result
        assert "Job failed" in result

    @pytest.mark.asyncio
    async def test_failed_job_with_error(self, mcp, mock_job_manager):
        """Test get_job_status returns error message for failed job."""
        job = create_mock_job(
            job_id="failed-456",
            status=JobStatus.FAILED,
            error="Video unavailable: Private video",
            started_at=datetime(2025, 1, 1, 12, 5, 0),
            completed_at=datetime(2025, 1, 1, 12, 6, 0),
        )
        mock_job_manager.get_job.return_value = job

        with patch(
            "gobbler_queue.manager.JobManager",
            return_value=mock_job_manager,
        ):
            tool = mcp._tool_manager._tools["get_job_status"]
            result = await tool.fn(job_id="failed-456")

        assert "Status: FAILED" in result
        assert "Job failed" in result
        assert "Error: Video unavailable: Private video" in result

    @pytest.mark.asyncio
    async def test_cancelled_job(self, mcp, mock_job_manager):
        """Test get_job_status returns correct info for cancelled job."""
        job = create_mock_job(
            job_id="cancelled-123",
            status=JobStatus.CANCELLED,
            started_at=datetime(2025, 1, 1, 12, 5, 0),
            completed_at=datetime(2025, 1, 1, 12, 7, 0),
        )
        mock_job_manager.get_job.return_value = job

        with patch(
            "gobbler_queue.manager.JobManager",
            return_value=mock_job_manager,
        ):
            tool = mcp._tool_manager._tools["get_job_status"]
            result = await tool.fn(job_id="cancelled-123")

        assert "Job ID: cancelled-123" in result
        assert "Status: CANCELLED" in result
        assert "Job was cancelled" in result

    @pytest.mark.asyncio
    async def test_nonexistent_job(self, mcp, mock_job_manager):
        """Test get_job_status with non-existent job ID."""
        mock_job_manager.get_job.return_value = None

        with patch(
            "gobbler_queue.manager.JobManager",
            return_value=mock_job_manager,
        ):
            tool = mcp._tool_manager._tools["get_job_status"]
            result = await tool.fn(job_id="nonexistent-999")

        assert "Job not found: nonexistent-999" in result
        mock_job_manager.get_job.assert_called_once_with("nonexistent-999")

    @pytest.mark.asyncio
    async def test_import_error(self, mcp):
        """Test get_job_status when JobManager import fails."""
        # Remove gobbler_queue.manager from sys.modules to simulate import failure
        with patch.dict(
            sys.modules,
            {"gobbler_queue.manager": None},
        ):
            tool = mcp._tool_manager._tools["get_job_status"]
            result = await tool.fn(job_id="test-123")

        assert "Job queue system not available" in result
        assert "gobbler jobs get" in result

    @pytest.mark.asyncio
    async def test_general_exception(self, mcp, mock_job_manager):
        """Test get_job_status handles general exceptions."""
        mock_job_manager.get_job.side_effect = Exception("Database connection failed")

        with patch(
            "gobbler_queue.manager.JobManager",
            return_value=mock_job_manager,
        ):
            tool = mcp._tool_manager._tools["get_job_status"]
            result = await tool.fn(job_id="test-123")

        assert "Failed to get job status" in result
        assert "Database connection failed" in result


class TestListJobs:
    """Tests for list_jobs tool."""

    @pytest.mark.asyncio
    async def test_list_all_jobs(self, mcp, mock_job_manager):
        """Test list_jobs returns all jobs when no filter."""
        mock_job_manager.list_jobs.return_value = [
            create_mock_job_summary(
                job_id="job-1",
                status=JobStatus.PENDING,
                job_type=JobType.YOUTUBE,
            ),
            create_mock_job_summary(
                job_id="job-2",
                status=JobStatus.RUNNING,
                job_type=JobType.AUDIO,
            ),
            create_mock_job_summary(
                job_id="job-3",
                status=JobStatus.COMPLETED,
                job_type=JobType.DOCUMENT,
            ),
        ]

        with patch(
            "gobbler_queue.manager.JobManager",
            return_value=mock_job_manager,
        ):
            tool = mcp._tool_manager._tools["list_jobs"]
            result = await tool.fn()

        assert "Jobs (showing up to 20):" in result
        assert "PENDING: job-1" in result
        assert "RUNNING: job-2" in result
        assert "COMPLETED: job-3" in result
        assert "Type: youtube" in result
        assert "Type: audio" in result
        assert "Type: document" in result
        mock_job_manager.list_jobs.assert_called_once_with(status=None, limit=20)

    @pytest.mark.asyncio
    async def test_list_jobs_filter_by_status_pending(self, mcp, mock_job_manager):
        """Test list_jobs filters by pending status correctly."""
        mock_job_manager.list_jobs.return_value = [
            create_mock_job_summary(
                job_id="pending-1",
                status=JobStatus.PENDING,
            ),
            create_mock_job_summary(
                job_id="pending-2",
                status=JobStatus.PENDING,
            ),
        ]

        with patch(
            "gobbler_queue.manager.JobManager",
            return_value=mock_job_manager,
        ):
            tool = mcp._tool_manager._tools["list_jobs"]
            result = await tool.fn(status="pending")

        assert "pending-1" in result
        assert "pending-2" in result
        mock_job_manager.list_jobs.assert_called_once_with(status=JobStatus.PENDING, limit=20)

    @pytest.mark.asyncio
    async def test_list_jobs_filter_by_status_running(self, mcp, mock_job_manager):
        """Test list_jobs filters by running status correctly."""
        mock_job_manager.list_jobs.return_value = [
            create_mock_job_summary(
                job_id="running-1",
                status=JobStatus.RUNNING,
            ),
        ]

        with patch(
            "gobbler_queue.manager.JobManager",
            return_value=mock_job_manager,
        ):
            tool = mcp._tool_manager._tools["list_jobs"]
            result = await tool.fn(status="running")

        assert "RUNNING: running-1" in result
        mock_job_manager.list_jobs.assert_called_once_with(status=JobStatus.RUNNING, limit=20)

    @pytest.mark.asyncio
    async def test_list_jobs_filter_by_status_completed(self, mcp, mock_job_manager):
        """Test list_jobs filters by completed status correctly."""
        mock_job_manager.list_jobs.return_value = [
            create_mock_job_summary(
                job_id="completed-1",
                status=JobStatus.COMPLETED,
            ),
        ]

        with patch(
            "gobbler_queue.manager.JobManager",
            return_value=mock_job_manager,
        ):
            tool = mcp._tool_manager._tools["list_jobs"]
            result = await tool.fn(status="completed")

        assert "COMPLETED: completed-1" in result
        mock_job_manager.list_jobs.assert_called_once_with(status=JobStatus.COMPLETED, limit=20)

    @pytest.mark.asyncio
    async def test_list_jobs_filter_by_status_failed(self, mcp, mock_job_manager):
        """Test list_jobs filters by failed status correctly."""
        mock_job_manager.list_jobs.return_value = [
            create_mock_job_summary(
                job_id="failed-1",
                status=JobStatus.FAILED,
                error="Network error",
            ),
        ]

        with patch(
            "gobbler_queue.manager.JobManager",
            return_value=mock_job_manager,
        ):
            tool = mcp._tool_manager._tools["list_jobs"]
            result = await tool.fn(status="failed")

        assert "FAILED: failed-1" in result
        assert "Error: Network error" in result
        mock_job_manager.list_jobs.assert_called_once_with(status=JobStatus.FAILED, limit=20)

    @pytest.mark.asyncio
    async def test_list_jobs_filter_by_status_cancelled(self, mcp, mock_job_manager):
        """Test list_jobs filters by cancelled status correctly."""
        mock_job_manager.list_jobs.return_value = [
            create_mock_job_summary(
                job_id="cancelled-1",
                status=JobStatus.CANCELLED,
            ),
        ]

        with patch(
            "gobbler_queue.manager.JobManager",
            return_value=mock_job_manager,
        ):
            tool = mcp._tool_manager._tools["list_jobs"]
            result = await tool.fn(status="cancelled")

        assert "CANCELLED: cancelled-1" in result
        mock_job_manager.list_jobs.assert_called_once_with(status=JobStatus.CANCELLED, limit=20)

    @pytest.mark.asyncio
    async def test_list_jobs_empty_results(self, mcp, mock_job_manager):
        """Test list_jobs with empty results."""
        mock_job_manager.list_jobs.return_value = []

        with patch(
            "gobbler_queue.manager.JobManager",
            return_value=mock_job_manager,
        ):
            tool = mcp._tool_manager._tools["list_jobs"]
            result = await tool.fn()

        assert "No jobs found" in result

    @pytest.mark.asyncio
    async def test_list_jobs_empty_results_with_filter(self, mcp, mock_job_manager):
        """Test list_jobs with empty results and status filter."""
        mock_job_manager.list_jobs.return_value = []

        with patch(
            "gobbler_queue.manager.JobManager",
            return_value=mock_job_manager,
        ):
            tool = mcp._tool_manager._tools["list_jobs"]
            result = await tool.fn(status="running")

        assert "No jobs found with status 'running'" in result

    @pytest.mark.asyncio
    async def test_list_jobs_invalid_status(self, mcp, mock_job_manager):
        """Test list_jobs with invalid status filter."""
        with patch(
            "gobbler_queue.manager.JobManager",
            return_value=mock_job_manager,
        ):
            tool = mcp._tool_manager._tools["list_jobs"]
            result = await tool.fn(status="invalid")

        assert "Invalid status: invalid" in result
        assert "pending, running, completed, failed, cancelled" in result

    @pytest.mark.asyncio
    async def test_list_jobs_custom_limit(self, mcp, mock_job_manager):
        """Test list_jobs with custom limit."""
        mock_job_manager.list_jobs.return_value = [
            create_mock_job_summary(job_id=f"job-{i}", status=JobStatus.PENDING) for i in range(5)
        ]

        with patch(
            "gobbler_queue.manager.JobManager",
            return_value=mock_job_manager,
        ):
            tool = mcp._tool_manager._tools["list_jobs"]
            result = await tool.fn(limit=5)

        assert "Jobs (showing up to 5):" in result
        mock_job_manager.list_jobs.assert_called_once_with(status=None, limit=5)

    @pytest.mark.asyncio
    async def test_list_jobs_limit_capped_at_max(self, mcp, mock_job_manager):
        """Test list_jobs limits are capped at MAX_JOBS_LIST (100)."""
        mock_job_manager.list_jobs.return_value = []

        with patch(
            "gobbler_queue.manager.JobManager",
            return_value=mock_job_manager,
        ):
            tool = mcp._tool_manager._tools["list_jobs"]
            await tool.fn(limit=500)

        # Should be capped to 100 (MAX_JOBS_LIST)
        mock_job_manager.list_jobs.assert_called_once_with(status=None, limit=100)

    @pytest.mark.asyncio
    async def test_list_jobs_status_icons(self, mcp, mock_job_manager):
        """Test list_jobs displays correct status icons."""
        mock_job_manager.list_jobs.return_value = [
            create_mock_job_summary(job_id="pending-1", status=JobStatus.PENDING),
            create_mock_job_summary(job_id="running-1", status=JobStatus.RUNNING),
            create_mock_job_summary(job_id="completed-1", status=JobStatus.COMPLETED),
            create_mock_job_summary(job_id="failed-1", status=JobStatus.FAILED),
            create_mock_job_summary(job_id="cancelled-1", status=JobStatus.CANCELLED),
        ]

        with patch(
            "gobbler_queue.manager.JobManager",
            return_value=mock_job_manager,
        ):
            tool = mcp._tool_manager._tools["list_jobs"]
            result = await tool.fn()

        # Check status icons are present
        assert "⏳ PENDING" in result
        assert "🔄 RUNNING" in result
        assert "✅ COMPLETED" in result
        assert "❌ FAILED" in result
        assert "⏹️ CANCELLED" in result

    @pytest.mark.asyncio
    async def test_list_jobs_import_error(self, mcp):
        """Test list_jobs when JobManager import fails."""
        with patch.dict(
            sys.modules,
            {"gobbler_queue.manager": None},
        ):
            tool = mcp._tool_manager._tools["list_jobs"]
            result = await tool.fn()

        assert "Job queue system not available" in result
        assert "gobbler jobs list" in result

    @pytest.mark.asyncio
    async def test_list_jobs_general_exception(self, mcp, mock_job_manager):
        """Test list_jobs handles general exceptions."""
        mock_job_manager.list_jobs.side_effect = Exception("Database connection failed")

        with patch(
            "gobbler_queue.manager.JobManager",
            return_value=mock_job_manager,
        ):
            tool = mcp._tool_manager._tools["list_jobs"]
            result = await tool.fn()

        assert "Failed to list jobs" in result
        assert "Database connection failed" in result

    @pytest.mark.asyncio
    async def test_list_jobs_shows_created_at(self, mcp, mock_job_manager):
        """Test list_jobs displays created_at timestamp."""
        mock_job_manager.list_jobs.return_value = [
            create_mock_job_summary(
                job_id="job-1",
                status=JobStatus.PENDING,
                created_at=datetime(2025, 1, 15, 10, 30, 0),
            ),
        ]

        with patch(
            "gobbler_queue.manager.JobManager",
            return_value=mock_job_manager,
        ):
            tool = mcp._tool_manager._tools["list_jobs"]
            result = await tool.fn()

        assert "Created: 2025-01-15T10:30:00" in result

    @pytest.mark.asyncio
    async def test_list_jobs_shows_job_type(self, mcp, mock_job_manager):
        """Test list_jobs displays job type for each job."""
        mock_job_manager.list_jobs.return_value = [
            create_mock_job_summary(
                job_id="job-1",
                status=JobStatus.PENDING,
                job_type=JobType.BATCH_YOUTUBE,
            ),
            create_mock_job_summary(
                job_id="job-2",
                status=JobStatus.RUNNING,
                job_type=JobType.CRAWL,
            ),
        ]

        with patch(
            "gobbler_queue.manager.JobManager",
            return_value=mock_job_manager,
        ):
            tool = mcp._tool_manager._tools["list_jobs"]
            result = await tool.fn()

        assert "Type: batch_youtube" in result
        assert "Type: crawl" in result
