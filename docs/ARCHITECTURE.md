---
icon: material/sitemap
---

# Gobbler Architecture

This document provides an in-depth explanation of Gobbler's architecture, design decisions, and integration strategies.

## Table of Contents

- [Overview](#overview)
- [Component Architecture](#component-architecture)
- [Design Decisions](#design-decisions)
- [Integration Patterns](#integration-patterns)

## Overview

Gobbler converts content to markdown through three interfaces that share the same backend:

- **CLI** - Direct command-line usage (`gobbler youtube URL`)
- **MCP Server** - For Claude Desktop/Code via Model Context Protocol
- **Skills** - Context-efficient UV scripts for Claude Code

All three interfaces call the same provider layer, which connects to:

- **YouTube APIs** - Transcript extraction
- **Crawl4AI** (Docker) - Web scraping with JavaScript rendering
- **Docling** (Docker) - Document conversion with OCR
- **faster-whisper** - Local audio transcription
- **Browser Relay** - WebSocket to browser extension

## Component Architecture

### MCP Server Layer

The MCP server coordinates all operations and manages service communication:

**Responsibilities:**
- MCP protocol handling (JSON-RPC over stdio)
- Tool routing and parameter validation
- Service health monitoring
- Auto-queue decision logic
- Configuration management

**Implementation:**
- Built on FastMCP framework
- Runs as stdio server for Claude Code/Desktop
- No HTTP server (except relay for browser extension)

### Provider Layer

The provider layer implements a **pluggable backend abstraction** that enables swapping between different implementations for the same functionality:

- **Multiple backends**: Different providers for the same category (e.g., local vs API-based transcription)
- **Configuration-driven selection**: Switch providers via config without code changes
- **Graceful fallback**: Automatic fallback between providers on failure

| Category | Provider | Description |
|----------|----------|-------------|
| Transcription | `whisper-local` | Local faster-whisper with CoreML acceleration |
| Document | `docling` | Docling Docker service for PDF, DOCX, PPTX, XLSX |
| Webpage | `crawl4ai` | Crawl4AI Docker service with JavaScript rendering |
| YouTube | Multiple | Auto-fallback between free and paid transcript APIs |
| Browser | Relay | WebSocket relay to browser extension |

For detailed provider documentation, configuration, and implementation patterns, see [Providers](providers.md).

**Configuration Resolution:**

```python
from gobbler_mcp.config import get_config

config = get_config()

# Get default provider for category
default_name = config.providers["transcription"]["default"]  # "whisper-local"

# Get provider-specific config
provider_config = config.providers["transcription"]["whisper-local"]
# {"model": "small", "device": "auto", "compute_type": "float16"}

# Create provider with config
provider = ProviderRegistry.create(
    category="transcription",
    name=default_name,
    **provider_config
)
```

**CLI Override:**

Users can override the default provider via CLI flags:

```bash
# Use default from config
gobbler audio transcribe audio.mp3

# Override with specific provider
gobbler audio transcribe audio.mp3 --provider whisper-local

# Override with provider + options
gobbler audio transcribe audio.mp3 --provider whisper-local --model large-v3
```

#### Available Providers

**Transcription Providers:**

| Provider | Description |
|----------|-------------|
| `whisper-local` | Local faster-whisper with CoreML acceleration |

**Document Providers:**

| Provider | Description |
|----------|-------------|
| `docling` | Docling Docker service for PDF, DOCX, PPTX, XLSX |

**Webpage Providers:**

| Provider | Description |
|----------|-------------|
| `crawl4ai` | Crawl4AI Docker service with JavaScript rendering |

**YouTube Provider:**
- Multiple transcript APIs (youtube-transcript-api, TranscriptAPI.com)
- Auto-fallback strategy between providers
- Video metadata extraction
- Download capabilities via yt-dlp

**Browser Provider:**
- WebSocket relay to browser extension
- Tab group security model
- JavaScript execution interface
- Content extraction

For detailed provider documentation, see [Providers](providers.md).

### Services Layer

Docker-based services provide specialized processing:

**Crawl4AI (Port 11235):**
- JavaScript rendering via Playwright
- Session persistence (cookies, localStorage)
- Content extraction with selectors
- Markdown conversion

**Docling (Port 5001):**
- Document structure analysis
- OCR via Tesseract
- Table extraction
- Markdown generation

### Queue System

SQLite-based background processing for long-running operations:

**Auto-Queue Logic:**
- Tasks estimated >1:45 automatically queue
- Returns job_id and ETA to user
- Real-time progress tracking
- Retry with exponential backoff

**Queues:**
- `default` - General background tasks
- `transcription` - Audio/video transcription
- `download` - YouTube video downloads

**Worker:**
- Executes via same provider layer as MCP server
- Updates progress in SQLite database

## Design Decisions

### Why Tab Group Security Model?

**Problem:** Browser automation could accidentally access sensitive tabs (banking, email, etc.)

**Solution:** Only tabs explicitly added to "Gobbler" group are accessible to Claude.

**Benefits:**
- User maintains explicit control
- Visual indicator (orange group color)
- Prevents accidental data leakage
- Easy to add/remove tabs

## Integration Patterns

### Provider Interface Pattern

Gobbler uses a registry-based provider pattern for extensible backend support. Each provider category has:

1. **Abstract base class** defining the interface
2. **Registry** for provider discovery and instantiation
3. **Concrete implementations** for each backend

#### Transcription Provider Example

```python
# Base class in gobbler_core/providers/transcription/base.py
class TranscriptionProvider(ABC):
    """Abstract base for transcription providers."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Provider identifier (e.g., 'whisper-local')."""

    @abstractmethod
    async def transcribe(
        self,
        audio_path: Path,
        language: str = "auto",
        **options,
    ) -> TranscriptionResult:
        """Transcribe audio to text."""

    @abstractmethod
    def supports_format(self, extension: str) -> bool:
        """Check if format is supported."""
```

#### Provider Registration

```python
# In gobbler_core/providers/transcription/whisper.py
from gobbler_core.providers.registry import ProviderRegistry

class WhisperLocalProvider(TranscriptionProvider):
    @property
    def name(self) -> str:
        return "whisper-local"

    async def transcribe(self, audio_path, language="auto", **options):
        # Implementation using faster-whisper
        ...

# Self-register at import time
ProviderRegistry.register("transcription", "whisper-local", WhisperLocalProvider)
```

#### Provider Usage

```python
from gobbler_core.providers import ProviderRegistry

# Create from registry
provider = ProviderRegistry.create("transcription", "whisper-local", model="small")

# Use the provider
result = await provider.transcribe(Path("audio.mp3"), language="en")
print(result.text)
```

#### YouTube Provider (Legacy Pattern)

The YouTube provider uses a similar but separate pattern with auto-fallback:

```python
class TranscriptProvider:
    """Abstract base for transcript providers"""
    def fetch(self, video_id, language, include_timestamps):
        ...

class YouTubeTranscriptAPIProvider(TranscriptProvider):
    """Free API with IP blocking risk"""
    ...

class TranscriptAPIProvider(TranscriptProvider):
    """Paid API, no IP blocks"""
    ...

class AutoFallbackProvider(TranscriptProvider):
    """Try free → paid on failure"""
    ...
```

This pattern enables:
- Multiple backends for same capability
- Easy addition of new providers
- Graceful fallback between providers
- User choice of cost/reliability tradeoffs

For detailed provider documentation, see [Providers](providers.md).

### Batch Processing Pattern

All batch operations follow this pattern:

1. Validate input items and limits
2. Check auto_queue threshold
3. If queued: Return batch_id, start background processing
4. If immediate: Process with concurrency control
5. Track progress in shared state
6. Generate summary report

**Benefits:**
- Consistent UX across batch operations
- Real-time progress tracking
- Automatic resource management
- Fail-fast validation

### Health Check Pattern

All external services implement health checks:

```python
class ServiceHealthChecker:
    def check_crawl4ai() -> HealthStatus
    def check_docling() -> HealthStatus
    def check_all() -> Dict[str, HealthStatus]
```

**Benefits:**
- Early failure detection
- Clear error messages
- Service status visibility
- Automated monitoring

### Frontmatter Pattern

All converters generate YAML frontmatter:

```python
def generate_frontmatter(content_type, metadata):
    """Standardized frontmatter for all content types"""
    return {
        "source": url,
        "type": content_type,
        "converted_at": timestamp,
        ...metadata
    }
```

**Benefits:**
- Consistent metadata format
- Easy parsing and filtering
- Preserved provenance
- Rich context for AI

