"""Converter modules for MCP tools.

Most converters live in gobbler_core for standalone use.
This module re-exports them for backwards compatibility with
existing imports from gobbler_mcp.converters.

The webpage_selector converter remains here as it has MCP-specific
dependencies (crawl sessions, etc.).
"""

# Re-export core converters for backwards compatibility
from gobbler_core.converters import (
    convert_audio_to_markdown,
    convert_document_to_markdown,
    convert_webpage_to_markdown,
    convert_youtube_to_markdown,
)

# MCP-specific converters
from .webpage_selector import convert_webpage_with_selector

__all__ = [
    # Core converters (re-exported from gobbler_core)
    "convert_audio_to_markdown",
    "convert_document_to_markdown",
    "convert_webpage_to_markdown",
    "convert_youtube_to_markdown",
    # MCP-specific converters
    "convert_webpage_with_selector",
]
