"""Webpage batch processing."""

import logging
import re
from pathlib import Path
from typing import List

from ..converters.webpage import convert_webpage_to_markdown
from ..utils import save_markdown_file
from .batch_manager import BatchProcessor
from .models import BatchItem, BatchResult, BatchSummary

logger = logging.getLogger(__name__)


def sanitize_filename(text: str, max_length: int = 200) -> str:
    """
    Sanitize text for use as filename.

    Args:
        text: Text to sanitize
        max_length: Maximum filename length

    Returns:
        Sanitized filename
    """
    # Remove or replace invalid characters
    safe = "".join(c for c in text if c.isalnum() or c in (" ", "-", "_"))
    safe = safe.strip().replace(" ", "_")

    # Truncate if too long
    if len(safe) > max_length:
        safe = safe[:max_length]

    # Fallback if empty
    return safe or "webpage"


def generate_filename_from_url(url: str) -> str:
    """
    Generate filename from URL when title is not available.

    Args:
        url: Web page URL

    Returns:
        Filename based on URL
    """
    # Extract domain and path
    match = re.search(r"https?://(?:www\.)?([^/]+)(/[^?#]*)?", url)
    if match:
        domain = match.group(1).replace(".", "_")
        path = match.group(2) or ""
        path = path.strip("/").replace("/", "_")

        if path:
            return f"{domain}_{path}"
        return domain

    # Fallback
    return "webpage"


async def process_webpage_batch(
    urls: List[str],
    output_dir: str,
    include_images: bool = True,
    timeout: int = 30,
    concurrency: int = 5,
    skip_existing: bool = True,
    batch_id: Optional[str] = None,
) -> BatchSummary:
    """
    Process multiple web pages in batch.

    Args:
        urls: List of URLs to process
        output_dir: Directory to save markdown files
        include_images: Include image references
        timeout: Request timeout per page
        concurrency: Number of concurrent requests
        skip_existing: Skip URLs with existing files
        batch_id: Optional batch ID

    Returns:
        BatchSummary with processing results
    """
    # Create output directory
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    # Convert to BatchItems
    items = []
    for i, url in enumerate(urls):
        # Generate fallback filename from URL
        fallback_name = generate_filename_from_url(url)

        items.append(
            BatchItem(
                id=f"url_{i}",
                source=url,
                metadata={
                    "fallback_filename": fallback_name,
                },
            )
        )

    # Process function for single webpage
    async def process_webpage(item: BatchItem) -> BatchResult:
        """Process single web page."""
        try:
            # Convert to markdown
            markdown, metadata = await convert_webpage_to_markdown(
                url=item.source,
                include_images=include_images,
                timeout=timeout,
            )

            # Generate filename from title or URL
            title = metadata.get("title")
            if title:
                filename = sanitize_filename(title)
            else:
                filename = item.metadata["fallback_filename"]

            # Get unique output path
            output_file = output_path / f"{filename}.md"
            if output_file.exists():
                if skip_existing:
                    return BatchResult(
                        item_id=item.id,
                        success=False,
                        error="skipped",
                        metadata={"reason": "File already exists"},
                    )
                else:
                    # Add numeric suffix
                    counter = 1
                    while output_file.exists():
                        output_file = output_path / f"{filename}_{counter}.md"
                        counter += 1

            # Save to file
            success = await save_markdown_file(str(output_file), markdown)

            if not success:
                return BatchResult(
                    item_id=item.id,
                    success=False,
                    error="Failed to write file",
                )

            return BatchResult(
                item_id=item.id,
                success=True,
                output_file=str(output_file),
                metadata={
                    "title": metadata.get("title", "Unknown"),
                    "word_count": metadata.get("word_count", 0),
                },
            )

        except Exception as e:
            logger.error(f"Error processing webpage {item.source}: {e}")
            return BatchResult(
                item_id=item.id,
                success=False,
                error=str(e),
            )

    # Create batch processor
    processor = BatchProcessor(
        batch_id=batch_id,
        items=items,
        process_fn=process_webpage,
        concurrency=concurrency,
        output_dir=str(output_path),
        skip_existing=skip_existing,
        operation_type="webpage_batch",
    )

    # Run batch
    summary = await processor.run()

    logger.info(
        f"Batch complete: {summary.successful}/{summary.total_items} successful"
    )

    return summary
