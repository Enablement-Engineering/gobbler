# Gobbler MCP Server

> 🦃 Convert any content to clean markdown with YAML frontmatter

Gobbler is a [Model Context Protocol (MCP)](https://modelcontextprotocol.io) server that converts various content types—YouTube videos, web pages, documents, and audio/video files—into clean, structured markdown with rich metadata.

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

## Features

- **YouTube Transcripts** - Extract official transcripts with video metadata
- **YouTube Downloads** - Download videos with quality selection
- **Web Scraping** - Convert any webpage to markdown (JavaScript-rendered content supported)
- **Document Conversion** - PDF, DOCX, PPTX, XLSX to markdown with OCR support
- **Audio/Video Transcription** - Fast transcription using Whisper with Metal/CoreML acceleration
- **Background Queue System** - Handle long-running tasks with Redis + RQ
- **Clean Output** - YAML frontmatter + structured markdown
- **MCP Compatible** - Works with Claude Code, Claude Desktop, and any MCP client

## Quick Start

```bash
# 1. Install dependencies
curl -LsSf https://astral.sh/uv/install.sh | sh  # Install uv if needed
git clone https://github.com/Enablement-Engineering/gobbler.git
cd gobbler
make install

# 2. Start all services (Docker + worker)
make start

# 3. Install to Claude Code
make claude-install  # Shows command to run

# 4. Use in Claude Code
# "Transcribe this YouTube video: https://youtube.com/watch?v=..."
```

## Architecture

Gobbler uses a **hybrid architecture** optimized for performance:

### Host-Based Components
- **MCP Server** (Python + uv) - Direct filesystem access, coordinates services
- **YouTube Tools** - No Docker required, uses official API
- **faster-whisper** - Local transcription with Metal/CoreML acceleration on M-series Macs
- **RQ Worker** - Background task processing

### Docker Services (Optional)
- **Crawl4AI** (port 11235) - Advanced web scraping with JavaScript rendering
- **Docling** (port 5001) - Document conversion with OCR
- **Redis** (port 6380) - Queue backend for long-running tasks

## Installation

### Prerequisites

- Python 3.11+
- [uv](https://docs.astral.sh/uv/) package manager
- Docker and Docker Compose (for web/document conversion)
- ffmpeg (for audio extraction from video)

### Setup

```bash
# Clone repository
git clone https://github.com/Enablement-Engineering/gobbler.git
cd gobbler

# Install Python dependencies
make install
# or: uv sync

# Start Docker services (optional, for web/doc conversion)
make start
```

### Claude Code Integration

```bash
# Show installation command
make claude-install

# Copy and run the displayed command:
claude mcp add gobbler-mcp -- uv --directory /path/to/gobbler run gobbler-mcp
```

### Claude Desktop Integration

Edit `~/Library/Application Support/Claude/claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "gobbler-mcp": {
      "command": "uv",
      "args": [
        "--directory",
        "/FULL/PATH/TO/gobbler",
        "run",
        "gobbler-mcp"
      ]
    }
  }
}
```

Restart Claude Desktop after editing.

## Available Tools

### `transcribe_youtube`

Extract YouTube video transcript with metadata.

**Parameters:**
- `video_url` (required) - YouTube URL
- `include_timestamps` (optional) - Include timestamp markers (default: false)
- `language` (optional) - Language code or 'auto' (default: 'auto')
- `output_file` (optional) - Path to save markdown file (auto-generates filename from title)

**Example:**
```
"Transcribe https://youtube.com/watch?v=dQw4w9WgXcQ to /Users/me/transcripts/"
```

### `download_youtube_video`

Download YouTube video with quality selection.

**Parameters:**
- `video_url` (required) - YouTube URL
- `output_dir` (required) - Directory to save video
- `quality` (optional) - 'best', '1080p', '720p', '480p', '360p' (default: 'best')
- `format` (optional) - 'mp4', 'webm', 'mkv' (default: 'mp4')
- `auto_queue` (optional) - Auto-queue if estimated > 1:45 (default: false)

**Example:**
```
"Download this YouTube video in 720p to /Users/me/Videos/"
```

### `fetch_webpage`

Convert webpage to markdown using Crawl4AI.

**Parameters:**
- `url` (required) - Full HTTP/HTTPS URL
- `include_images` (optional) - Include image references (default: true)
- `timeout` (optional) - Request timeout in seconds (default: 30, max: 120)
- `output_file` (optional) - Path to save markdown file

**Example:**
```
"Convert https://example.com/article to markdown"
```

**Requires:** Crawl4AI Docker container (`make start-docker`)

### `convert_document`

Convert documents (PDF, DOCX, PPTX, XLSX) to markdown.

**Parameters:**
- `file_path` (required) - Absolute path to document
- `enable_ocr` (optional) - Enable OCR for scanned documents (default: true)
- `output_file` (optional) - Path to save markdown file

**Example:**
```
"Convert /Users/me/Documents/report.pdf to markdown with OCR"
```

**Requires:** Docling Docker container (`make start-docker`)

### `transcribe_audio`

Transcribe audio/video files using Whisper with Metal acceleration.

**Parameters:**
- `file_path` (required) - Absolute path to audio/video file
- `model` (optional) - 'tiny', 'base', 'small', 'medium', 'large' (default: 'small')
- `language` (optional) - Language code or 'auto' (default: 'auto')
- `output_file` (optional) - Path to save markdown file
- `auto_queue` (optional) - Auto-queue if estimated > 1:45 (default: false)

**Example:**
```
"Transcribe /Users/me/Videos/meeting.mp4 with auto-queue enabled"
```

**Performance:** ~6 seconds per MB with Metal/CoreML on M-series Macs

### `get_job_status`

Check status of queued background jobs.

**Parameters:**
- `job_id` (required) - Job ID returned when task was queued

**Example:**
```
"Check status of job abc123"
```

### `list_jobs`

List jobs in a queue.

**Parameters:**
- `queue_name` (optional) - 'default', 'transcription', 'download' (default: 'default')
- `limit` (optional) - Max results (default: 20, max: 100)

**Example:**
```
"List jobs in the transcription queue"
```

## Background Queue System

Long-running tasks can be queued for background processing:

```bash
# Start worker (included in 'make start')
make worker

# Or manually
uv run python -m gobbler_mcp.worker

# Stop worker
make worker-stop
```

**Auto-queue Feature:**
- Set `auto_queue: true` on supported tools
- Tasks estimated > 1:45 automatically queue
- Returns job_id and ETA
- Check progress with `get_job_status(job_id)`

**Queues:**
- `default` - General tasks
- `transcription` - Audio/video transcription
- `download` - YouTube downloads

## Configuration

User config location: `~/.config/gobbler/config.yml`

```yaml
# Whisper settings
whisper:
  model: small  # tiny, base, small, medium, large
  language: auto

# Docling settings
docling:
  ocr: true
  vlm: false

# Crawl4AI settings
crawl4ai:
  timeout: 30
  max_timeout: 120
  api_token: gobbler-local-token

# Redis queue settings
redis:
  host: localhost
  port: 6380
  db: 0

queue:
  auto_queue_threshold: 105  # seconds (1:45)
  default_queue: default

# Service endpoints
services:
  crawl4ai:
    host: localhost
    port: 11235
  docling:
    host: localhost
    port: 5001
```

## Makefile Commands

```bash
make help          # Show all available commands

# Quick start
make start         # Start everything (Docker + worker)
make start-docker  # Start only Docker services
make stop          # Stop all services

# Workers
make worker        # Start RQ worker (foreground)
make worker-stop   # Stop background workers

# Status and logs
make status        # Check service health
make logs          # View Docker logs

# Installation
make install       # Install dependencies
make claude-install # Show Claude Code installation command

# Testing
make inspector     # Launch MCP inspector
make test          # Run tests (when implemented)

# Cleanup
make clean         # Remove build artifacts
```

## Example Output

All tools return markdown with YAML frontmatter:

```markdown
---
source: https://youtube.com/watch?v=dQw4w9WgXcQ
type: youtube_transcript
title: "Rick Astley - Never Gonna Give You Up"
channel: "Rick Astley"
duration: 213
language: en
video_id: dQw4w9WgXcQ
word_count: 1547
converted_at: 2025-10-03T15:32:11Z
---

# Rick Astley - Never Gonna Give You Up

Never gonna give you up, never gonna let you down...
```

## Performance

- **YouTube transcripts:** < 1 second (no Docker required)
- **Web scraping:** 2-10 seconds depending on page complexity
- **Document conversion:** 5-30 seconds depending on size and OCR
- **Audio transcription:** ~6 seconds per MB with Metal/CoreML
- **Video transcription:** Auto-extracts audio first, then transcribes

## Troubleshooting

### Port 6379 already in use

Gobbler uses port 6380 for Redis to avoid conflicts. If you still have issues:

```bash
# Check what's using the port
lsof -i :6380

# Change port in config
vim ~/.config/gobbler/config.yml
# Update redis.port to different value
```

### Worker crashes with fork() errors on macOS

This is fixed in the latest version. Gobbler uses `SimpleWorker` which doesn't fork, making it compatible with CoreML/Metal on macOS.

### Services not starting

```bash
# Check logs
make logs

# Restart services
make stop && make start

# Check status
make status
```

### YouTube transcript not available

Some videos don't have transcripts. Try downloading and transcribing instead:

```
"Download this video and transcribe it with auto-queue"
```

## Development

```bash
# Install dev dependencies
uv sync --dev

# Run tests
uv run pytest

# Type checking
uv run mypy src/

# Linting
uv run ruff check src/

# Format code
uv run ruff format src/

# Test with MCP Inspector
make inspector
```

## Project Structure

```
gobbler/
├── src/gobbler_mcp/
│   ├── server.py          # MCP tools and server
│   ├── worker.py          # RQ background worker
│   ├── config.py          # Configuration management
│   ├── converters/        # Conversion implementations
│   │   ├── youtube.py     # YouTube transcript/download
│   │   ├── audio.py       # Whisper transcription
│   │   ├── webpage.py     # Crawl4AI web scraping
│   │   └── document.py    # Docling document conversion
│   └── utils/             # Shared utilities
│       ├── queue.py       # Redis/RQ queue management
│       ├── frontmatter.py # YAML frontmatter generation
│       ├── health.py      # Service health checks
│       └── http_client.py # HTTP client with retries
├── docker-compose.yml     # Service orchestration
├── Makefile              # Convenience commands
└── pyproject.toml        # Python dependencies
```

## Contributing

Contributions welcome! Please:

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests if applicable
5. Submit a pull request

See [ARCHITECTURE.md](ARCHITECTURE.md) for design decisions.

## License

MIT License - see [LICENSE](LICENSE) file for details.

## Acknowledgments

- [Model Context Protocol](https://modelcontextprotocol.io) by Anthropic
- [FastMCP](https://github.com/jlowin/fastmcp) framework
- [Crawl4AI](https://github.com/unclecode/crawl4ai) for web scraping
- [Docling](https://github.com/DS4SD/docling) for document conversion
- [faster-whisper](https://github.com/SYSTRAN/faster-whisper) for transcription
- [yt-dlp](https://github.com/yt-dlp/yt-dlp) for YouTube downloads

## Support

- **Issues:** https://github.com/Enablement-Engineering/gobbler/issues
- **Discussions:** https://github.com/Enablement-Engineering/gobbler/discussions
- **MCP Docs:** https://modelcontextprotocol.io
