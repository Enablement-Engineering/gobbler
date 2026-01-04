---
icon: material/sitemap
---

# Gobbler Architecture

This document provides an in-depth explanation of Gobbler's architecture, design decisions, and integration strategies.

## Table of Contents

- [Overview](#overview)
- [Skills vs MCP Integration](#skills-vs-mcp-integration)
- [Component Architecture](#component-architecture)
- [Design Decisions](#design-decisions)
- [Integration Patterns](#integration-patterns)

## Overview

Gobbler is designed as a Model Context Protocol (MCP) server with a dual-interface approach: Skills for context-efficient operations and MCP tools for comprehensive functionality. Both interfaces share the same backend logic, providing flexibility in how you interact with Gobbler's capabilities.

## Skills vs MCP Integration

Gobbler provides two complementary interfaces to the same backend services: Skills and MCP Tools. Understanding when to use each approach is key to maximizing efficiency.

### Architecture Comparison

**Skills Path (Context-Efficient)**
- ~100 tokens of metadata loaded into Claude's context
- UV scripts execute directly, calling backend providers
- Progressive disclosure - only loaded when relevant
- Full Python scripting capabilities with CLI options
- Works standalone without MCP server running

**MCP Path (Full Toolset)**
- ~4,500 tokens of tool definitions always loaded
- MCP server coordinates all backend operations
- Persistent server state and session management
- Standardized tool interface across all MCP clients
- Server-side job queue for long-running operations

### Shared Backend Architecture

Both Skills and MCP Tools call the same backend providers:

```
┌─────────────────────────────────────────┐
│         Claude Code Interface            │
├────────────────────┬────────────────────┤
│   Skills (~100t)   │   MCP Tools (~4.5k)│
└─────────┬──────────┴──────────┬─────────┘
          │                     │
          └──────────┬──────────┘
                     │
          ┌──────────▼──────────┐
          │  Provider Layer      │
          │  - YouTube Provider  │
          │  - Crawl4AI Client   │
          │  - Docling Client    │
          │  - Whisper Provider  │
          │  - Browser Relay     │
          └──────────┬──────────┘
                     │
          ┌──────────▼──────────┐
          │  Services Layer      │
          │  - YouTube API       │
          │  - Crawl4AI :11235   │
          │  - Docling :5001     │
          │  - faster-whisper    │
          │  - WebSocket :4625   │
          └─────────────────────┘
```

### When to Use Skills vs MCP Tools

#### Use Skills When:

1. **Minimizing context overhead** - Working with limited context windows
2. **Interactive guidance needed** - Browser automation, multi-step workflows
3. **Exploratory tasks** - Discovering capabilities before committing
4. **Offline/standalone operation** - No MCP server available
5. **Complex scripting** - Need full Python flexibility

**Examples:**
- "Use the gobbler-browser skill to extract this page"
- "Run the notebooklm skill to query my notebook"
- "Transcribe this video using the gobbler-youtube skill"

#### Use MCP Tools When:

1. **Server-side job management** - Background queues for long operations
2. **Well-defined operations** - Single-purpose, straightforward tasks
3. **Tool chaining** - Combining multiple operations efficiently
4. **Automated pipelines** - Building reproducible workflows
5. **Batch processing** - Processing multiple items with progress tracking

**Examples:**
- "Transcribe this playlist with auto_queue enabled"
- "Convert all PDFs in this directory to markdown"
- "Crawl this documentation site and save all pages"

#### Both Work Equally Well For:

- Single file conversions (YouTube, webpage, document, audio)
- Simple browser operations without complex workflows
- One-shot content extraction tasks
- Individual document processing

### Integration Methods

Skills can call backend logic in two ways:

**Direct Import (Current - Standalone)**
```python
# Skill script imports provider directly
from gobbler_mcp.providers.youtube import AutoFallbackProvider
provider = AutoFallbackProvider()
result = provider.fetch(video_id, language)
```

**HTTP to Relay (Future - Integrated)**
```python
# Skill calls MCP server via HTTP relay
import httpx
response = httpx.post("http://localhost:4625/mcp/transcribe_youtube", json={...})
```

Both methods access the same backend logic. Direct import is simpler for standalone use; HTTP relay enables tighter integration with MCP server features.

### Decision Framework

Use this decision tree to choose the right approach:

```
Start
  │
  ├─ Need background queue? ────────────────► MCP Tools
  │
  ├─ Processing >10 items? ─────────────────► MCP Tools (batch)
  │
  ├─ Multi-step interactive workflow? ──────► Skills
  │
  ├─ Limited context window? ───────────────► Skills
  │
  ├─ MCP server not available? ─────────────► Skills
  │
  └─ Simple single operation? ──────────────► Either (choose based on context availability)
```

### Context Overhead Comparison

| Interface | Initial Load | Per Use | Total (5 uses) |
|-----------|--------------|---------|----------------|
| Skills | 100 tokens | ~500 tokens | ~2,600 tokens |
| MCP Tools | 4,500 tokens | ~100 tokens | ~5,000 tokens |

Skills become more efficient when:
- Used infrequently (1-2 times per session)
- Context window is constrained
- Interactive guidance reduces total operations

MCP Tools become more efficient when:
- Used frequently (5+ times per session)
- Chaining multiple operations
- Batch processing with shared state

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

The provider layer implements a **pluggable backend abstraction** that enables swapping between different implementations for the same functionality. This design allows:

- **Multiple backends**: Different providers for the same category (e.g., local vs API-based transcription)
- **Configuration-driven selection**: Switch providers via config without code changes
- **Graceful fallback**: Automatic fallback between providers on failure
- **Easy extensibility**: Add new providers by implementing a base class

#### Provider Registry Pattern

The `ProviderRegistry` class serves as the central coordinator for all provider types. It maintains a mapping of category → name → provider class, enabling dynamic provider discovery and instantiation.

```
┌─────────────────────────────────────────────────────────────┐
│                     ProviderRegistry                         │
├─────────────────────────────────────────────────────────────┤
│  register(category, name, provider_class)                   │
│  create(category, name, **kwargs) -> Provider               │
│  list_providers(category) -> list[str]                      │
│  get_provider_info(category, name) -> dict                  │
└─────────────────────────────────────────────────────────────┘
                              │
        ┌─────────────────────┼─────────────────────┐
        ▼                     ▼                     ▼
┌───────────────┐     ┌───────────────┐     ┌───────────────┐
│ transcription │     │   document    │     │   webpage     │
├───────────────┤     ├───────────────┤     ├───────────────┤
│ whisper-local │     │   docling     │     │   crawl4ai    │
│ (future: API) │     │ (future: ...)│     │ (future: ...) │
└───────────────┘     └───────────────┘     └───────────────┘
```

**Key Registry Methods:**

| Method | Description |
|--------|-------------|
| `register(category, name, cls)` | Register a provider class under category/name |
| `create(category, name, **kwargs)` | Instantiate a provider with configuration |
| `list_providers(category)` | List all registered providers for a category |
| `get_provider_info(category, name)` | Get metadata about a specific provider |

#### Base Classes

Each provider category defines an abstract base class that all implementations must follow:

| Category | Base Class | Result Type |
|----------|------------|-------------|
| `transcription` | `TranscriptionProvider` | `TranscriptionResult` |
| `document` | `DocumentProvider` | `DocumentResult` |
| `webpage` | `WebPageProvider` | `WebPageResult` |

**Base Class Interface Example:**

```python
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
        """Check if audio format is supported."""
```

#### Provider Lookup Flow

When a CLI command or MCP tool requests a specific provider, this flow executes:

```
CLI --provider flag / MCP tool parameter
        ↓
ProviderRegistry.create(category, name, **config)
        ↓
Registry looks up provider class by category + name
        ↓
Provider class instantiated with merged config
        ↓
Provider instance returned
        ↓
Converter uses provider.convert() / provider.transcribe()
```

**Example Flow:**

```bash
# CLI invocation
gobbler audio transcribe recording.mp3 --provider whisper-local --model small
```

```python
# Internal execution
provider = ProviderRegistry.create(
    category="transcription",
    name="whisper-local",
    model="small"  # passed as kwargs
)
result = await provider.transcribe(Path("recording.mp3"))
```

#### Registration Methods

Providers can register themselves in two ways:

**1. Self-Registration at Import (Recommended)**

Providers register themselves when their module is imported:

```python
# In gobbler_core/providers/transcription/whisper.py
from gobbler_core.providers.registry import ProviderRegistry
from gobbler_core.providers.transcription.base import TranscriptionProvider

class WhisperLocalProvider(TranscriptionProvider):
    @property
    def name(self) -> str:
        return "whisper-local"

    async def transcribe(self, audio_path, language="auto", **options):
        # Implementation using faster-whisper
        ...

# Self-registration at module load
ProviderRegistry.register("transcription", "whisper-local", WhisperLocalProvider)
```

**2. Decorator-Based Registration**

For cleaner syntax, use the `@register_provider` decorator:

```python
from gobbler_core.providers.registry import register_provider

@register_provider("transcription", "whisper-local")
class WhisperLocalProvider(TranscriptionProvider):
    ...
```

Both methods enable automatic discovery when the provider module is imported.

#### Configuration Integration

The `config.yaml` providers section maps directly to registry lookups:

```yaml
# config.yaml
providers:
  transcription:
    default: whisper-local
    whisper-local:
      model: small
      device: auto
      compute_type: float16

  document:
    default: docling
    docling:
      url: http://localhost:5001
      timeout: 120

  webpage:
    default: crawl4ai
    crawl4ai:
      url: http://localhost:11235
      timeout: 60
```

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

### Why Dual Interface (Skills + MCP)?

**Problem:** MCP tool definitions consume ~4,500 tokens of context, even when not all tools are needed.

**Solution:** Skills provide progressive disclosure - only ~100 tokens until used.

**Benefits:**
- Reduced context overhead for simple tasks
- Full Python flexibility for complex workflows
- Standalone operation without MCP server
- Same backend logic, no duplication

### Why SQLite for the Queue?

**Problem:** External queue systems like Redis add operational complexity and dependency management.

**Solution:** Use SQLite for zero-configuration, embedded queue storage that works everywhere Python runs.

### Why Auto-Queue Threshold of 1:45?

**Problem:** Users don't know when tasks will take long enough to warrant background processing.

**Solution:** Auto-queue tasks estimated >1:45 based on empirical testing:
- YouTube transcripts: <1s (never queue)
- Audio transcription: Varies by file size (queue if >35s audio)
- Video downloads: Almost always queue
- Document conversion: Usually <1:45 (queue rarely)

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

## Future Enhancements

### Planned Improvements

1. **Skills → MCP HTTP Integration**
   - Skills call MCP server via HTTP relay
   - Share job queue and session state
   - Unified progress tracking

2. **Provider Abstraction Library**
   - Shared provider interface package
   - Import from both Skills and MCP
   - Unified testing and documentation

3. **Enhanced Session Management**
   - Cross-tool session sharing
   - Persistent browser sessions
   - Session export/import

4. **Advanced Queue Features**
   - Job prioritization
   - Scheduled execution
   - Batch operation dependencies

### Architecture Evolution

The dual-interface approach allows gradual evolution:

```
Current: Skills ──import──> Providers <──import── MCP Tools
                                │
Future:  Skills ──HTTP──> MCP Server ──> Providers
                    │           │
                    └─── Relay ─┘
```

This maintains backward compatibility while enabling tighter integration.

## Conclusion

Gobbler's architecture balances context efficiency, flexibility, and power through its dual-interface approach. Skills provide lightweight, interactive workflows while MCP tools offer comprehensive automation with background processing. Both share the same robust backend, ensuring consistency and reducing maintenance burden.

The key insight is **progressive disclosure**: start with minimal context (Skills), scale to full toolset (MCP) as needed, all while using the same underlying services.
