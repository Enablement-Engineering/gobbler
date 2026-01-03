"""Utility functions for content processing."""

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

__all__ = [
    # Frontmatter
    "create_frontmatter",
    "create_youtube_frontmatter",
    "create_webpage_frontmatter",
    "create_document_frontmatter",
    "create_audio_frontmatter",
    "count_words",
    "get_iso8601_timestamp",
    # File handling
    "save_markdown_file",
    "validate_output_path",
    "validate_input_path",
    "get_file_extension",
    # HTTP client
    "RetryableHTTPClient",
    # Health checks
    "ServiceHealth",
    "get_service_unavailable_error",
]
