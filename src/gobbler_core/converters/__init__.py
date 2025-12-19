"""Content converters for transforming various formats to markdown.

All converters are decoupled from infrastructure (config, metrics) and accept
optional parameters for customization. They work standalone or can be wrapped
by gobbler_mcp to inject infrastructure.

Usage:
    from gobbler_core.converters import convert_youtube_to_markdown

    # Basic usage (uses defaults)
    markdown, metadata = await convert_youtube_to_markdown(video_url)

    # With custom metrics callback
    markdown, metadata = await convert_youtube_to_markdown(
        video_url,
        metrics_callback=lambda t, s: print(f"Converted {s} bytes")
    )
"""

from gobbler_core.converters.youtube import convert_youtube_to_markdown
from gobbler_core.converters.webpage import convert_webpage_to_markdown
from gobbler_core.converters.document import convert_document_to_markdown
from gobbler_core.converters.audio import convert_audio_to_markdown

__all__ = [
    "convert_youtube_to_markdown",
    "convert_webpage_to_markdown",
    "convert_document_to_markdown",
    "convert_audio_to_markdown",
]
