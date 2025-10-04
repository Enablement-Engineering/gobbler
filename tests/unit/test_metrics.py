"""Unit tests for Prometheus metrics."""

import pytest
from prometheus_client import REGISTRY

from gobbler_mcp.metrics import (
    conversion_duration,
    conversion_size,
    conversion_total,
    errors_total,
    get_metrics,
    track_conversion,
)


@pytest.fixture
def clear_metrics():
    """Clear metrics before each test."""
    # Note: In real tests, we'd use a separate registry per test
    # For now, we just track deltas
    yield
    # Cleanup handled by registry


def test_track_conversion_success(clear_metrics):
    """Test successful conversion tracking."""
    converter_type = "test_success"

    # Get initial count
    initial_success = conversion_total.labels(
        converter_type=converter_type, status="success"
    )._value._value

    # Track a successful conversion
    with track_conversion(converter_type):
        pass  # Simulate successful conversion

    # Verify success counter incremented
    final_success = conversion_total.labels(
        converter_type=converter_type, status="success"
    )._value._value

    assert final_success == initial_success + 1


def test_track_conversion_failure(clear_metrics):
    """Test failed conversion tracking."""
    converter_type = "test_failure"

    # Get initial counts
    initial_failure = conversion_total.labels(
        converter_type=converter_type, status="failure"
    )._value._value
    initial_error = errors_total.labels(
        error_type="ValueError", converter_type=converter_type
    )._value._value

    # Track a failed conversion
    with pytest.raises(ValueError):
        with track_conversion(converter_type):
            raise ValueError("Test error")

    # Verify failure counter incremented
    final_failure = conversion_total.labels(
        converter_type=converter_type, status="failure"
    )._value._value
    final_error = errors_total.labels(
        error_type="ValueError", converter_type=converter_type
    )._value._value

    assert final_failure == initial_failure + 1
    assert final_error == initial_error + 1


def test_track_conversion_duration(clear_metrics):
    """Test conversion duration tracking."""
    import time

    converter_type = "test_duration"

    # Track conversion with sleep
    with track_conversion(converter_type):
        time.sleep(0.1)  # Sleep for 100ms

    # Get histogram sum (total duration)
    histogram = conversion_duration.labels(converter_type=converter_type)
    # Verify histogram recorded the duration (should be ~0.1 seconds)
    assert histogram._sum._value >= 0.1


def test_conversion_size_tracking(clear_metrics):
    """Test conversion size metric."""
    converter_type = "test_size"
    content_size = 1024 * 50  # 50KB

    # Track size
    conversion_size.labels(converter_type=converter_type).observe(content_size)

    # Verify histogram recorded the size
    histogram = conversion_size.labels(converter_type=converter_type)
    assert histogram._sum._value >= content_size


def test_get_metrics_returns_prometheus_format():
    """Test metrics can be exported in Prometheus format."""
    metrics_data, content_type = get_metrics()

    # Verify content type (format may vary by prometheus_client version)
    assert "text/plain" in content_type
    assert "charset=utf-8" in content_type

    # Verify metrics data is bytes
    assert isinstance(metrics_data, bytes)

    # Verify contains metric names
    metrics_text = metrics_data.decode("utf-8")
    assert "gobbler_conversions_total" in metrics_text
    assert "gobbler_conversion_duration_seconds" in metrics_text
    assert "gobbler_app_info" in metrics_text


def test_get_metrics_includes_resource_metrics():
    """Test that get_metrics includes resource metrics."""
    metrics_data, _ = get_metrics()
    metrics_text = metrics_data.decode("utf-8")

    # Verify resource metrics are included
    assert "gobbler_cpu_usage_percent" in metrics_text
    assert "gobbler_memory_usage_bytes" in metrics_text


def test_conversion_tracker_context_manager():
    """Test ConversionTracker as context manager."""
    converter_type = "test_context"

    tracker = track_conversion(converter_type)

    # Verify it's a context manager
    assert hasattr(tracker, "__enter__")
    assert hasattr(tracker, "__exit__")

    # Use it
    with tracker:
        assert tracker.start_time is not None


def test_multiple_converter_types():
    """Test tracking different converter types."""
    # Track multiple conversions
    with track_conversion("youtube"):
        pass

    with track_conversion("audio"):
        pass

    with track_conversion("webpage"):
        pass

    # Get metrics
    metrics_data, _ = get_metrics()
    metrics_text = metrics_data.decode("utf-8")

    # Verify all converter types are present
    assert 'converter_type="youtube"' in metrics_text
    assert 'converter_type="audio"' in metrics_text
    assert 'converter_type="webpage"' in metrics_text


def test_error_types_tracked_separately():
    """Test different error types are tracked separately."""
    converter_type = "test_errors"

    # Track ValueError
    with pytest.raises(ValueError):
        with track_conversion(converter_type):
            raise ValueError("Test error 1")

    # Track TypeError
    with pytest.raises(TypeError):
        with track_conversion(converter_type):
            raise TypeError("Test error 2")

    # Get metrics
    metrics_data, _ = get_metrics()
    metrics_text = metrics_data.decode("utf-8")

    # Verify both error types are tracked
    assert 'error_type="ValueError"' in metrics_text
    assert 'error_type="TypeError"' in metrics_text
