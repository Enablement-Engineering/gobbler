"""Structured logging configuration for Gobbler MCP server.

Supports both JSON (production) and text (development/MCP) logging formats.
"""

import json
import logging
import sys
from datetime import datetime, timezone
from typing import Any, Dict, Optional


class StructuredFormatter(logging.Formatter):
    """JSON formatter for structured logging."""

    def format(self, record: logging.LogRecord) -> str:
        """
        Format log record as JSON.

        Args:
            record: Log record to format

        Returns:
            JSON-formatted log string
        """
        log_data: Dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }

        # Add exception info if present
        if record.exc_info:
            log_data["exception"] = {
                "type": record.exc_info[0].__name__,
                "message": str(record.exc_info[1]),
                "traceback": self.formatException(record.exc_info),
            }

        # Add extra fields if present
        if hasattr(record, "extra_fields"):
            log_data.update(record.extra_fields)

        return json.dumps(log_data)


def setup_logging(
    level: str = "INFO",
    format: str = "text",
    logger_name: Optional[str] = None,
) -> None:
    """
    Configure application logging.

    Args:
        level: Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        format: 'json' for structured logging, 'text' for human-readable
        logger_name: Specific logger to configure. If None, configures root logger.
    """
    # Get logger
    target_logger = logging.getLogger(logger_name)
    target_logger.setLevel(level)

    # Remove existing handlers to avoid duplicates
    for handler in target_logger.handlers[:]:
        target_logger.removeHandler(handler)

    # Create stderr handler (required for MCP stdio transport)
    handler = logging.StreamHandler(sys.stderr)

    # Set formatter based on format type
    if format == "json":
        handler.setFormatter(StructuredFormatter())
    else:
        # Text format (default for MCP compatibility)
        handler.setFormatter(
            logging.Formatter(
                "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
            )
        )

    target_logger.addHandler(handler)

    # Prevent propagation to root logger if configuring a specific logger
    if logger_name is not None:
        target_logger.propagate = False


def get_logger_with_context(name: str, **context: Any) -> logging.LoggerAdapter:
    """
    Get logger with context fields automatically added to all log messages.

    Args:
        name: Logger name
        **context: Context fields to add to all log messages

    Returns:
        LoggerAdapter with context
    """

    class ContextAdapter(logging.LoggerAdapter):
        """Adapter that adds context fields to log records."""

        def process(
            self, msg: str, kwargs: Dict[str, Any]
        ) -> tuple[str, Dict[str, Any]]:
            """Add context fields to extra."""
            extra = kwargs.get("extra", {})
            if "extra_fields" not in extra:
                extra["extra_fields"] = {}
            extra["extra_fields"].update(self.extra)
            kwargs["extra"] = extra
            return msg, kwargs

    logger = logging.getLogger(name)
    return ContextAdapter(logger, context)
