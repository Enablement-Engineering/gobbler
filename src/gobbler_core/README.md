# gobbler_core

Shared, portable core library for Gobbler content conversion.

## Overview

`gobbler_core` provides standalone converters and utilities that can be used
independently of the MCP server. This package has no MCP dependencies and
can be used in any Python application.

## Modules

### Converters

- `audio.py` - Audio/video transcription with Whisper
- `document.py` - Document conversion via Docling
- `webpage.py` - Webpage conversion via Crawl4AI
- `youtube.py` - YouTube transcript extraction

### Providers

- `youtube.py` - YouTube transcript API providers with fallback chain

### Utilities

- `file_handler.py` - File validation and saving
- `frontmatter.py` - YAML frontmatter generation
- `health.py` - Service health checking
- `http_client.py` - Retryable HTTP client

## Usage

```python
from gobbler_core.converters import convert_youtube_to_markdown

# Convert YouTube video to markdown
markdown, metadata = await convert_youtube_to_markdown(
    "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
    include_timestamps=True
)
```

## Architecture

This package is designed to be:
- **Standalone**: No MCP or server dependencies
- **Portable**: Can be used in skills, scripts, or other applications
- **Testable**: All external services are mockable

The `gobbler_mcp` package re-exports from this package and adds MCP-specific
functionality.
