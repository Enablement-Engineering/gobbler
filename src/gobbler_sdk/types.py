"""Type definitions for Gobbler SDK.

This module defines dataclasses and type aliases used throughout the
Gobbler SDK to provide type-safe interfaces to the Gobbler daemon.
"""

from dataclasses import dataclass, field
from typing import Any, Literal, Optional


@dataclass
class ConversionMetadata:
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

    title: Optional[str] = None
    source_url: Optional[str] = None
    source_file: Optional[str] = None
    content_type: Optional[str] = None
    conversion_date: Optional[str] = None
    language: Optional[str] = None
    duration: Optional[float] = None
    word_count: Optional[int] = None
    author: Optional[str] = None
    description: Optional[str] = None
    tags: list[str] = field(default_factory=list)
    model: Optional[str] = None
    error: Optional[str] = None


@dataclass
class ConversionResult:
    """Result of a content conversion operation.

    Attributes:
        markdown: Converted content in markdown format
        metadata: Metadata about the conversion
        output_file: Path to output file if saved
        success: Whether the conversion was successful
        error: Error message if conversion failed
    """

    markdown: str
    metadata: ConversionMetadata = field(default_factory=ConversionMetadata)
    output_file: Optional[str] = None
    success: bool = True
    error: Optional[str] = None


JobStatusType = Literal["queued", "started", "finished", "failed", "cancelled"]


@dataclass
class JobStatus:
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
    status: JobStatusType
    queue_name: Optional[str] = None
    enqueued_at: Optional[str] = None
    started_at: Optional[str] = None
    ended_at: Optional[str] = None
    progress: float = 0.0
    result: Any = None
    error: Optional[str] = None
    exc_info: Optional[str] = None


BatchStatusType = Literal["queued", "running", "completed", "failed", "cancelled"]


@dataclass
class BatchItemResult:
    """Result of a single item in a batch operation.

    Attributes:
        item_id: Unique identifier for the item
        source: Source URL or file path
        success: Whether the item was processed successfully
        output_file: Path to output file if saved
        error: Error message if processing failed
        metadata: Item-specific metadata
    """

    item_id: str
    source: str
    success: bool
    output_file: Optional[str] = None
    error: Optional[str] = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class BatchResult:
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
        items: List of individual item results
    """

    batch_id: str
    status: BatchStatusType
    total_items: int = 0
    processed_items: int = 0
    successful_items: int = 0
    failed_items: int = 0
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    duration_seconds: Optional[float] = None
    output_files: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    current_item: Optional[str] = None
    items: list[BatchItemResult] = field(default_factory=list)


ServiceHealthStatus = Literal["healthy", "unhealthy", "degraded", "unknown"]


@dataclass
class ServiceHealth:
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
    status: ServiceHealthStatus
    available: bool = False
    version: Optional[str] = None
    uptime_seconds: Optional[float] = None
    last_check: Optional[str] = None
    error: Optional[str] = None
    details: dict[str, Any] = field(default_factory=dict)


WhisperModel = Literal["tiny", "base", "small", "medium", "large"]


@dataclass
class TranscriptionOptions:
    """Options for audio/video transcription.

    Attributes:
        model: Whisper model size to use
        language: Expected language code (ISO 639-1)
        include_timestamps: Include timestamps in output
        output_file: Path to save transcription
        auto_queue: Automatically queue if estimated duration > threshold
    """

    model: WhisperModel = "small"
    language: Optional[str] = None
    include_timestamps: bool = False
    output_file: Optional[str] = None
    auto_queue: bool = False


@dataclass
class WebpageOptions:
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

    include_images: bool = True
    timeout: int = 30
    css_selector: Optional[str] = None
    xpath: Optional[str] = None
    extract_links: bool = False
    session_id: Optional[str] = None
    bypass_cache: bool = False


@dataclass
class DocumentOptions:
    """Options for document conversion.

    Attributes:
        enable_ocr: Enable OCR for scanned documents
        output_file: Path to save converted document
    """

    enable_ocr: bool = True
    output_file: Optional[str] = None


@dataclass
class BatchOptions:
    """Options for batch operations.

    Attributes:
        concurrency: Number of concurrent operations
        skip_existing: Skip items that already have output files
        auto_queue: Automatically queue if batch exceeds threshold
        output_dir: Directory to save output files
        pattern: Glob pattern for file matching
        recursive: Search subdirectories recursively
    """

    concurrency: int = 3
    skip_existing: bool = False
    auto_queue: bool = True
    output_dir: Optional[str] = None
    pattern: str = "*"
    recursive: bool = False
