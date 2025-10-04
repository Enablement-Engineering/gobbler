"""Unit tests for structured logging configuration."""

import json
import logging
from io import StringIO

import pytest

from gobbler_mcp.logging_config import (
    StructuredFormatter,
    get_logger_with_context,
    setup_logging,
)


def test_structured_formatter_basic():
    """Test basic JSON formatting."""
    formatter = StructuredFormatter()
    record = logging.LogRecord(
        name="test.logger",
        level=logging.INFO,
        pathname="test.py",
        lineno=42,
        msg="Test message",
        args=(),
        exc_info=None,
        func="test_func",
    )

    output = formatter.format(record)
    data = json.loads(output)

    assert data["level"] == "INFO"
    assert data["logger"] == "test.logger"
    assert data["message"] == "Test message"
    assert data["module"] == "test"
    assert data["function"] == "test_func"
    assert data["line"] == 42
    assert "timestamp" in data


def test_structured_formatter_with_exception():
    """Test JSON formatting with exception info."""
    formatter = StructuredFormatter()

    try:
        raise ValueError("Test error")
    except ValueError:
        import sys

        exc_info = sys.exc_info()

    record = logging.LogRecord(
        name="test.logger",
        level=logging.ERROR,
        pathname="test.py",
        lineno=42,
        msg="Error occurred",
        args=(),
        exc_info=exc_info,
        func="test_func",
    )

    output = formatter.format(record)
    data = json.loads(output)

    assert "exception" in data
    assert data["exception"]["type"] == "ValueError"
    assert data["exception"]["message"] == "Test error"
    assert "traceback" in data["exception"]


def test_structured_formatter_with_extra_fields():
    """Test JSON formatting with extra fields."""
    formatter = StructuredFormatter()
    record = logging.LogRecord(
        name="test.logger",
        level=logging.INFO,
        pathname="test.py",
        lineno=42,
        msg="Test message",
        args=(),
        exc_info=None,
        func="test_func",
    )

    # Add extra fields
    record.extra_fields = {
        "converter_type": "youtube",
        "video_id": "abc123",
        "duration": 1.5,
    }

    output = formatter.format(record)
    data = json.loads(output)

    assert data["converter_type"] == "youtube"
    assert data["video_id"] == "abc123"
    assert data["duration"] == 1.5


def test_setup_logging_text_format():
    """Test text logging setup."""
    logger_name = "test.text.logger"
    setup_logging(level="DEBUG", format="text", logger_name=logger_name)

    logger = logging.getLogger(logger_name)
    assert logger.level == logging.DEBUG
    assert len(logger.handlers) == 1
    assert not isinstance(logger.handlers[0].formatter, StructuredFormatter)


def test_setup_logging_json_format():
    """Test JSON logging setup."""
    logger_name = "test.json.logger"
    setup_logging(level="INFO", format="json", logger_name=logger_name)

    logger = logging.getLogger(logger_name)
    assert logger.level == logging.INFO
    assert len(logger.handlers) == 1
    assert isinstance(logger.handlers[0].formatter, StructuredFormatter)


def test_setup_logging_removes_duplicate_handlers():
    """Test that setting up logging twice doesn't duplicate handlers."""
    logger_name = "test.duplicate.logger"

    setup_logging(logger_name=logger_name)
    setup_logging(logger_name=logger_name)

    logger = logging.getLogger(logger_name)
    assert len(logger.handlers) == 1


def test_get_logger_with_context():
    """Test context logger adapter."""
    logger_name = "test.context.logger"
    context = {"converter_type": "youtube", "session_id": "abc123"}

    adapter = get_logger_with_context(logger_name, **context)

    # Capture log output
    stream = StringIO()
    handler = logging.StreamHandler(stream)
    handler.setFormatter(StructuredFormatter())

    base_logger = logging.getLogger(logger_name)
    base_logger.addHandler(handler)
    base_logger.setLevel(logging.INFO)

    adapter.info("Test message")

    output = stream.getvalue()
    data = json.loads(output)

    assert data["message"] == "Test message"
    assert data["converter_type"] == "youtube"
    assert data["session_id"] == "abc123"

    # Cleanup
    base_logger.removeHandler(handler)


def test_logger_with_context_extra_fields():
    """Test context logger with additional extra fields."""
    logger_name = "test.context.extra.logger"
    context = {"converter_type": "audio"}

    adapter = get_logger_with_context(logger_name, **context)

    # Capture log output
    stream = StringIO()
    handler = logging.StreamHandler(stream)
    handler.setFormatter(StructuredFormatter())

    base_logger = logging.getLogger(logger_name)
    base_logger.addHandler(handler)
    base_logger.setLevel(logging.INFO)

    # Log with additional extra fields
    adapter.info(
        "Processing file",
        extra={"extra_fields": {"file_path": "/tmp/test.mp3", "size": 1024}},
    )

    output = stream.getvalue()
    data = json.loads(output)

    assert data["converter_type"] == "audio"  # From context
    assert data["file_path"] == "/tmp/test.mp3"  # From extra
    assert data["size"] == 1024  # From extra

    # Cleanup
    base_logger.removeHandler(handler)
