"""Gobbler Core - Shared providers and utilities for content processing.

This package contains portable, standalone functionality that can be used
by both gobbler-mcp (MCP server) and skill scripts without dependencies
on MCP infrastructure.

What's included:
- providers/  - Content source providers (YouTube transcripts, etc.)
- utils/      - Frontmatter generation, HTTP client, file handling

Usage:
    # YouTube transcription
    from gobbler_core.providers.youtube import AutoFallbackProvider
    provider = AutoFallbackProvider(api_key="...")
    result = provider.fetch(video_id, language="en")

    # Utilities
    from gobbler_core.utils import create_frontmatter
    output = create_frontmatter(metadata) + content

Note: Converters (webpage, document, audio) remain in gobbler_mcp as they
depend on configuration and metrics infrastructure. Skills can use the
providers directly or call MCP tools for full conversion.
"""

__version__ = "0.2.0"

# Convenience imports for common use cases
from gobbler_core.providers.youtube import (
    AutoFallbackProvider,
    TranscriptAPIProvider,
    TranscriptProvider,
    TranscriptResult,
    TranscriptSegment,
    YouTubeTranscriptAPIProvider,
    create_provider,
)

__all__ = [
    "AutoFallbackProvider",
    "TranscriptAPIProvider",
    "TranscriptProvider",
    "TranscriptResult",
    "TranscriptSegment",
    "YouTubeTranscriptAPIProvider",
    "__version__",
    "create_provider",
]
