"""Gobbler MCP utilities - re-exported from gobbler_core.

This module re-exports utilities from gobbler_core for backwards compatibility
with existing imports from gobbler_mcp.utils. The metrics_helpers module
remains here as it has MCP-specific dependencies.
"""

from gobbler_core.utils.file_handler import (
    get_file_extension,
    save_markdown_file,
    validate_input_path,
    validate_output_path,
)
from gobbler_core.utils.frontmatter import (
    count_words,
    create_audio_frontmatter,
    create_document_frontmatter,
    create_frontmatter,
    create_webpage_frontmatter,
    create_youtube_frontmatter,
    get_iso8601_timestamp,
)
from gobbler_core.utils.health import ServiceHealth, get_service_unavailable_error
from gobbler_core.utils.http_client import RetryableHTTPClient

# MCP-specific utilities
from .metrics_helpers import get_metrics_callback

__all__ = [
    "RetryableHTTPClient",
    "ServiceHealth",
    "count_words",
    "create_audio_frontmatter",
    "create_document_frontmatter",
    "create_frontmatter",
    "create_webpage_frontmatter",
    "create_youtube_frontmatter",
    "get_file_extension",
    "get_iso8601_timestamp",
    "get_metrics_callback",
    "get_service_unavailable_error",
    "save_markdown_file",
    "validate_input_path",
    "validate_output_path",
]
