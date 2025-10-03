"""Data models for batch processing."""

from dataclasses import dataclass, field
from typing import Any, Dict, Optional


@dataclass
class BatchItem:
    """Single item in a batch operation."""

    id: str
    source: str  # URL, file path, etc.
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class BatchResult:
    """Result of processing a batch item."""

    item_id: str
    success: bool
    output_file: Optional[str] = None
    error: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class BatchSummary:
    """Summary of batch operation."""

    batch_id: str
    total_items: int
    successful: int
    failed: int
    skipped: int
    output_dir: str
    processing_time_seconds: float
    success_details: list[dict] = field(default_factory=list)
    failures: list[dict] = field(default_factory=list)
    skipped_details: list[dict] = field(default_factory=list)

    def format_report(self) -> str:
        """
        Format batch summary as human-readable report.

        Returns:
            Formatted markdown report
        """
        success_rate = (
            (self.successful / self.total_items * 100) if self.total_items > 0 else 0
        )

        # Format processing time
        minutes = int(self.processing_time_seconds // 60)
        seconds = int(self.processing_time_seconds % 60)
        time_str = f"{minutes}m {seconds}s" if minutes > 0 else f"{seconds}s"

        lines = [
            "# Batch Operation Summary\n",
            f"**Batch ID:** {self.batch_id}",
            f"**Status:** {'✅ Completed' if self.failed == 0 else '⚠️ Completed with errors'}\n",
            "## Statistics",
            f"- **Total Items:** {self.total_items}",
            f"- **Successful:** {self.successful} ({success_rate:.1f}%)",
            f"- **Failed:** {self.failed}",
            f"- **Skipped:** {self.skipped}",
            f"- **Processing Time:** {time_str}\n",
        ]

        # Successful items
        if self.success_details:
            lines.append("## Successful Items")
            for i, item in enumerate(self.success_details, 1):
                source = item.get("source", "unknown")
                output = item.get("output_file", "")
                meta_str = ""
                if "word_count" in item.get("metadata", {}):
                    meta_str = f" ({item['metadata']['word_count']:,} words)"
                lines.append(f"{i}. ✅ {source} → {output}{meta_str}")
            lines.append("")

        # Failed items
        if self.failures:
            lines.append("## Failed Items")
            for i, item in enumerate(self.failures, 1):
                source = item.get("source", "unknown")
                error = item.get("error", "Unknown error")
                lines.append(f"{i}. ❌ {source} - {error}")
            lines.append("")

        # Skipped items
        if self.skipped_details:
            lines.append("## Skipped Items")
            for i, item in enumerate(self.skipped_details, 1):
                source = item.get("source", "unknown")
                reason = item.get("reason", "Unknown reason")
                lines.append(f"{i}. ⏭️ {source} - {reason}")
            lines.append("")

        # Output location
        lines.append("## Output Location")
        lines.append(f"All files saved to: {self.output_dir}\n")

        lines.append(
            f"Check progress anytime with: get_batch_progress(batch_id=\"{self.batch_id}\")"
        )

        return "\n".join(lines)
