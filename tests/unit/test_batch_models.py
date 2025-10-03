"""Unit tests for batch models."""

import pytest

from gobbler_mcp.batch.models import BatchItem, BatchResult, BatchSummary


class TestBatchItem:
    """Test BatchItem model."""

    def test_create_batch_item(self):
        """Test creating a batch item."""
        item = BatchItem(
            id="test-1",
            source="https://example.com/video",
            metadata={"title": "Test Video"},
        )

        assert item.id == "test-1"
        assert item.source == "https://example.com/video"
        assert item.metadata["title"] == "Test Video"

    def test_batch_item_empty_metadata(self):
        """Test batch item with empty metadata."""
        item = BatchItem(id="test-1", source="test.mp4")

        assert item.id == "test-1"
        assert item.source == "test.mp4"
        assert item.metadata == {}


class TestBatchResult:
    """Test BatchResult model."""

    def test_successful_result(self):
        """Test successful batch result."""
        result = BatchResult(
            item_id="test-1",
            success=True,
            output_file="/tmp/output.md",
            metadata={"word_count": 1000},
        )

        assert result.item_id == "test-1"
        assert result.success is True
        assert result.output_file == "/tmp/output.md"
        assert result.error is None
        assert result.metadata["word_count"] == 1000

    def test_failed_result(self):
        """Test failed batch result."""
        result = BatchResult(
            item_id="test-1",
            success=False,
            error="File not found",
        )

        assert result.item_id == "test-1"
        assert result.success is False
        assert result.output_file is None
        assert result.error == "File not found"

    def test_skipped_result(self):
        """Test skipped batch result."""
        result = BatchResult(
            item_id="test-1",
            success=False,
            error="skipped",
            metadata={"reason": "File already exists"},
        )

        assert result.item_id == "test-1"
        assert result.success is False
        assert result.error == "skipped"
        assert result.metadata["reason"] == "File already exists"


class TestBatchSummary:
    """Test BatchSummary model."""

    def test_create_summary(self):
        """Test creating batch summary."""
        summary = BatchSummary(
            batch_id="batch-123",
            total_items=10,
            successful=8,
            failed=1,
            skipped=1,
            output_dir="/tmp/output",
            processing_time_seconds=120.5,
        )

        assert summary.batch_id == "batch-123"
        assert summary.total_items == 10
        assert summary.successful == 8
        assert summary.failed == 1
        assert summary.skipped == 1
        assert summary.output_dir == "/tmp/output"
        assert summary.processing_time_seconds == 120.5

    def test_format_report_all_successful(self):
        """Test formatting report with all successful items."""
        summary = BatchSummary(
            batch_id="batch-123",
            total_items=3,
            successful=3,
            failed=0,
            skipped=0,
            output_dir="/tmp/output",
            processing_time_seconds=45.2,
            success_details=[
                {
                    "source": "video1.mp4",
                    "output_file": "/tmp/output/video1.md",
                    "metadata": {"word_count": 1000},
                },
                {
                    "source": "video2.mp4",
                    "output_file": "/tmp/output/video2.md",
                    "metadata": {"word_count": 1500},
                },
                {
                    "source": "video3.mp4",
                    "output_file": "/tmp/output/video3.md",
                    "metadata": {"word_count": 800},
                },
            ],
        )

        report = summary.format_report()

        assert "batch-123" in report
        assert "✅ Completed" in report
        assert "Total Items:** 3" in report
        assert "Successful:** 3 (100.0%)" in report
        assert "Failed:** 0" in report
        assert "45s" in report
        assert "video1.mp4" in report
        assert "1,000 words" in report
        assert "/tmp/output" in report

    def test_format_report_with_failures(self):
        """Test formatting report with failures."""
        summary = BatchSummary(
            batch_id="batch-456",
            total_items=5,
            successful=3,
            failed=2,
            skipped=0,
            output_dir="/tmp/output",
            processing_time_seconds=125.8,
            success_details=[
                {
                    "source": "video1.mp4",
                    "output_file": "/tmp/output/video1.md",
                    "metadata": {},
                },
            ],
            failures=[
                {"source": "video2.mp4", "error": "Transcript not available"},
                {"source": "video3.mp4", "error": "Video is private"},
            ],
        )

        report = summary.format_report()

        assert "batch-456" in report
        assert "⚠️ Completed with errors" in report
        assert "Total Items:** 5" in report
        assert "Successful:** 3 (60.0%)" in report
        assert "Failed:** 2" in report
        assert "2m 5s" in report
        assert "## Failed Items" in report
        assert "Transcript not available" in report
        assert "Video is private" in report

    def test_format_report_with_skipped(self):
        """Test formatting report with skipped items."""
        summary = BatchSummary(
            batch_id="batch-789",
            total_items=4,
            successful=2,
            failed=0,
            skipped=2,
            output_dir="/tmp/output",
            processing_time_seconds=30.0,
            skipped_details=[
                {"source": "file1.md", "reason": "File already exists"},
                {"source": "file2.md", "reason": "File already exists"},
            ],
        )

        report = summary.format_report()

        assert "batch-789" in report
        assert "Skipped:** 2" in report
        assert "## Skipped Items" in report
        assert "File already exists" in report
        assert "30s" in report

    def test_format_report_timing(self):
        """Test formatting of different timing values."""
        # Less than 1 minute
        summary1 = BatchSummary(
            batch_id="batch-1",
            total_items=1,
            successful=1,
            failed=0,
            skipped=0,
            output_dir="/tmp",
            processing_time_seconds=45.0,
        )
        assert "45s" in summary1.format_report()

        # Exactly 1 minute
        summary2 = BatchSummary(
            batch_id="batch-2",
            total_items=1,
            successful=1,
            failed=0,
            skipped=0,
            output_dir="/tmp",
            processing_time_seconds=60.0,
        )
        assert "1m 0s" in summary2.format_report()

        # Multiple minutes
        summary3 = BatchSummary(
            batch_id="batch-3",
            total_items=1,
            successful=1,
            failed=0,
            skipped=0,
            output_dir="/tmp",
            processing_time_seconds=185.5,
        )
        assert "3m 5s" in summary3.format_report()
