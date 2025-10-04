"""Prometheus metrics definitions and tracking for Gobbler MCP server."""

import time
from typing import Optional

import psutil
from prometheus_client import (
    CONTENT_TYPE_LATEST,
    CollectorRegistry,
    Counter,
    Gauge,
    Histogram,
    Info,
    generate_latest,
)

# Create registry
registry = CollectorRegistry()

# Application info
app_info = Info(
    "gobbler_app",
    "Gobbler MCP Server Information",
    registry=registry,
)
app_info.info({
    "version": "0.1.0",
    "python_version": "3.11",
})

# Conversion metrics
conversion_total = Counter(
    "gobbler_conversions_total",
    "Total number of conversions attempted",
    ["converter_type", "status"],  # labels: youtube/audio/webpage/document, success/failure
    registry=registry,
)

conversion_duration = Histogram(
    "gobbler_conversion_duration_seconds",
    "Time spent on conversions",
    ["converter_type"],
    buckets=[0.5, 1, 2, 5, 10, 30, 60, 120, 300],  # 0.5s to 5min
    registry=registry,
)

conversion_size = Histogram(
    "gobbler_conversion_size_bytes",
    "Size of content converted",
    ["converter_type"],
    buckets=[1024, 10240, 102400, 1048576, 10485760, 104857600],  # 1KB to 100MB
    registry=registry,
)

# Queue metrics
queue_depth = Gauge(
    "gobbler_queue_depth",
    "Number of jobs in queue",
    ["queue_name"],  # default, transcription, download
    registry=registry,
)

queue_processing_time = Histogram(
    "gobbler_queue_processing_seconds",
    "Time spent processing queued jobs",
    ["queue_name", "job_type"],
    buckets=[1, 5, 10, 30, 60, 300, 600, 1800],  # 1s to 30min
    registry=registry,
)

# Service health metrics
service_up = Gauge(
    "gobbler_service_up",
    "Service health status (1=up, 0=down)",
    ["service_name"],  # crawl4ai, docling, redis
    registry=registry,
)

service_response_time = Histogram(
    "gobbler_service_response_seconds",
    "Service response time",
    ["service_name"],
    buckets=[0.1, 0.5, 1, 2, 5, 10],  # 100ms to 10s
    registry=registry,
)

# Worker metrics
worker_active = Gauge(
    "gobbler_workers_active",
    "Number of active workers",
    registry=registry,
)

worker_idle_time = Histogram(
    "gobbler_worker_idle_seconds",
    "Time workers spend idle between jobs",
    buckets=[1, 5, 10, 30, 60, 300],  # 1s to 5min
    registry=registry,
)

# Resource metrics
cpu_usage = Gauge(
    "gobbler_cpu_usage_percent",
    "CPU usage percentage",
    registry=registry,
)

memory_usage = Gauge(
    "gobbler_memory_usage_bytes",
    "Memory usage in bytes",
    registry=registry,
)

disk_usage = Gauge(
    "gobbler_disk_usage_percent",
    "Disk usage percentage",
    ["mount_point"],
    registry=registry,
)

# Error tracking
errors_total = Counter(
    "gobbler_errors_total",
    "Total errors encountered",
    ["error_type", "converter_type"],
    registry=registry,
)

# Batch processing metrics
batch_operations_total = Counter(
    "gobbler_batch_operations_total",
    "Total batch operations",
    ["batch_type", "status"],  # youtube_playlist/webpages/audio/documents, success/failure
    registry=registry,
)

batch_items_processed = Counter(
    "gobbler_batch_items_processed_total",
    "Total items processed in batch operations",
    ["batch_type", "status"],  # success/failure/skipped
    registry=registry,
)


class ConversionTracker:
    """Context manager for tracking conversion operations."""

    def __init__(self, converter_type: str):
        """
        Initialize conversion tracker.

        Args:
            converter_type: Type of converter (youtube, audio, webpage, document)
        """
        self.converter_type = converter_type
        self.start_time: Optional[float] = None

    def __enter__(self) -> "ConversionTracker":
        """Start tracking conversion."""
        self.start_time = time.time()
        return self

    def __exit__(
        self,
        exc_type: Optional[type],
        exc_val: Optional[BaseException],
        exc_tb: Optional[object],
    ) -> None:
        """
        Stop tracking and record metrics.

        Args:
            exc_type: Exception type if error occurred
            exc_val: Exception value if error occurred
            exc_tb: Exception traceback if error occurred
        """
        if self.start_time is None:
            return

        duration = time.time() - self.start_time
        conversion_duration.labels(converter_type=self.converter_type).observe(duration)

        if exc_type is None:
            # Success
            conversion_total.labels(
                converter_type=self.converter_type, status="success"
            ).inc()
        else:
            # Failure
            conversion_total.labels(
                converter_type=self.converter_type, status="failure"
            ).inc()
            errors_total.labels(
                error_type=exc_type.__name__, converter_type=self.converter_type
            ).inc()


def track_conversion(converter_type: str) -> ConversionTracker:
    """
    Create context manager for tracking conversions.

    Args:
        converter_type: Type of converter (youtube, audio, webpage, document)

    Returns:
        ConversionTracker context manager

    Example:
        with track_conversion('youtube'):
            # conversion logic
            pass
    """
    return ConversionTracker(converter_type)


def update_resource_metrics() -> None:
    """Update system resource metrics (CPU, memory, disk)."""
    try:
        # CPU usage
        cpu_usage.set(psutil.cpu_percent(interval=0.1))

        # Memory usage
        memory = psutil.virtual_memory()
        memory_usage.set(memory.used)

        # Disk usage for all partitions
        for partition in psutil.disk_partitions():
            try:
                usage = psutil.disk_usage(partition.mountpoint)
                disk_usage.labels(mount_point=partition.mountpoint).set(usage.percent)
            except (PermissionError, OSError):
                # Skip partitions we can't access
                pass
    except Exception:
        # Don't let metrics collection crash the application
        pass


def update_queue_metrics() -> None:
    """Update queue depth metrics from Redis."""
    try:
        from .utils.queue import get_queue

        for queue_name in ["default", "transcription", "download"]:
            try:
                queue = get_queue(queue_name)
                depth = len(queue)
                queue_depth.labels(queue_name=queue_name).set(depth)
            except Exception:
                # Queue might not be available (Redis down)
                pass
    except Exception:
        # Don't let metrics collection crash the application
        pass


def get_metrics() -> tuple[bytes, str]:
    """
    Get Prometheus metrics in text format.

    Returns:
        Tuple of (metrics_data, content_type)
    """
    # Update dynamic metrics before generating output
    update_resource_metrics()
    update_queue_metrics()

    return generate_latest(registry), CONTENT_TYPE_LATEST
