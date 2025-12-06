"""Type definitions for Gobbler MCP server.

This module defines TypedDict classes and type aliases used throughout the
Gobbler MCP server to improve type safety and code documentation.
"""

from typing import TypedDict, Literal, Any


class ConversionMetadata(TypedDict, total=False):
    """Metadata for converted content.

    Attributes:
        title: Document or content title
        source_url: Original URL of the content
        source_file: Original file path of the content
        content_type: Type of content (webpage, video, audio, document)
        conversion_date: ISO 8601 timestamp of conversion
        language: Content language code (ISO 639-1)
        duration: Duration in seconds (for audio/video)
        word_count: Number of words in the content
        author: Content author or creator
        description: Content description or summary
        tags: List of tags or keywords
        model: Model used for processing (e.g., Whisper model)
        error: Error message if conversion partially failed
    """
    title: str
    source_url: str
    source_file: str
    content_type: str
    conversion_date: str
    language: str
    duration: float
    word_count: int
    author: str
    description: str
    tags: list[str]
    model: str
    error: str


class BatchResult(TypedDict, total=False):
    """Result of a batch operation.

    Attributes:
        batch_id: Unique identifier for the batch
        status: Current status of the batch
        total_items: Total number of items to process
        processed_items: Number of items processed so far
        successful_items: Number of successfully processed items
        failed_items: Number of failed items
        start_time: ISO 8601 timestamp when batch started
        end_time: ISO 8601 timestamp when batch completed
        duration_seconds: Total duration in seconds
        output_files: List of output file paths
        errors: List of error messages
        current_item: Currently processing item
    """
    batch_id: str
    status: Literal["queued", "running", "completed", "failed", "cancelled"]
    total_items: int
    processed_items: int
    successful_items: int
    failed_items: int
    start_time: str
    end_time: str
    duration_seconds: float
    output_files: list[str]
    errors: list[str]
    current_item: str


class JobStatus(TypedDict, total=False):
    """Status of a queued job.

    Attributes:
        job_id: Unique identifier for the job
        status: Current status of the job
        queue_name: Name of the queue containing the job
        enqueued_at: ISO 8601 timestamp when job was enqueued
        started_at: ISO 8601 timestamp when job started
        ended_at: ISO 8601 timestamp when job completed
        progress: Progress percentage (0-100)
        result: Job result data
        error: Error message if job failed
        exc_info: Exception information if job failed
    """
    job_id: str
    status: Literal["queued", "started", "finished", "failed", "cancelled"]
    queue_name: str
    enqueued_at: str
    started_at: str
    ended_at: str
    progress: float
    result: Any
    error: str
    exc_info: str


class ServiceHealth(TypedDict, total=False):
    """Health status of a service.

    Attributes:
        service_name: Name of the service
        status: Current health status
        available: Whether the service is available
        version: Service version
        uptime_seconds: Service uptime in seconds
        last_check: ISO 8601 timestamp of last health check
        error: Error message if service is unhealthy
        details: Additional service-specific health details
    """
    service_name: str
    status: Literal["healthy", "unhealthy", "degraded", "unknown"]
    available: bool
    version: str
    uptime_seconds: float
    last_check: str
    error: str
    details: dict[str, Any]


class CrawlSessionConfig(TypedDict, total=False):
    """Configuration for a crawl session.

    Attributes:
        session_id: Unique identifier for the session
        cookies: List of cookies to set
        local_storage: localStorage key-value pairs
        user_agent: Custom user agent string
        headers: Additional HTTP headers
    """
    session_id: str
    cookies: list[dict[str, Any]]
    local_storage: dict[str, str]
    user_agent: str
    headers: dict[str, str]


class TranscriptionOptions(TypedDict, total=False):
    """Options for audio/video transcription.

    Attributes:
        model: Whisper model size to use
        language: Expected language code (ISO 639-1)
        include_timestamps: Include timestamps in output
        output_file: Path to save transcription
        auto_queue: Automatically queue if estimated duration > threshold
    """
    model: Literal["tiny", "base", "small", "medium", "large"]
    language: str
    include_timestamps: bool
    output_file: str
    auto_queue: bool


class WebpageOptions(TypedDict, total=False):
    """Options for webpage conversion.

    Attributes:
        include_images: Include image references in markdown
        timeout: Request timeout in seconds
        css_selector: CSS selector to extract specific content
        xpath: XPath expression to extract content
        extract_links: Extract and categorize links
        session_id: Session ID for authenticated crawling
        bypass_cache: Bypass cache for fresh content
    """
    include_images: bool
    timeout: int
    css_selector: str
    xpath: str
    extract_links: bool
    session_id: str
    bypass_cache: bool


class DocumentOptions(TypedDict, total=False):
    """Options for document conversion.

    Attributes:
        enable_ocr: Enable OCR for scanned documents
        output_file: Path to save converted document
    """
    enable_ocr: bool
    output_file: str


class BatchOptions(TypedDict, total=False):
    """Options for batch operations.

    Attributes:
        concurrency: Number of concurrent operations
        skip_existing: Skip items that already have output files
        auto_queue: Automatically queue if batch exceeds threshold
        output_dir: Directory to save output files
        pattern: Glob pattern for file matching
        recursive: Search subdirectories recursively
    """
    concurrency: int
    skip_existing: bool
    auto_queue: bool
    output_dir: str
    pattern: str
    recursive: bool
