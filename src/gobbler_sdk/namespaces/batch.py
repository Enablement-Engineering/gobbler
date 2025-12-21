"""Batch operations namespace for Gobbler SDK.

This module provides methods for batch processing of multiple items.
"""

from typing import TYPE_CHECKING, Any, Callable

from gobbler_sdk.exceptions import BatchError
from gobbler_sdk.types import BatchItemResult, BatchOptions, BatchResult

if TYPE_CHECKING:
    import httpx


class BatchNamespace:
    """Namespace for batch processing operations.

    This class provides methods for processing multiple items in batches
    with progress tracking and result aggregation.
    """

    def __init__(self, client: "httpx.Client", base_url: str) -> None:
        """Initialize the batch namespace.

        Args:
            client: httpx Client instance for making requests
            base_url: Base URL of the Gobbler daemon API
        """
        self._client = client
        self._base_url = base_url

    def _parse_batch_result(self, response_data: dict[str, Any]) -> BatchResult:
        """Parse API response into BatchResult.

        Args:
            response_data: Raw response data from API

        Returns:
            Parsed BatchResult
        """
        items_data = response_data.get("items", [])
        items = [
            BatchItemResult(
                item_id=item.get("item_id", ""),
                source=item.get("source", ""),
                success=item.get("success", False),
                output_file=item.get("output_file"),
                error=item.get("error"),
                metadata=item.get("metadata", {}),
            )
            for item in items_data
        ]

        return BatchResult(
            batch_id=response_data.get("batch_id", ""),
            status=response_data.get("status", "queued"),
            total_items=response_data.get("total_items", 0),
            processed_items=response_data.get("processed_items", 0),
            successful_items=response_data.get("successful_items", 0),
            failed_items=response_data.get("failed_items", 0),
            start_time=response_data.get("start_time"),
            end_time=response_data.get("end_time"),
            duration_seconds=response_data.get("duration_seconds"),
            output_files=response_data.get("output_files", []),
            errors=response_data.get("errors", []),
            current_item=response_data.get("current_item"),
            items=items,
        )

    def youtube_playlist(
        self,
        playlist_url: str,
        options: BatchOptions | None = None,
        on_progress: Callable[[str, float], None] | None = None,
    ) -> BatchResult:
        """Process all videos in a YouTube playlist.

        Args:
            playlist_url: YouTube playlist URL
            options: Batch processing options
            on_progress: Optional callback for progress updates (batch_id, progress)

        Returns:
            BatchResult with processing results

        Raises:
            BatchError: If the batch operation fails
            ConnectionError: If unable to connect to daemon
        """
        opts = options or BatchOptions()

        try:
            response = self._client.post(
                f"{self._base_url}/batch/youtube-playlist",
                json={
                    "playlist_url": playlist_url,
                    "concurrency": opts.concurrency,
                    "skip_existing": opts.skip_existing,
                    "auto_queue": opts.auto_queue,
                    "output_dir": opts.output_dir,
                },
            )
            response.raise_for_status()
            result = self._parse_batch_result(response.json())

            # Poll for progress if callback provided
            if on_progress and result.status in ("queued", "running"):
                self._poll_progress(result.batch_id, on_progress)

            return result
        except Exception as e:
            error_msg = str(e)
            if hasattr(e, "response") and hasattr(e.response, "json"):
                try:
                    error_data = e.response.json()
                    error_msg = error_data.get("error", error_msg)
                except Exception:
                    pass
            raise BatchError(f"Failed to process YouTube playlist: {error_msg}") from e

    def audio_files(
        self,
        file_paths: list[str],
        options: BatchOptions | None = None,
        on_progress: Callable[[str, float], None] | None = None,
    ) -> BatchResult:
        """Transcribe multiple audio files.

        Args:
            file_paths: List of audio file paths
            options: Batch processing options
            on_progress: Optional callback for progress updates (batch_id, progress)

        Returns:
            BatchResult with transcription results

        Raises:
            BatchError: If the batch operation fails
            ConnectionError: If unable to connect to daemon
        """
        opts = options or BatchOptions()

        try:
            response = self._client.post(
                f"{self._base_url}/batch/audio",
                json={
                    "file_paths": file_paths,
                    "concurrency": opts.concurrency,
                    "skip_existing": opts.skip_existing,
                    "auto_queue": opts.auto_queue,
                    "output_dir": opts.output_dir,
                },
            )
            response.raise_for_status()
            result = self._parse_batch_result(response.json())

            # Poll for progress if callback provided
            if on_progress and result.status in ("queued", "running"):
                self._poll_progress(result.batch_id, on_progress)

            return result
        except Exception as e:
            error_msg = str(e)
            if hasattr(e, "response") and hasattr(e.response, "json"):
                try:
                    error_data = e.response.json()
                    error_msg = error_data.get("error", error_msg)
                except Exception:
                    pass
            raise BatchError(f"Failed to process audio files: {error_msg}") from e

    def documents(
        self,
        file_paths: list[str],
        options: BatchOptions | None = None,
        on_progress: Callable[[str, float], None] | None = None,
    ) -> BatchResult:
        """Convert multiple documents.

        Args:
            file_paths: List of document file paths
            options: Batch processing options
            on_progress: Optional callback for progress updates (batch_id, progress)

        Returns:
            BatchResult with conversion results

        Raises:
            BatchError: If the batch operation fails
            ConnectionError: If unable to connect to daemon
        """
        opts = options or BatchOptions()

        try:
            response = self._client.post(
                f"{self._base_url}/batch/documents",
                json={
                    "file_paths": file_paths,
                    "concurrency": opts.concurrency,
                    "skip_existing": opts.skip_existing,
                    "auto_queue": opts.auto_queue,
                    "output_dir": opts.output_dir,
                },
            )
            response.raise_for_status()
            result = self._parse_batch_result(response.json())

            # Poll for progress if callback provided
            if on_progress and result.status in ("queued", "running"):
                self._poll_progress(result.batch_id, on_progress)

            return result
        except Exception as e:
            error_msg = str(e)
            if hasattr(e, "response") and hasattr(e.response, "json"):
                try:
                    error_data = e.response.json()
                    error_msg = error_data.get("error", error_msg)
                except Exception:
                    pass
            raise BatchError(f"Failed to process documents: {error_msg}") from e

    def webpages(
        self,
        urls: list[str],
        options: BatchOptions | None = None,
        on_progress: Callable[[str, float], None] | None = None,
    ) -> BatchResult:
        """Convert multiple webpages.

        Args:
            urls: List of webpage URLs
            options: Batch processing options
            on_progress: Optional callback for progress updates (batch_id, progress)

        Returns:
            BatchResult with conversion results

        Raises:
            BatchError: If the batch operation fails
            ConnectionError: If unable to connect to daemon
        """
        opts = options or BatchOptions()

        try:
            response = self._client.post(
                f"{self._base_url}/batch/webpages",
                json={
                    "urls": urls,
                    "concurrency": opts.concurrency,
                    "skip_existing": opts.skip_existing,
                    "auto_queue": opts.auto_queue,
                    "output_dir": opts.output_dir,
                },
            )
            response.raise_for_status()
            result = self._parse_batch_result(response.json())

            # Poll for progress if callback provided
            if on_progress and result.status in ("queued", "running"):
                self._poll_progress(result.batch_id, on_progress)

            return result
        except Exception as e:
            error_msg = str(e)
            if hasattr(e, "response") and hasattr(e.response, "json"):
                try:
                    error_data = e.response.json()
                    error_msg = error_data.get("error", error_msg)
                except Exception:
                    pass
            raise BatchError(f"Failed to process webpages: {error_msg}") from e

    def _poll_progress(self, batch_id: str, callback: Callable[[str, float], None]) -> None:
        """Poll batch progress and call callback with updates.

        Args:
            batch_id: Batch ID to poll
            callback: Callback function to call with progress updates
        """
        import time

        while True:
            try:
                response = self._client.get(f"{self._base_url}/batch/{batch_id}")
                response.raise_for_status()
                result = self._parse_batch_result(response.json())

                # Calculate progress percentage
                progress = (
                    (result.processed_items / result.total_items * 100)
                    if result.total_items > 0
                    else 0
                )

                callback(batch_id, progress)

                # Stop polling if batch is complete
                if result.status in ("completed", "failed", "cancelled"):
                    break

                time.sleep(1)  # Poll every second
            except Exception:
                break  # Stop polling on error


class AsyncBatchNamespace:
    """Async namespace for batch processing operations.

    This class provides async methods for processing multiple items in batches
    with progress tracking and result aggregation.
    """

    def __init__(self, client: "httpx.AsyncClient", base_url: str) -> None:
        """Initialize the async batch namespace.

        Args:
            client: httpx AsyncClient instance for making requests
            base_url: Base URL of the Gobbler daemon API
        """
        self._client = client
        self._base_url = base_url

    def _parse_batch_result(self, response_data: dict[str, Any]) -> BatchResult:
        """Parse API response into BatchResult.

        Args:
            response_data: Raw response data from API

        Returns:
            Parsed BatchResult
        """
        items_data = response_data.get("items", [])
        items = [
            BatchItemResult(
                item_id=item.get("item_id", ""),
                source=item.get("source", ""),
                success=item.get("success", False),
                output_file=item.get("output_file"),
                error=item.get("error"),
                metadata=item.get("metadata", {}),
            )
            for item in items_data
        ]

        return BatchResult(
            batch_id=response_data.get("batch_id", ""),
            status=response_data.get("status", "queued"),
            total_items=response_data.get("total_items", 0),
            processed_items=response_data.get("processed_items", 0),
            successful_items=response_data.get("successful_items", 0),
            failed_items=response_data.get("failed_items", 0),
            start_time=response_data.get("start_time"),
            end_time=response_data.get("end_time"),
            duration_seconds=response_data.get("duration_seconds"),
            output_files=response_data.get("output_files", []),
            errors=response_data.get("errors", []),
            current_item=response_data.get("current_item"),
            items=items,
        )

    async def youtube_playlist(
        self,
        playlist_url: str,
        options: BatchOptions | None = None,
        on_progress: Callable[[str, float], None] | None = None,
    ) -> BatchResult:
        """Process all videos in a YouTube playlist.

        Args:
            playlist_url: YouTube playlist URL
            options: Batch processing options
            on_progress: Optional callback for progress updates (batch_id, progress)

        Returns:
            BatchResult with processing results

        Raises:
            BatchError: If the batch operation fails
            ConnectionError: If unable to connect to daemon
        """
        opts = options or BatchOptions()

        try:
            response = await self._client.post(
                f"{self._base_url}/batch/youtube-playlist",
                json={
                    "playlist_url": playlist_url,
                    "concurrency": opts.concurrency,
                    "skip_existing": opts.skip_existing,
                    "auto_queue": opts.auto_queue,
                    "output_dir": opts.output_dir,
                },
            )
            response.raise_for_status()
            result = self._parse_batch_result(response.json())

            # Poll for progress if callback provided
            if on_progress and result.status in ("queued", "running"):
                await self._poll_progress(result.batch_id, on_progress)

            return result
        except Exception as e:
            error_msg = str(e)
            if hasattr(e, "response") and hasattr(e.response, "json"):
                try:
                    error_data = e.response.json()
                    error_msg = error_data.get("error", error_msg)
                except Exception:
                    pass
            raise BatchError(f"Failed to process YouTube playlist: {error_msg}") from e

    async def audio_files(
        self,
        file_paths: list[str],
        options: BatchOptions | None = None,
        on_progress: Callable[[str, float], None] | None = None,
    ) -> BatchResult:
        """Transcribe multiple audio files.

        Args:
            file_paths: List of audio file paths
            options: Batch processing options
            on_progress: Optional callback for progress updates (batch_id, progress)

        Returns:
            BatchResult with transcription results

        Raises:
            BatchError: If the batch operation fails
            ConnectionError: If unable to connect to daemon
        """
        opts = options or BatchOptions()

        try:
            response = await self._client.post(
                f"{self._base_url}/batch/audio",
                json={
                    "file_paths": file_paths,
                    "concurrency": opts.concurrency,
                    "skip_existing": opts.skip_existing,
                    "auto_queue": opts.auto_queue,
                    "output_dir": opts.output_dir,
                },
            )
            response.raise_for_status()
            result = self._parse_batch_result(response.json())

            # Poll for progress if callback provided
            if on_progress and result.status in ("queued", "running"):
                await self._poll_progress(result.batch_id, on_progress)

            return result
        except Exception as e:
            error_msg = str(e)
            if hasattr(e, "response") and hasattr(e.response, "json"):
                try:
                    error_data = e.response.json()
                    error_msg = error_data.get("error", error_msg)
                except Exception:
                    pass
            raise BatchError(f"Failed to process audio files: {error_msg}") from e

    async def documents(
        self,
        file_paths: list[str],
        options: BatchOptions | None = None,
        on_progress: Callable[[str, float], None] | None = None,
    ) -> BatchResult:
        """Convert multiple documents.

        Args:
            file_paths: List of document file paths
            options: Batch processing options
            on_progress: Optional callback for progress updates (batch_id, progress)

        Returns:
            BatchResult with conversion results

        Raises:
            BatchError: If the batch operation fails
            ConnectionError: If unable to connect to daemon
        """
        opts = options or BatchOptions()

        try:
            response = await self._client.post(
                f"{self._base_url}/batch/documents",
                json={
                    "file_paths": file_paths,
                    "concurrency": opts.concurrency,
                    "skip_existing": opts.skip_existing,
                    "auto_queue": opts.auto_queue,
                    "output_dir": opts.output_dir,
                },
            )
            response.raise_for_status()
            result = self._parse_batch_result(response.json())

            # Poll for progress if callback provided
            if on_progress and result.status in ("queued", "running"):
                await self._poll_progress(result.batch_id, on_progress)

            return result
        except Exception as e:
            error_msg = str(e)
            if hasattr(e, "response") and hasattr(e.response, "json"):
                try:
                    error_data = e.response.json()
                    error_msg = error_data.get("error", error_msg)
                except Exception:
                    pass
            raise BatchError(f"Failed to process documents: {error_msg}") from e

    async def webpages(
        self,
        urls: list[str],
        options: BatchOptions | None = None,
        on_progress: Callable[[str, float], None] | None = None,
    ) -> BatchResult:
        """Convert multiple webpages.

        Args:
            urls: List of webpage URLs
            options: Batch processing options
            on_progress: Optional callback for progress updates (batch_id, progress)

        Returns:
            BatchResult with conversion results

        Raises:
            BatchError: If the batch operation fails
            ConnectionError: If unable to connect to daemon
        """
        opts = options or BatchOptions()

        try:
            response = await self._client.post(
                f"{self._base_url}/batch/webpages",
                json={
                    "urls": urls,
                    "concurrency": opts.concurrency,
                    "skip_existing": opts.skip_existing,
                    "auto_queue": opts.auto_queue,
                    "output_dir": opts.output_dir,
                },
            )
            response.raise_for_status()
            result = self._parse_batch_result(response.json())

            # Poll for progress if callback provided
            if on_progress and result.status in ("queued", "running"):
                await self._poll_progress(result.batch_id, on_progress)

            return result
        except Exception as e:
            error_msg = str(e)
            if hasattr(e, "response") and hasattr(e.response, "json"):
                try:
                    error_data = e.response.json()
                    error_msg = error_data.get("error", error_msg)
                except Exception:
                    pass
            raise BatchError(f"Failed to process webpages: {error_msg}") from e

    async def _poll_progress(self, batch_id: str, callback: Callable[[str, float], None]) -> None:
        """Poll batch progress and call callback with updates.

        Args:
            batch_id: Batch ID to poll
            callback: Callback function to call with progress updates
        """
        import asyncio

        while True:
            try:
                response = await self._client.get(f"{self._base_url}/batch/{batch_id}")
                response.raise_for_status()
                result = self._parse_batch_result(response.json())

                # Calculate progress percentage
                progress = (
                    (result.processed_items / result.total_items * 100)
                    if result.total_items > 0
                    else 0
                )

                callback(batch_id, progress)

                # Stop polling if batch is complete
                if result.status in ("completed", "failed", "cancelled"):
                    break

                await asyncio.sleep(1)  # Poll every second
            except Exception:
                break  # Stop polling on error
