"""Jobs namespace for Gobbler SDK.

This module provides methods for managing background jobs.
"""

from typing import TYPE_CHECKING, Any

from gobbler_sdk.exceptions import JobError
from gobbler_sdk.types import JobStatus

if TYPE_CHECKING:
    import httpx


class JobsNamespace:
    """Namespace for job management operations.

    This class provides methods for managing background jobs,
    including getting status, cancelling, and listing jobs.
    """

    def __init__(self, client: "httpx.Client", base_url: str) -> None:
        """Initialize the jobs namespace.

        Args:
            client: httpx Client instance for making requests
            base_url: Base URL of the Gobbler daemon API
        """
        self._client = client
        self._base_url = base_url

    def _parse_job_status(self, response_data: dict[str, Any]) -> JobStatus:
        """Parse API response into JobStatus.

        Args:
            response_data: Raw response data from API

        Returns:
            Parsed JobStatus
        """
        return JobStatus(
            job_id=response_data.get("job_id", ""),
            status=response_data.get("status", "queued"),
            queue_name=response_data.get("queue_name"),
            enqueued_at=response_data.get("enqueued_at"),
            started_at=response_data.get("started_at"),
            ended_at=response_data.get("ended_at"),
            progress=response_data.get("progress", 0.0),
            result=response_data.get("result"),
            error=response_data.get("error"),
            exc_info=response_data.get("exc_info"),
        )

    def get(self, job_id: str) -> JobStatus:
        """Get status of a specific job.

        Args:
            job_id: Job ID to query

        Returns:
            JobStatus with current job information

        Raises:
            JobError: If the job cannot be found or query fails
            ConnectionError: If unable to connect to daemon
        """
        try:
            response = self._client.get(f"{self._base_url}/jobs/{job_id}")
            response.raise_for_status()
            return self._parse_job_status(response.json())
        except Exception as e:
            error_msg = str(e)
            if hasattr(e, "response") and hasattr(e.response, "json"):
                try:
                    error_data = e.response.json()
                    error_msg = error_data.get("error", error_msg)
                except Exception:
                    pass
            raise JobError(f"Failed to get job status: {error_msg}", job_id=job_id) from e

    def cancel(self, job_id: str) -> JobStatus:
        """Cancel a running or queued job.

        Args:
            job_id: Job ID to cancel

        Returns:
            JobStatus after cancellation

        Raises:
            JobError: If the job cannot be cancelled
            ConnectionError: If unable to connect to daemon
        """
        try:
            response = self._client.delete(f"{self._base_url}/jobs/{job_id}")
            response.raise_for_status()
            return self._parse_job_status(response.json())
        except Exception as e:
            error_msg = str(e)
            if hasattr(e, "response") and hasattr(e.response, "json"):
                try:
                    error_data = e.response.json()
                    error_msg = error_data.get("error", error_msg)
                except Exception:
                    pass
            raise JobError(f"Failed to cancel job: {error_msg}", job_id=job_id) from e

    def list(
        self, queue_name: str | None = None, status: str | None = None, limit: int = 100
    ) -> list[JobStatus]:
        """List jobs with optional filtering.

        Args:
            queue_name: Filter by queue name
            status: Filter by job status (queued, started, finished, failed, cancelled)
            limit: Maximum number of jobs to return

        Returns:
            List of JobStatus objects

        Raises:
            JobError: If the query fails
            ConnectionError: If unable to connect to daemon
        """
        try:
            params = {"limit": limit}
            if queue_name:
                params["queue"] = queue_name
            if status:
                params["status"] = status

            response = self._client.get(f"{self._base_url}/jobs", params=params)
            response.raise_for_status()

            jobs_data = response.json().get("jobs", [])
            return [self._parse_job_status(job) for job in jobs_data]
        except Exception as e:
            error_msg = str(e)
            if hasattr(e, "response") and hasattr(e.response, "json"):
                try:
                    error_data = e.response.json()
                    error_msg = error_data.get("error", error_msg)
                except Exception:
                    pass
            raise JobError(f"Failed to list jobs: {error_msg}") from e


class AsyncJobsNamespace:
    """Async namespace for job management operations.

    This class provides async methods for managing background jobs,
    including getting status, cancelling, and listing jobs.
    """

    def __init__(self, client: "httpx.AsyncClient", base_url: str) -> None:
        """Initialize the async jobs namespace.

        Args:
            client: httpx AsyncClient instance for making requests
            base_url: Base URL of the Gobbler daemon API
        """
        self._client = client
        self._base_url = base_url

    def _parse_job_status(self, response_data: dict[str, Any]) -> JobStatus:
        """Parse API response into JobStatus.

        Args:
            response_data: Raw response data from API

        Returns:
            Parsed JobStatus
        """
        return JobStatus(
            job_id=response_data.get("job_id", ""),
            status=response_data.get("status", "queued"),
            queue_name=response_data.get("queue_name"),
            enqueued_at=response_data.get("enqueued_at"),
            started_at=response_data.get("started_at"),
            ended_at=response_data.get("ended_at"),
            progress=response_data.get("progress", 0.0),
            result=response_data.get("result"),
            error=response_data.get("error"),
            exc_info=response_data.get("exc_info"),
        )

    async def get(self, job_id: str) -> JobStatus:
        """Get status of a specific job.

        Args:
            job_id: Job ID to query

        Returns:
            JobStatus with current job information

        Raises:
            JobError: If the job cannot be found or query fails
            ConnectionError: If unable to connect to daemon
        """
        try:
            response = await self._client.get(f"{self._base_url}/jobs/{job_id}")
            response.raise_for_status()
            return self._parse_job_status(response.json())
        except Exception as e:
            error_msg = str(e)
            if hasattr(e, "response") and hasattr(e.response, "json"):
                try:
                    error_data = e.response.json()
                    error_msg = error_data.get("error", error_msg)
                except Exception:
                    pass
            raise JobError(f"Failed to get job status: {error_msg}", job_id=job_id) from e

    async def cancel(self, job_id: str) -> JobStatus:
        """Cancel a running or queued job.

        Args:
            job_id: Job ID to cancel

        Returns:
            JobStatus after cancellation

        Raises:
            JobError: If the job cannot be cancelled
            ConnectionError: If unable to connect to daemon
        """
        try:
            response = await self._client.delete(f"{self._base_url}/jobs/{job_id}")
            response.raise_for_status()
            return self._parse_job_status(response.json())
        except Exception as e:
            error_msg = str(e)
            if hasattr(e, "response") and hasattr(e.response, "json"):
                try:
                    error_data = e.response.json()
                    error_msg = error_data.get("error", error_msg)
                except Exception:
                    pass
            raise JobError(f"Failed to cancel job: {error_msg}", job_id=job_id) from e

    async def list(
        self, queue_name: str | None = None, status: str | None = None, limit: int = 100
    ) -> list[JobStatus]:
        """List jobs with optional filtering.

        Args:
            queue_name: Filter by queue name
            status: Filter by job status (queued, started, finished, failed, cancelled)
            limit: Maximum number of jobs to return

        Returns:
            List of JobStatus objects

        Raises:
            JobError: If the query fails
            ConnectionError: If unable to connect to daemon
        """
        try:
            params = {"limit": limit}
            if queue_name:
                params["queue"] = queue_name
            if status:
                params["status"] = status

            response = await self._client.get(f"{self._base_url}/jobs", params=params)
            response.raise_for_status()

            jobs_data = response.json().get("jobs", [])
            return [self._parse_job_status(job) for job in jobs_data]
        except Exception as e:
            error_msg = str(e)
            if hasattr(e, "response") and hasattr(e.response, "json"):
                try:
                    error_data = e.response.json()
                    error_msg = error_data.get("error", error_msg)
                except Exception:
                    pass
            raise JobError(f"Failed to list jobs: {error_msg}") from e
