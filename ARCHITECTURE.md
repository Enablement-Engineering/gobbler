# Gobbler MCP Server - System Architecture

## Overview

Gobbler is an MCP (Model Context Protocol) server that converts various content types into clean markdown format. It follows **Option C: Hybrid Architecture** - lightweight built-in tools for simple conversions, containerized services for heavy processing.

## Architecture Diagram

```
Host Machine
├── Gobbler MCP Server (Python + uv)
│   ├── Native filesystem access (no volume mount issues)
│   ├── Built-in: YouTube transcripts (youtube-transcript-api)
│   ├── Built-in: Audio transcription (faster-whisper with CoreML/Metal)
│   ├── Calls HTTP APIs of Docker services for web/docs
│   └── Saves files with frontmatter metadata
│
└── Docker Compose Services
    ├── Crawl4AI Container (port 11235) - Advanced web scraping
    ├── Docling Container (port 5001) - Document conversion
    └── Redis Container (port 6380) - Queue backend for long tasks
```

## Key Architectural Decisions

### 1. MCP Server Deployment: Host-based

**Decision**: Run MCP server on host, not in container

**Rationale**:
- MCP clients connect via **stdio** (standard input/output)
- Direct filesystem access for saving to arbitrary project paths
- No volume mounting complexity
- User runs: `uv run gobbler-mcp` and it just works

**File Saving Strategy**:
- Tools accept optional `output_file` parameter
- Absolute paths: `/Users/dylan/Projects/myapp/research/video.md`
- Direct filesystem writes (no container volume mounts)
- Metadata saved in YAML frontmatter

### 2. Service Deployment: Docker Compose

**Decision**: Use pre-built Docker images for heavy services

**Rationale**:
- Isolation of potentially unsafe code execution
- Consistent runtime environments
- Easy dependency management
- User controls which services to run

**Service Images**:
- **Crawl4AI**: `unclecode/crawl4ai:basic` (official)
- **Docling**: `quay.io/docling-project/docling-serve` (official)
- **Redis**: `redis:7-alpine` (official)

### 3. Graceful Degradation

**Decision**: Fail fast per-tool, not globally

**Behavior**:
- YouTube transcripts ALWAYS work (no containers needed)
- Audio transcription ALWAYS works (no containers needed, uses faster-whisper locally)
- Web/doc conversions fail with clear error if service unavailable
- Error messages explain how to start services
- No silent failures or half-working tools

### 4. Configuration Management

**Model Caching**: Host directory mounts for containers, local cache for faster-whisper
```yaml
# Docker service volumes
volumes:
  - ~/.gobbler/models/docling:/app/models

# Local model cache (faster-whisper automatically uses ~/.cache/huggingface)
```

**User Config**: `~/.config/gobbler/config.yml`
```yaml
whisper:
  model: small  # tiny, base, small, medium, large
  language: auto
docling:
  ocr: true
  vlm: false
crawl4ai:
  timeout: 30
```

### 5. Output Format

**Decision**: Markdown with YAML frontmatter metadata

**Example**:
```markdown
---
source: https://youtube.com/watch?v=dQw4w9WgXcQ
type: youtube_transcript
duration: 213
language: en
word_count: 1547
converted_at: 2025-10-02T14:32:11Z
---

# Video Transcript

[transcript content...]
```

**Rationale**:
- Combined metadata + content in single file
- Human-readable, git-friendly
- Parseable by other tools
- No separate `.meta.json` files to manage

## Tool Design

### Tool Structure

Following MCP best practices from deep-research.md:
- **Separate tools per conversion type** (not unified)
- **Clear naming**: `verb_source_target` pattern
- **Rich parameters** over many narrow tools
- **Comprehensive descriptions** for LLM tool selection

### Tools

1. **`transcribe_youtube`**
   - Built-in (no container required)
   - Uses `youtube-transcript-api`
   - Fastest, most reliable conversion

2. **`fetch_webpage`**
   - Requires Crawl4AI container
   - Advanced scraping with JavaScript rendering
   - Graceful degradation if container unavailable

3. **`convert_document`**
   - Requires Docling container
   - Supports PDF, DOCX, PPTX, XLSX
   - OCR support for scanned documents

4. **`transcribe_audio`**
   - Built-in (no container required)
   - Uses `faster-whisper` with CoreML/Metal acceleration
   - Supports audio and video files
   - Automatic audio extraction from video with ffmpeg

### Error Handling

Following MCP philosophy: **errors are data, not exceptions**

```python
return {
    "isError": true,
    "content": [{
        "type": "text",
        "text": "Crawl4AI service unavailable. Start with: docker-compose up -d crawl4ai"
    }]
}
```

**Actionable error messages**:
- Explain what went wrong
- Suggest concrete fixes
- Mention alternative tools when applicable

## Security Model

### Container Isolation

- Services run in isolated containers
- MCP server talks to services via HTTP (localhost only)
- No direct code execution of untrusted content in host

### File Access

- MCP server reads/writes files with host user permissions
- No privileged container access needed
- Services receive file content via HTTP POST (not file paths)

### Resource Limits

```yaml
deploy:
  resources:
    limits:
      memory: 4g
      cpus: '2'
```

## Dependency Management

**Package Manager**: uv (not pip)

**Rationale**:
- Faster installation (10-100x)
- Better dependency resolution
- Automatic virtual environment management
- Modern Python tooling

**Installation**:
```bash
uv tool install gobbler-mcp
```

## Technology Stack

### MCP Server (Host)
- **Language**: Python 3.10+
- **Framework**: FastMCP (official MCP Python SDK)
- **Package Manager**: uv
- **Built-in Libraries**:
  - youtube-transcript-api (YouTube transcripts)
  - faster-whisper (audio transcription with CoreML/Metal)
  - yt-dlp (YouTube downloads)

### Services (Docker)
- **Crawl4AI**: Web scraping with browser automation
- **Docling**: Document understanding (PyTorch-based ML)
- **Redis**: Queue backend for long-running tasks

## Performance Considerations

### Async I/O
- All I/O operations use `async/await`
- Concurrent conversions supported
- Non-blocking HTTP calls to services

### Resource Management
- Services initialized once at startup
- Shared HTTP clients (connection pooling)
- Proper cleanup on shutdown (lifespan management)

### Progress Reporting
For long-running conversions:
```python
await ctx.report_progress(
    progress=bytes_processed / total_bytes,
    total=1.0,
    message=f"Processing page {page} of {total_pages}"
)
```

## Service Communication Protocol

### MCP Server → Services

**HTTP POST** with file content or URL:

```python
# Web scraping
POST http://localhost:11235/crawl
{
    "url": "https://example.com",
    "timeout": 30
}

# Document conversion
POST http://localhost:5001/convert
Content-Type: multipart/form-data
file: [binary content]

# Audio transcription (local, no HTTP call)
# Uses faster-whisper Python library directly
whisper.transcribe(file_path, model="small", language="auto")
```

### Services → MCP Server

**JSON responses** with markdown + metadata:

```json
{
    "markdown": "# Converted content...",
    "metadata": {
        "source": "https://example.com",
        "word_count": 1547,
        "conversion_time_ms": 2341
    }
}
```

## Deployment Workflow

### Developer
1. Build Docker images (or use pre-built)
2. Push to registry
3. Tag releases

### End User
1. Install MCP server: `uv tool install gobbler-mcp`
2. Start services: `docker-compose up -d`
3. Configure MCP client (Claude Desktop, etc.)
4. Services auto-restart on system reboot

## Future Considerations

### Extensibility
- Plugin system for additional converters
- Custom markdown post-processors
- Alternative service backends

### Observability
- Structured logging (JSON format)
- Metrics collection (conversion times, success rates)
- Health check endpoints

### Distribution
- Submit to Docker MCP Catalog
- Publish to PyPI as `gobbler-mcp`
- Pre-built binaries via uv
