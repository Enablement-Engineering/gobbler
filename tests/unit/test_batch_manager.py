"""Unit tests for batch manager."""

import pytest

from gobbler_mcp.batch.batch_manager import BatchProcessor
from gobbler_mcp.batch.models import BatchItem, BatchResult


class TestBatchProcessor:
    """Test BatchProcessor class."""

    @pytest.mark.asyncio
    async def test_simple_batch_processing(self, tmp_path):
        """Test processing a simple batch."""
        # Create test items
        items = [
            BatchItem(id="1", source="item1", metadata={}),
            BatchItem(id="2", source="item2", metadata={}),
            BatchItem(id="3", source="item3", metadata={}),
        ]

        # Define process function
        async def process_item(item: BatchItem) -> BatchResult:
            """Simple processor that always succeeds."""
            return BatchResult(
                item_id=item.id,
                success=True,
                output_file=f"/tmp/{item.source}.md",
                metadata={"processed": True},
            )

        # Create processor
        processor = BatchProcessor(
            items=items,
            process_fn=process_item,
            concurrency=2,
            output_dir=str(tmp_path),
            operation_type="test_batch",
        )

        # Run batch
        summary = await processor.run()

        # Verify results
        assert summary.total_items == 3
        assert summary.successful == 3
        assert summary.failed == 0
        assert summary.skipped == 0
        assert len(summary.success_details) == 3
        assert summary.processing_time_seconds > 0

    @pytest.mark.asyncio
    async def test_batch_with_failures(self, tmp_path):
        """Test batch processing with failures."""
        # Create test items
        items = [
            BatchItem(id="1", source="item1", metadata={}),
            BatchItem(id="2", source="item2", metadata={}),
            BatchItem(id="3", source="item3", metadata={}),
        ]

        # Define process function that fails on item2
        async def process_item(item: BatchItem) -> BatchResult:
            """Processor that fails on item2."""
            if item.id == "2":
                return BatchResult(
                    item_id=item.id,
                    success=False,
                    error="Simulated error",
                )
            return BatchResult(
                item_id=item.id,
                success=True,
                output_file=f"/tmp/{item.source}.md",
            )

        # Create processor
        processor = BatchProcessor(
            items=items,
            process_fn=process_item,
            concurrency=1,
            output_dir=str(tmp_path),
            operation_type="test_batch",
        )

        # Run batch
        summary = await processor.run()

        # Verify results
        assert summary.total_items == 3
        assert summary.successful == 2
        assert summary.failed == 1
        assert summary.skipped == 0
        assert len(summary.success_details) == 2
        assert len(summary.failures) == 1
        assert summary.failures[0]["error"] == "Simulated error"

    @pytest.mark.asyncio
    async def test_batch_with_skipped_items(self, tmp_path):
        """Test batch processing with skipped items."""
        # Create test items
        items = [
            BatchItem(id="1", source="item1", metadata={}),
            BatchItem(id="2", source="item2", metadata={}),
            BatchItem(id="3", source="item3", metadata={}),
        ]

        # Define process function that skips item2
        async def process_item(item: BatchItem) -> BatchResult:
            """Processor that skips item2."""
            if item.id == "2":
                return BatchResult(
                    item_id=item.id,
                    success=False,
                    error="skipped",
                    metadata={"reason": "Already exists"},
                )
            return BatchResult(
                item_id=item.id,
                success=True,
                output_file=f"/tmp/{item.source}.md",
            )

        # Create processor
        processor = BatchProcessor(
            items=items,
            process_fn=process_item,
            concurrency=1,
            output_dir=str(tmp_path),
            operation_type="test_batch",
        )

        # Run batch
        summary = await processor.run()

        # Verify results
        assert summary.total_items == 3
        assert summary.successful == 2
        assert summary.failed == 0
        assert summary.skipped == 1
        assert len(summary.skipped_details) == 1
        assert summary.skipped_details[0]["reason"] == "Already exists"

    @pytest.mark.asyncio
    async def test_batch_concurrency_control(self, tmp_path):
        """Test that concurrency is properly controlled."""
        import asyncio

        # Track concurrent execution
        concurrent_count = 0
        max_concurrent = 0

        items = [
            BatchItem(id=str(i), source=f"item{i}", metadata={})
            for i in range(10)
        ]

        async def process_item(item: BatchItem) -> BatchResult:
            """Processor that tracks concurrency."""
            nonlocal concurrent_count, max_concurrent

            concurrent_count += 1
            max_concurrent = max(max_concurrent, concurrent_count)

            # Simulate work
            await asyncio.sleep(0.01)

            concurrent_count -= 1

            return BatchResult(
                item_id=item.id,
                success=True,
                output_file=f"/tmp/{item.source}.md",
            )

        # Create processor with concurrency=3
        processor = BatchProcessor(
            items=items,
            process_fn=process_item,
            concurrency=3,
            output_dir=str(tmp_path),
            operation_type="test_batch",
        )

        # Run batch
        summary = await processor.run()

        # Verify concurrency was limited
        assert summary.total_items == 10
        assert summary.successful == 10
        assert max_concurrent <= 3  # Should never exceed concurrency limit

    @pytest.mark.asyncio
    async def test_batch_exception_handling(self, tmp_path):
        """Test that exceptions are caught and reported."""
        items = [
            BatchItem(id="1", source="item1", metadata={}),
            BatchItem(id="2", source="item2", metadata={}),
        ]

        async def process_item(item: BatchItem) -> BatchResult:
            """Processor that raises exception on item2."""
            if item.id == "2":
                raise ValueError("Simulated exception")
            return BatchResult(
                item_id=item.id,
                success=True,
                output_file=f"/tmp/{item.source}.md",
            )

        processor = BatchProcessor(
            items=items,
            process_fn=process_item,
            concurrency=1,
            output_dir=str(tmp_path),
            operation_type="test_batch",
        )

        # Run batch (should not raise, exceptions are caught)
        summary = await processor.run()

        # Verify exception was caught and reported
        assert summary.total_items == 2
        assert summary.successful == 1
        assert summary.failed == 1
        assert "Simulated exception" in summary.failures[0]["error"]

    @pytest.mark.asyncio
    async def test_empty_batch(self, tmp_path):
        """Test processing empty batch."""
        async def process_item(item: BatchItem) -> BatchResult:
            """Dummy processor."""
            return BatchResult(item_id=item.id, success=True)

        processor = BatchProcessor(
            items=[],
            process_fn=process_item,
            concurrency=1,
            output_dir=str(tmp_path),
            operation_type="test_batch",
        )

        summary = await processor.run()

        assert summary.total_items == 0
        assert summary.successful == 0
        assert summary.failed == 0
        assert summary.skipped == 0
