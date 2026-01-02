"""Job queue management tools.

Tools for managing background job queues:
- get_job_status: Check status and result of queued jobs
- list_jobs: List jobs in a queue

These tools use the SQLite-based gobbler_queue system.
"""

import logging
from fastmcp import FastMCP

from ..constants import MAX_JOBS_LIST, DEFAULT_JOBS_LIST

logger = logging.getLogger(__name__)


def register_tools(mcp: FastMCP):
    """Register queue management tools with the MCP server."""

    @mcp.tool()
    async def get_job_status(job_id: str) -> str:
        """
        Check status and result of a queued job.

        Retrieves current status, progress, and result (if completed) for a job
        that was queued via the job queue system.

        Args:
            job_id: Job ID returned when task was queued

        Returns:
            Job status information including:
            - Current status (pending/running/completed/failed/cancelled)
            - Progress information
            - Result (if completed)
            - Error message (if failed)
        """
        try:
            from gobbler_queue.manager import JobManager

            manager = JobManager()
            job = manager.get_job(job_id)

            if job is None:
                return f"Job not found: {job_id}"

            # Format response based on status
            status = job.status.value
            result = [f"Job ID: {job_id}", f"Status: {status.upper()}"]

            if job.status.value == "pending":
                result.append("Waiting to start...")

            elif job.status.value == "running":
                result.append("Job is currently running...")
                if job.progress is not None:
                    result.append(f"Progress: {job.progress}%")
                if job.progress_message:
                    result.append(f"Current: {job.progress_message}")

            elif job.status.value == "completed":
                result.append("✅ Job completed successfully")
                if job.result:
                    result.append(f"\nResult:\n{job.result}")

            elif job.status.value == "failed":
                result.append("❌ Job failed")
                if job.error:
                    result.append(f"Error: {job.error}")

            elif job.status.value == "cancelled":
                result.append("⏹️ Job was cancelled")

            # Add timing info
            if job.created_at:
                result.append(f"\nCreated: {job.created_at.isoformat()}")
            if job.started_at:
                result.append(f"Started: {job.started_at.isoformat()}")
            if job.completed_at:
                result.append(f"Finished: {job.completed_at.isoformat()}")

            return "\n".join(result)

        except ImportError:
            return "Job queue system not available. Use 'gobbler jobs get' CLI command instead."
        except Exception as e:
            logger.error(f"Error getting job status: {e}", exc_info=True)
            return f"Failed to get job status: {str(e)}"

    @mcp.tool()
    async def list_jobs(
        status: str = "all",
        limit: int = DEFAULT_JOBS_LIST,
    ) -> str:
        """
        List jobs in the queue.

        Shows recent jobs with their current status.
        Useful for monitoring background tasks.

        Args:
            status: Filter by status - 'all', 'pending', 'running', 'completed', 'failed', 'cancelled' (default: 'all')
            limit: Maximum number of jobs to return (default: 20, max: 100)

        Returns:
            List of jobs with status, ID, and created time
        """
        try:
            from gobbler_queue.manager import JobManager
            from gobbler_queue.models import JobStatus

            manager = JobManager()

            if limit > MAX_JOBS_LIST:
                limit = MAX_JOBS_LIST

            # Convert status string to enum if filtering
            status_filter = None
            if status != "all":
                try:
                    status_filter = JobStatus(status)
                except ValueError:
                    return f"Invalid status: {status}. Use: all, pending, running, completed, failed, cancelled"

            jobs = manager.list_jobs(status=status_filter, limit=limit)

            if not jobs:
                filter_msg = f" with status '{status}'" if status != "all" else ""
                return f"No jobs found{filter_msg}"

            result = [f"Jobs (showing up to {limit}):\n"]

            for job_summary in jobs:
                status_icon = {
                    "pending": "⏳",
                    "running": "🔄",
                    "completed": "✅",
                    "failed": "❌",
                    "cancelled": "⏹️",
                }.get(job_summary.status.value, "❓")

                result.append(f"{status_icon} {job_summary.status.value.upper()}: {job_summary.id}")
                result.append(f"   Type: {job_summary.job_type.value}")
                result.append(f"   Created: {job_summary.created_at.isoformat()}")

                if job_summary.error:
                    result.append(f"   Error: {job_summary.error}")

                result.append("")

            return "\n".join(result)

        except ImportError:
            return "Job queue system not available. Use 'gobbler jobs list' CLI command instead."
        except Exception as e:
            logger.error(f"Error listing jobs: {e}", exc_info=True)
            return f"Failed to list jobs: {str(e)}"
