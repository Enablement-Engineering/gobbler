"""Pydantic models for API request/response schemas."""

from datetime import datetime
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field, HttpUrl


class ConversionType(str, Enum):
    """Supported conversion types."""

    YOUTUBE = "youtube"
    AUDIO = "audio"
    DOCUMENT = "document"
    WEBPAGE = "webpage"


class JobStatus(str, Enum):
    """Job execution status."""

    QUEUED = "queued"
    STARTED = "started"
    FINISHED = "finished"
    FAILED = "failed"
    CANCELED = "canceled"


# Request Models


class YouTubeConvertRequest(BaseModel):
    """Request schema for YouTube video conversion."""

    video_url: HttpUrl = Field(..., description="YouTube video URL")
    include_timestamps: bool = Field(False, description="Include timestamp markers")
    language: str = Field("auto", description="Transcript language code or 'auto'")
    output_file: Optional[str] = Field(None, description="Optional output file path")


class AudioConvertRequest(BaseModel):
    """Request schema for audio transcription."""

    file_path: str = Field(..., description="Absolute path to audio/video file")
    model: str = Field("small", description="Whisper model size")
    language: str = Field("auto", description="Audio language code or 'auto'")
    output_file: Optional[str] = Field(None, description="Optional output file path")


class DocumentConvertRequest(BaseModel):
    """Request schema for document conversion."""

    file_path: str = Field(..., description="Absolute path to document file")
    enable_ocr: bool = Field(True, description="Enable OCR for scanned documents")
    output_file: Optional[str] = Field(None, description="Optional output file path")


class WebpageConvertRequest(BaseModel):
    """Request schema for webpage conversion."""

    url: HttpUrl = Field(..., description="Web page URL")
    include_images: bool = Field(True, description="Include image references")
    timeout: int = Field(30, description="Request timeout in seconds", ge=5, le=120)
    css_selector: Optional[str] = Field(None, description="CSS selector for content extraction")
    xpath: Optional[str] = Field(None, description="XPath for content extraction")
    extract_links: bool = Field(False, description="Extract and categorize links")
    session_id: Optional[str] = Field(None, description="Session ID for authenticated crawling")
    bypass_cache: bool = Field(False, description="Bypass cache for fresh content")
    output_file: Optional[str] = Field(None, description="Optional output file path")


class BatchConvertRequest(BaseModel):
    """Request schema for batch conversion jobs."""

    conversion_type: ConversionType = Field(..., description="Type of conversion")
    items: list[dict[str, Any]] = Field(..., description="List of items to convert")
    output_dir: str = Field(..., description="Output directory for results")
    concurrency: int = Field(3, description="Number of concurrent conversions", ge=1, le=10)
    skip_existing: bool = Field(True, description="Skip items with existing output files")


# Response Models


class ConversionMetadata(BaseModel):
    """Metadata for converted content."""

    source: str = Field(..., description="Source URL or file path")
    conversion_type: ConversionType = Field(..., description="Type of conversion")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Conversion timestamp")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Additional metadata")


class ConversionResponse(BaseModel):
    """Response schema for single conversion."""

    success: bool = Field(..., description="Whether conversion succeeded")
    markdown: Optional[str] = Field(None, description="Converted markdown content")
    metadata: Optional[ConversionMetadata] = Field(None, description="Conversion metadata")
    error: Optional[str] = Field(None, description="Error message if conversion failed")
    file_path: Optional[str] = Field(None, description="Output file path if saved")


class JobResponse(BaseModel):
    """Response schema for job creation."""

    job_id: str = Field(..., description="Unique job identifier")
    status: JobStatus = Field(..., description="Current job status")
    queue: str = Field(..., description="Queue name")
    estimated_completion: Optional[str] = Field(None, description="Estimated completion time")
    created_at: datetime = Field(default_factory=datetime.utcnow, description="Job creation time")


class JobStatusResponse(BaseModel):
    """Response schema for job status query."""

    job_id: str = Field(..., description="Unique job identifier")
    status: JobStatus = Field(..., description="Current job status")
    queue: str = Field(..., description="Queue name")
    result: Optional[Any] = Field(None, description="Job result if completed")
    error: Optional[str] = Field(None, description="Error message if failed")
    created_at: Optional[datetime] = Field(None, description="Job creation time")
    started_at: Optional[datetime] = Field(None, description="Job start time")
    ended_at: Optional[datetime] = Field(None, description="Job end time")
    progress: Optional[dict[str, Any]] = Field(None, description="Progress information")


class BatchJobResponse(BaseModel):
    """Response schema for batch job creation."""

    job_id: str = Field(..., description="Unique job identifier")
    status: JobStatus = Field(..., description="Current job status")
    queue: str = Field(..., description="Queue name")
    item_count: int = Field(..., description="Number of items to process")
    estimated_completion: Optional[str] = Field(None, description="Estimated completion time")
    created_at: datetime = Field(default_factory=datetime.utcnow, description="Job creation time")


class HealthResponse(BaseModel):
    """Response schema for health check."""

    status: str = Field(..., description="Service status")
    version: str = Field(..., description="API version")
    uptime_seconds: float = Field(..., description="Uptime in seconds")
    services: dict[str, bool] = Field(default_factory=dict, description="Service availability")
    queue_stats: Optional[dict[str, Any]] = Field(None, description="Queue statistics")


class ErrorResponse(BaseModel):
    """Standard error response."""

    error: str = Field(..., description="Error message")
    detail: Optional[str] = Field(None, description="Detailed error information")
    status_code: int = Field(..., description="HTTP status code")


class EventMessage(BaseModel):
    """Server-sent event message."""

    event: str = Field(..., description="Event type")
    data: dict[str, Any] = Field(..., description="Event data")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Event timestamp")
