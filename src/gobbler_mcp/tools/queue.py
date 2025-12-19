"""Job queue management tools.

Tools for managing background job queues:
- get_job_status: Check status and result of queued jobs
- list_jobs: List jobs in a queue
"""

import logging
from fastmcp import FastMCP

from ..constants import MAX_JOBS_LIST, DEFAULT_JOBS_LIST
from ..utils.queue import get_job_info, list_jobs_in_queue

logger = logging.getLogger(__name__)


def register_tools(mcp: FastMCP):
    """Register queue management tools with the MCP server."""

    @mcp.tool()
    async def get_job_status(job_id: str) -> str:
        """
        Check status and result of a queued job.

        Retrieves current status, progress, and result (if completed) for a job
        that was queued via auto_queue flag.

        Args:
            job_id: Job ID returned when task was queued

        Returns:
            Job status information including:
            - Current status (queued/started/finished/failed)
            - Progress information
            - Result (if completed)
            - Error message (if failed)
        """
        try:
            job_info = get_job_info(job_id)
            if job_info is None:
                return f"Job not found: {job_id}"

            # Format response based on status
            status = job_info["status"]
            result = [f"Job ID: {job_id}", f"Status: {status}"]

            if status == "queued":
                position = job_info.get("queue_position", "unknown")
                result.append(f"Queue position: {position}")
                result.append("Waiting to start...")

            elif status == "started":
                result.append("Job is currently running...")
                if job_info.get("progress"):
                    result.append(f"Progress: {job_info['progress']}")

            elif status == "finished":
                result.append("✅ Job completed successfully")
                if job_info.get("result"):
                    result.append(f"\nResult:\n{job_info['result']}")

            elif status == "failed":
                result.append("❌ Job failed")
                if job_info.get("error"):
                    result.append(f"Error: {job_info['error']}")

            return "\n".join(result)

        except Exception as e:
            logger.error(f"Error getting job status: {e}", exc_info=True)
            return f"Failed to get job status: {str(e)}"

    @mcp.tool()
    async def list_jobs(queue_name: str = "default", limit: int = DEFAULT_JOBS_LIST) -> str:
        """
        List jobs in a queue.

        Shows recent jobs in the specified queue with their current status.
        Useful for monitoring background tasks.

        Args:
            queue_name: Queue to list jobs from (default: 'default', options: 'transcription', 'download')
            limit: Maximum number of jobs to return (default: 20, max: 100)

        Returns:
            List of jobs with status, ID, and created time
        """
        try:
            if limit > MAX_JOBS_LIST:
                limit = MAX_JOBS_LIST

            jobs = list_jobs_in_queue(queue_name, limit)

            if not jobs:
                return f"No jobs found in queue '{queue_name}'"

            result = [f"Jobs in queue '{queue_name}' (showing up to {limit}):\n"]

            for job_data in jobs:
                status_icon = {
                    "queued": "⏳",
                    "started": "🔄",
                    "finished": "✅",
                    "failed": "❌",
                }.get(job_data["status"], "❓")

                result.append(
                    f"{status_icon} {job_data['status'].upper()}: {job_data['id']}"
                )
                result.append(f"   Created: {job_data['created_at']}")

                if job_data["status"] == "queued" and job_data.get("queue_position"):
                    result.append(f"   Position: {job_data['queue_position']}")

                result.append("")

            return "\n".join(result)

        except Exception as e:
            logger.error(f"Error listing jobs: {e}", exc_info=True)
            return f"Failed to list jobs: {str(e)}"
