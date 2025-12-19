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

Providers encapsulate backend service communication:

**YouTube Provider:**
- Multiple transcript APIs (youtube-transcript-api, TranscriptAPI.com)
- Auto-fallback strategy between providers
- Video metadata extraction
- Download capabilities via yt-dlp

**Webpage Provider:**
- HTTP client for Crawl4AI service
- Session management for authenticated crawling
- CSS/XPath selector support
- Link extraction and categorization

**Document Provider:**
- HTTP client for Docling service
- OCR toggle support
- Multi-format handling (PDF, DOCX, PPTX, XLSX)

**Audio Provider:**
- faster-whisper integration
- Metal/CoreML acceleration on M-series Macs
- Language auto-detection
- Model size selection (tiny to large)

**Browser Provider:**
- WebSocket relay to browser extension
- Tab group security model
- JavaScript execution interface
- Content extraction

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

**Redis (Port 6380):**
- RQ job queue backend
- Job state management
- Progress tracking

### Queue System

Background processing for long-running operations:

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
- SimpleWorker (no forking) for macOS CoreML compatibility
- Polls Redis for jobs
- Executes via same provider layer as MCP server
- Updates progress in Redis

## Design Decisions

### Why Dual Interface (Skills + MCP)?

**Problem:** MCP tool definitions consume ~4,500 tokens of context, even when not all tools are needed.

**Solution:** Skills provide progressive disclosure - only ~100 tokens until used.

**Benefits:**
- Reduced context overhead for simple tasks
- Full Python flexibility for complex workflows
- Standalone operation without MCP server
- Same backend logic, no duplication

### Why Port 6380 for Redis?

**Problem:** Port 6379 (default Redis) often conflicts with user's existing Redis instances.

**Solution:** Use 6380 to avoid conflicts while maintaining standard Redis protocol.

### Why SimpleWorker Instead of Fork?

**Problem:** RQ's default fork() worker crashes on macOS with CoreML/Metal acceleration.

**Solution:** Use SimpleWorker which doesn't fork, making it compatible with macOS frameworks.

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

Demonstrated by YouTube provider:

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
    def check_redis() -> HealthStatus
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
