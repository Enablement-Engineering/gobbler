# gobbler_core

Shared, portable core library for Gobbler content conversion.

## Overview

`gobbler_core` provides standalone converters and utilities used by the Gobbler
CLI, skills, scripts, and other Python applications.

## Modules

### Converters

- `audio.py` - Audio/video transcription with Whisper
- `document.py` - Document conversion via Docling
- `webpage.py` - Webpage conversion via Crawl4AI
- `youtube.py` - YouTube transcript extraction

### Providers

- `transcription/` - local faster-whisper and OpenAI Whisper API providers
- `document/` - Docling HTTP provider
- `webpage/` - Crawl4AI HTTP provider
- `youtube.py` - transcript-specific providers and fallback chain

Converters orchestrate these provider interfaces; providers are not themselves converters. The
YouTube provider family is a separate synchronous interface from the generic registry-backed
transcription/document/webpage families.

### Utilities

- `file_handler.py` - File validation and saving
- `frontmatter.py` - YAML frontmatter generation
- `health.py` - Service health checking
- `http_client.py` - Retryable HTTP client
- `config.py` - YAML defaults, deep merge, and service endpoint lookup
- `providers/fallback.py` and `providers/proxy.py` - library-level fallback/proxy composition
- `redaction.py` - diagnostic secret and URL sanitization
- `selectors.py` - selector normalization for webpage conversion

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
- **Standalone**: No protocol-server dependencies
- **Portable**: Can be used in skills, scripts, or other applications
- **Testable**: All external services are mockable

The Gobbler CLI imports these modules directly for conversion workflows.

The CLI is the stable public automation surface. Python imports are useful for
in-repository development but may evolve during the active beta.
