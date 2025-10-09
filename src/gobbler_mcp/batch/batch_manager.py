"""Core batch processing engine."""

import asyncio
import logging
import random
import time
import uuid
from pathlib import Path
from typing import Callable, List, Optional

from .models import BatchItem, BatchResult, BatchSummary
from .progress_tracker import ProgressTracker

logger = logging.getLogger(__name__)


class BatchProcessor:
    """Generic batch processing engine with concurrency control."""

    def __init__(
        self,
        batch_id: Optional[str] = None,
        items: Optional[List[BatchItem]] = None,
        process_fn: Optional[Callable] = None,
        concurrency: int = 3,
        output_dir: Optional[str] = None,
        skip_existing: bool = True,
        operation_type: str = "batch",
        delay_between_requests: float = 0.0,
        jitter_range: float = 0.0,
        max_retries: int = 0,
        retry_delay: float = 1.0,
    ):
        """
        Initialize batch processor.

        Args:
            batch_id: Unique identifier for batch (auto-generated if None)
            items: List of items to process
            process_fn: Async function to process each item
            concurrency: Maximum concurrent operations
            output_dir: Directory for output files
            skip_existing: Skip items with existing output files
            operation_type: Type of operation for tracking
            delay_between_requests: Fixed delay in seconds between requests (default: 0)
            jitter_range: Random jitter added to delay, 0-jitter_range seconds (default: 0)
            max_retries: Maximum retry attempts for failed items (default: 0)
            retry_delay: Initial delay for exponential backoff retries in seconds (default: 1.0)
        """
        self.batch_id = batch_id or str(uuid.uuid4())
        self.items = items or []
        self.process_fn = process_fn
        self.concurrency = concurrency
        self.output_dir = Path(output_dir) if output_dir else None
        self.skip_existing = skip_existing
        self.operation_type = operation_type
        self.delay_between_requests = delay_between_requests
        self.jitter_range = jitter_range
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.progress = ProgressTracker(self.batch_id)
        self.results: List[BatchResult] = []
        self.start_time: float = 0
        self.end_time: float = 0
        self._request_lock = asyncio.Lock()  # For rate limiting coordination

    async def _process_with_retry(self, item: BatchItem) -> BatchResult:
        """
        Process item with exponential backoff retry logic.

        Args:
            item: Item to process

        Returns:
            BatchResult from processing
        """
        last_error = None

        for attempt in range(self.max_retries + 1):
            try:
                result = await self.process_fn(item)

                # If successful or skipped, return immediately
                if result.success or result.error == "skipped":
                    if attempt > 0:
                        logger.info(f"Succeeded on attempt {attempt + 1} for {item.source}")
                    return result

                # If failed but out of retries, return the result
                if attempt >= self.max_retries:
                    return result

                # Otherwise retry
                last_error = result.error

            except Exception as e:
                last_error = str(e)

                # If out of retries, raise the exception
                if attempt >= self.max_retries:
                    raise

            # Exponential backoff: retry_delay * 2^attempt
            backoff_delay = self.retry_delay * (2 ** attempt)
            logger.warning(
                f"Attempt {attempt + 1} failed for {item.source}: {last_error}. "
                f"Retrying in {backoff_delay:.1f}s..."
            )
            await asyncio.sleep(backoff_delay)

        # Should not reach here, but return failure if we do
        return BatchResult(
            item_id=item.id,
            success=False,
            error=last_error or "Unknown error after retries"
        )

    def _get_unique_output_path(self, base_path: Path) -> Path:
        """
        Get unique output path by adding numeric suffix if file exists.

        Args:
            base_path: Base output path

        Returns:
            Unique output path
        """
        if not base_path.exists():
            return base_path

        # File exists, add numeric suffix
        stem = base_path.stem
        suffix = base_path.suffix
        parent = base_path.parent
        counter = 1

        while True:
            new_path = parent / f"{stem}_{counter}{suffix}"
            if not new_path.exists():
                return new_path
            counter += 1

    async def run(self) -> BatchSummary:
        """
        Execute batch operation with progress tracking.

        Returns:
            BatchSummary with results and statistics
        """
        self.start_time = time.time()

        try:
            # Initialize progress tracking
            await self.progress.initialize(
                total_items=len(self.items), operation_type=self.operation_type
            )

            # Create output directory if needed
            if self.output_dir:
                self.output_dir.mkdir(parents=True, exist_ok=True)

            # Process items with concurrency control
            semaphore = asyncio.Semaphore(self.concurrency)

            async def process_with_tracking(item: BatchItem) -> BatchResult:
                """Process single item with progress tracking and rate limiting."""
                async with semaphore:
                    # Rate limiting: add delay with jitter before processing
                    if self.delay_between_requests > 0 or self.jitter_range > 0:
                        async with self._request_lock:
                            delay = self.delay_between_requests
                            if self.jitter_range > 0:
                                delay += random.uniform(0, self.jitter_range)
                            if delay > 0:
                                logger.debug(f"Rate limit delay: {delay:.2f}s for {item.source}")
                                await asyncio.sleep(delay)

                    try:
                        # Update progress
                        await self.progress.update_current_item(item.source)

                        # Check if should skip
                        if self.skip_existing and "expected_output" in item.metadata:
                            expected_path = Path(item.metadata["expected_output"])
                            if expected_path.exists():
                                await self.progress.increment_skipped(
                                    "File already exists", item.source
                                )
                                return BatchResult(
                                    item_id=item.id,
                                    success=False,
                                    error="skipped",
                                    metadata={"reason": "File already exists"},
                                )

                        # Process item with retries
                        result = await self._process_with_retry(item)

                        # Track success
                        if result.success:
                            await self.progress.increment_success()
                        else:
                            if result.error == "skipped":
                                await self.progress.increment_skipped(
                                    result.metadata.get("reason", "Unknown"),
                                    item.source,
                                )
                            else:
                                await self.progress.increment_failure(
                                    result.error or "Unknown error", item.source
                                )

                        return result

                    except Exception as e:
                        error_msg = str(e)
                        logger.error(
                            f"Error processing item {item.source}: {error_msg}",
                            exc_info=True,
                        )
                        await self.progress.increment_failure(error_msg, item.source)
                        return BatchResult(
                            item_id=item.id, success=False, error=error_msg
                        )

            # Process all items
            logger.info(
                f"Processing {len(self.items)} items with concurrency={self.concurrency}"
            )
            self.results = await asyncio.gather(
                *[process_with_tracking(item) for item in self.items]
            )

            # Mark batch complete
            await self.progress.mark_complete()

        except Exception as e:
            logger.error(f"Batch operation failed: {e}", exc_info=True)
            await self.progress.mark_failed(str(e))
            raise

        finally:
            self.end_time = time.time()

        # Generate summary
        return self._generate_summary()

    def _generate_summary(self) -> BatchSummary:
        """
        Generate batch operation summary.

        Returns:
            BatchSummary with statistics and details
        """
        successful = []
        failed = []
        skipped = []

        for i, result in enumerate(self.results):
            item = self.items[i]

            if result.error == "skipped":
                skipped.append(
                    {
                        "source": item.source,
                        "reason": result.metadata.get("reason", "Unknown"),
                    }
                )
            elif result.success:
                successful.append(
                    {
                        "source": item.source,
                        "output_file": result.output_file,
                        "metadata": result.metadata,
                    }
                )
            else:
                failed.append(
                    {
                        "source": item.source,
                        "error": result.error or "Unknown error",
                    }
                )

        processing_time = self.end_time - self.start_time

        return BatchSummary(
            batch_id=self.batch_id,
            total_items=len(self.items),
            successful=len(successful),
            failed=len(failed),
            skipped=len(skipped),
            output_dir=str(self.output_dir) if self.output_dir else "",
            processing_time_seconds=processing_time,
            success_details=successful,
            failures=failed,
            skipped_details=skipped,
        )
