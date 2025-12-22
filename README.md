<p align="center">
  <img src="docs/assets/Gobby Feasting (small).png" alt="Gobby the Turkey mascot consuming PDF, HTML, DOCX, and VIDEO files, outputting clean MD blocks" width="500">
</p>

# Gobbler

> *Universal Content Conversion to Markdown*

Gobbler converts various content types—YouTube videos, web pages, documents, and audio/video files—into clean, structured markdown with rich metadata.

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)

## Features

- **YouTube Transcripts** - Extract official transcripts with video metadata
- **Web Scraping** - Convert any webpage to markdown (JavaScript-rendered content supported)
- **Document Conversion** - PDF, DOCX, PPTX, XLSX to markdown with OCR support
- **Audio/Video Transcription** - Fast transcription using Whisper
- **Browser Automation** - Control browser via extension for live page extraction
- **Clean Output** - YAML frontmatter + structured markdown

## Quick Start

```bash
# Install
git clone https://github.com/dylanisaac/gobbler.git
cd gobbler
uv sync

# Start services
docker compose up -d

# Convert content
gobbler youtube "https://youtube.com/watch?v=VIDEO_ID" -o transcript.md
gobbler document report.pdf --no-ocr -o report.md
gobbler audio recording.mp3 -o transcript.md
gobbler webpage "https://example.com" -o page.md
```

## Architecture

Gobbler provides **four ways to access the same conversion engine**:

```
┌─────────────────────────────────────────────────────────────┐
│                     Your Automations                        │
└──────────────┬──────────────┬──────────────┬───────────────┘
               │              │              │
      ┌────────▼────┐  ┌──────▼─────┐  ┌─────▼─────┐
      │  gobbler    │  │ gobbler_sdk │  │  MCP      │
      │    CLI      │  │   Python   │  │ Protocol  │
      └────────┬────┘  └──────┬─────┘  └─────┬─────┘
               │              │              │
               └──────────────┼──────────────┘
                              │
                    ┌─────────▼─────────┐
                    │   REST API        │
                    │   Port 4600       │
                    └─────────┬─────────┘
                              │
        ┌─────────────────────┼─────────────────────┐
        │                     │                     │
   ┌────▼────┐          ┌─────▼─────┐         ┌────▼────┐
   │ Whisper │          │  Docling  │         │ Crawl4AI│
   │ (Audio) │          │  (Docs)   │         │  (Web)  │
   └─────────┘          └───────────┘         └─────────┘
```

### Interface Options

| Interface | Best For | Example |
|-----------|----------|---------|
| **CLI** | Shell scripts, quick tasks | `gobbler youtube URL -o file.md` |
| **Python SDK** | Python applications | `client.convert.youtube(url)` |
| **REST API** | Any HTTP client | `curl http://localhost:4600/convert/youtube` |
| **MCP** | Claude Desktop/Code | Built-in tool discovery |

## CLI Usage

```bash
# YouTube
gobbler youtube "https://youtube.com/watch?v=VIDEO_ID"
gobbler youtube "https://youtube.com/watch?v=VIDEO_ID" -o transcript.md --timestamps

# Documents (use --no-ocr for digital PDFs, --ocr for scanned)
gobbler document report.pdf -o output.md
gobbler document report.pdf --no-ocr -o output.md
gobbler document scanned.pdf --ocr -o output.md

# Audio/Video
gobbler audio recording.mp3 -o transcript.md
gobbler audio lecture.mp4 --model medium -o lecture.md

# Web pages
gobbler webpage "https://example.com" -o page.md
```

## Python SDK

```python
from gobbler_sdk import GobblerClient

client = GobblerClient()

# YouTube
result = client.convert.youtube("https://youtube.com/watch?v=VIDEO_ID")
print(result.markdown)

# Document
result = client.convert.document("/path/to/report.pdf", enable_ocr=False)
print(result.markdown)

# Audio
result = client.convert.audio("/path/to/recording.mp3", model="small")
print(result.markdown)

# Webpage
result = client.convert.webpage("https://example.com")
print(result.markdown)
```

## REST API

```bash
# YouTube
curl -X POST http://localhost:4600/convert/youtube \
  -H "Content-Type: application/json" \
  -d '{"video_url": "https://youtube.com/watch?v=VIDEO_ID"}'

# Document
curl -X POST http://localhost:4600/convert/document \
  -H "Content-Type: application/json" \
  -d '{"file_path": "/path/to/report.pdf", "enable_ocr": false}'

# Audio
curl -X POST http://localhost:4600/convert/audio \
  -H "Content-Type: application/json" \
  -d '{"file_path": "/path/to/recording.mp3", "model": "small"}'

# Webpage
curl -X POST http://localhost:4600/convert/webpage \
  -H "Content-Type: application/json" \
  -d '{"url": "https://example.com"}'
```

## Installation

### Prerequisites

- Python 3.11+
- Docker Desktop
- uv (Python package manager)
- ffmpeg (for audio processing)

### Install

```bash
# Install uv if needed
curl -LsSf https://astral.sh/uv/install.sh | sh

# Clone and install
git clone https://github.com/dylanisaac/gobbler.git
cd gobbler
uv sync

# Start Docker services
docker compose up -d

# Verify
gobbler --version
curl http://localhost:5001/health  # Docling
curl http://localhost:11235/health # Crawl4AI
```

### Claude Code Integration

```bash
# Install as MCP server
claude mcp add gobbler-mcp -- uv --directory /path/to/gobbler run gobbler-mcp
```

### Claude Desktop Integration

Edit `~/Library/Application Support/Claude/claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "gobbler-mcp": {
      "command": "uv",
      "args": ["--directory", "/path/to/gobbler", "run", "gobbler-mcp"]
    }
  }
}
```

## Daemon Management

```bash
# Start daemon (background)
gobbler daemon start

# Start in foreground (for debugging)
gobbler daemon start --foreground

# Check status
gobbler daemon status

# View logs
gobbler daemon logs
gobbler daemon logs --follow

# Stop
gobbler daemon stop

# Restart
gobbler daemon restart
```

## Docker Services

| Service | Port | Purpose |
|---------|------|---------|
| `gobbler-docling` | 5001 | PDF, DOCX, PPTX, XLSX conversion |
| `gobbler-crawl4ai` | 11235 | Web page scraping |
| `gobbler-redis` | 6380 | Job queue backend |

```bash
# Start all
docker compose up -d

# Check status
docker compose ps

# View logs
docker logs gobbler-docling --tail 50
docker logs gobbler-crawl4ai --tail 50

# Restart a service
docker compose restart docling
```

## Configuration

Config file: `~/.config/gobbler/config.yaml`

```yaml
api:
  port: 4600
  host: "0.0.0.0"

services:
  docling: "http://localhost:5001"
  crawl4ai: "http://localhost:11235"

storage:
  type: "sqlite"
  path: "~/.config/gobbler/jobs.db"

logging:
  level: "INFO"
  file: "~/.config/gobbler/gobbler.log"
```

## Auto-Start on Login (macOS)

Create `~/Library/LaunchAgents/com.gobbler.plist`:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.gobbler</string>
    <key>ProgramArguments</key>
    <array>
        <string>/bin/bash</string>
        <string>-c</string>
        <string>cd /path/to/gobbler && docker compose up -d && sleep 10 && gobbler daemon start</string>
    </array>
    <key>RunAtLoad</key>
    <true/>
</dict>
</plist>
```

Load: `launchctl load ~/Library/LaunchAgents/com.gobbler.plist`

## Troubleshooting

### Document conversion crashes

```bash
# Use --no-ocr for digital PDFs (faster, less memory)
gobbler document file.pdf --no-ocr -o output.md
```

### Service not responding

```bash
docker compose up -d
curl http://localhost:5001/health  # Docling
curl http://localhost:11235/health # Crawl4AI
```

### CLI not found

```bash
# Run via uv
uv run gobbler --version

# Or install globally
uv tool install .
```

See [skills/gobbler-setup/SKILL.md](skills/gobbler-setup/SKILL.md) for complete troubleshooting guide.

## Example Output

```markdown
---
source: https://youtube.com/watch?v=VIDEO_ID
type: youtube_transcript
title: "Video Title"
channel: "Channel Name"
duration: 213
language: en
word_count: 1547
converted_at: 2025-12-21T15:32:11Z
---

# Video Title

Transcript content here...
```

## Project Structure

```
gobbler/
├── src/
│   ├── gobbler_cli/       # CLI interface
│   ├── gobbler_api/       # REST API server
│   ├── gobbler_sdk/       # Python client library
│   ├── gobbler_daemon/    # Background daemon
│   ├── gobbler_core/      # Shared converters
│   ├── gobbler_mcp/       # MCP server
│   └── gobbler_relay/     # Browser extension relay
├── skills/                # Claude Code skills
├── docker-compose.yml     # Docker services
└── pyproject.toml         # Python config
```

## License

MIT License - see [LICENSE](LICENSE) file.

## Acknowledgments

- [Crawl4AI](https://github.com/unclecode/crawl4ai) for web scraping
- [Docling](https://github.com/DS4SD/docling) for document conversion
- [faster-whisper](https://github.com/SYSTRAN/faster-whisper) for transcription
- [yt-dlp](https://github.com/yt-dlp/yt-dlp) for YouTube
