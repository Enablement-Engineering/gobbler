<p align="center">
  <img src="docs/assets/Gobby Feasting (small).png" alt="Gobby the Turkey mascot consuming PDF, HTML, DOCX, and VIDEO files, outputting clean MD blocks" width="500">
</p>

# Gobbler

> **Universal Content Conversion to Markdown for AI**

Gobbler transforms any content—YouTube videos, web pages, documents, audio files, even live browser sessions—into clean, structured markdown that AI systems can immediately reason about.

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)

## The Problem

AI assistants work best with markdown. But content exists in countless formats—PDFs, videos, web pages behind logins, audio recordings. Getting that content into a format AI can use requires:

- Different tools for each content type
- Custom scripts to extract and format
- Lost metadata and inconsistent output
- No unified way for AI agents to access content

**Gobbler solves this.** One tool, one output format, multiple access patterns.

## The Solution

```bash
# Every content type → Same pattern → Same output format
gobbler youtube "https://youtube.com/watch?v=..." -o transcript.md
gobbler document report.pdf -o report.md
gobbler audio meeting.mp3 -o meeting.md
gobbler webpage "https://docs.example.com" -o docs.md
```

Every conversion produces **markdown with YAML frontmatter**:

```markdown
---
source: https://youtube.com/watch?v=VIDEO_ID
type: youtube_transcript
title: "Video Title"
duration: 847
word_count: 2341
converted_at: 2025-01-03T10:30:00Z
---

# Video Title

Content here, ready for AI consumption...
```

## Quick Start

```bash
# Install
git clone https://github.com/Enablement-Engineering/gobbler.git
cd gobbler && make install

# Start services (for web/document conversion)
make start-docker

# Convert content
gobbler youtube "https://youtube.com/watch?v=dQw4w9WgXcQ"
gobbler document paper.pdf --no-ocr -o paper.md
gobbler audio interview.mp3 --model small -o interview.md
```

📖 **[Full Documentation](https://Enablement-Engineering.github.io/gobbler/)**

## Three Ways to Use Gobbler

### 1. CLI (For Humans & Scripts)

```bash
gobbler youtube URL              # YouTube transcripts
gobbler audio FILE               # Audio/video transcription
gobbler document FILE            # PDF, DOCX, PPTX, XLSX
gobbler webpage URL              # Web pages (JS-rendered)
gobbler batch youtube-playlist URL  # Batch processing
```

### 2. Skills (For AI Agents)

Skills are markdown instruction files (`SKILL.md`) that teach Claude how to use the `gobbler` CLI. Each skill contains YAML frontmatter for discovery and CLI commands for completing tasks:

```
skills/
├── gobbler-youtube/     # YouTube transcription
├── gobbler-audio/       # Audio/video transcription
├── gobbler-document/    # Document conversion
├── gobbler-webpage/     # Web scraping
├── gobbler-browser/     # Browser automation + AI chat integrations
├── gobbler-setup/       # Installation and troubleshooting
└── gobbler-utils/       # Utility commands
```

The `gobbler-browser` skill includes integrations for NotebookLM, Claude.ai, ChatGPT, and Gemini (DOM automation - may break with site updates).

Skills use **progressive disclosure**—Claude only loads skill metadata at startup, then reads full CLI instructions when triggered.

### 3. MCP Protocol (For AI Coding Assistants)

```bash
# For Claude Code
claude mcp add gobbler-mcp -- uv --directory /path/to/gobbler run gobbler-mcp
```

```jsonc
// For OpenCode (opencode.json)
{
  "mcp": {
    "gobbler": {
      "type": "local",
      "command": ["uv", "--directory", "/path/to/gobbler", "run", "gobbler-mcp"]
    }
  }
}
```

```jsonc
// For Claude Desktop (~/.config/claude/claude_desktop_config.json)
{
  "mcpServers": {
    "gobbler-mcp": {
      "command": "uv",
      "args": ["--directory", "/path/to/gobbler", "run", "gobbler-mcp"]
    }
  }
}
```

## Features

### Content Conversion

| Type | Command | Backend |
|------|---------|---------|
| YouTube | `gobbler youtube URL` | youtube-transcript-api |
| Audio/Video | `gobbler audio FILE` | faster-whisper (local) |
| Documents | `gobbler document FILE` | Docling (Docker) |
| Web Pages | `gobbler webpage URL` | Crawl4AI (Docker) |

### Browser Automation

Control browsers via the Gobbler extension for authenticated content:

```bash
gobbler browser extract          # Extract current page
gobbler notebooklm query "..."   # Query NotebookLM
gobbler chatgpt query "..."      # Send to ChatGPT
gobbler claude query "..."       # Send to Claude.ai
gobbler gemini query "..."       # Send to Gemini
```

**Setup:**

1. Load the extension in Chrome:
   - Go to `chrome://extensions/`
   - Enable "Developer mode"
   - Click "Load unpacked" → select `browser-extension/` folder

2. Create a tab group named **"Gobbler"** (right-click any tab → Add to group → New group)

3. Add tabs you want to control to the Gobbler group

Only tabs in the "Gobbler" group are accessible—this prevents accidental access to sensitive tabs.

### Batch Processing

```bash
gobbler batch youtube-playlist "https://youtube.com/playlist?list=..."
gobbler batch directory ./documents --pattern "*.pdf"
gobbler batch webpages urls.txt --output-dir ./pages
```

## Architecture

Gobbler provides three interfaces that all use the same CLI and backends:

```
┌─────────────────────────────────────────────────────────────┐
│                     Your Automations                        │
└──────────────┬──────────────┬──────────────┬───────────────┘
               │              │              │
      ┌────────▼────┐  ┌──────▼─────┐  ┌─────▼─────┐
      │   Skills    │  │  gobbler   │  │    MCP    │
      │(CLI instrs) │  │    CLI     │  │  Server   │
      └────────┬────┘  └──────┬─────┘  └─────┬─────┘
               │              │              │
               └──────────────┼──────────────┘
                              ▼
                    ┌─────────────────┐
                    │  Provider Layer │
                    │  (Converters)   │
                    └────────┬────────┘
                             │
         ┌───────────────────┼───────────────────┐
         ▼                   ▼                   ▼
    ┌─────────┐        ┌───────────┐       ┌─────────┐
    │ Whisper │        │  Docling  │       │Crawl4AI │
    │ (local) │        │ (Docker)  │       │(Docker) │
    └─────────┘        └───────────┘       └─────────┘
```

**Skills** are markdown files that teach Claude which CLI commands to run. **MCP** exposes the same functionality as tools for Claude Desktop/Code.

## Installation

### Prerequisites

- Python 3.11+
- [uv](https://docs.astral.sh/uv/) (Python package manager)
- Docker Desktop (for web/document conversion)
- ffmpeg (for audio extraction from video)

### Install

```bash
# Install uv (if not already installed)
curl -LsSf https://astral.sh/uv/install.sh | sh

# Clone and install
git clone https://github.com/Enablement-Engineering/gobbler.git
cd gobbler
make install

# Start Docker services
make start-docker

# Verify
gobbler --version
```

### What Works Without Docker

- **YouTube transcripts** - Uses YouTube's API directly
- **Audio transcription** - Uses local Whisper model

### What Needs Docker

- **Document conversion** - Docling service (port 5001)
- **Web scraping** - Crawl4AI service (port 11235)

## Configuration

Config file: `~/.config/gobbler/config.yaml`

```yaml
services:
  docling: "http://localhost:5001"
  crawl4ai: "http://localhost:11235"

storage:
  type: "sqlite"
  path: "~/.config/gobbler/jobs.db"

logging:
  level: "INFO"
```

## Troubleshooting

### Document conversion crashes

```bash
# Use --no-ocr for digital PDFs (faster, less memory)
gobbler document file.pdf --no-ocr -o output.md
```

### Service not responding

```bash
docker compose up -d
docker compose ps
curl http://localhost:5001/health   # Docling
curl http://localhost:11235/health  # Crawl4AI
```

### YouTube "IP blocked"

```bash
# Set up TranscriptAPI.com for reliable access
export TRANSCRIPTAPI_KEY=your_key
gobbler youtube "URL"
```

See [gobbler-setup skill](skills/gobbler-setup/SKILL.md) for complete troubleshooting.

## Project Structure

```
gobbler/
├── src/
│   ├── gobbler_cli/       # CLI interface (typer)
│   ├── gobbler_core/      # Converters & utilities
│   ├── gobbler_mcp/       # MCP protocol server
│   ├── gobbler_relay/     # Browser extension bridge
│   └── gobbler_queue/     # Background job queue
├── skills/                # AI agent instruction files
├── browser-extension/     # Chrome/Firefox extension
└── docker-compose.yml     # External services
```

## Documentation

📖 **[Full Documentation](https://Enablement-Engineering.github.io/gobbler/)** - Installation, configuration, and usage guides

Key pages:
- [Quick Start](https://Enablement-Engineering.github.io/gobbler/QUICK_START/) - Get running in 5 minutes
- [CLI Reference](https://Enablement-Engineering.github.io/gobbler/cli/) - All commands and options
- [Skills Guide](https://Enablement-Engineering.github.io/gobbler/SKILLS/) - Using skills with AI agents
- [Browser Extension](https://Enablement-Engineering.github.io/gobbler/browser-extension/) - Setup and usage
- [Configuration](https://Enablement-Engineering.github.io/gobbler/configuration/) - Customize Gobbler

## License

MIT License - see [LICENSE](LICENSE) file.

## Acknowledgments

Built on the shoulders of giants:
- [Crawl4AI](https://github.com/unclecode/crawl4ai) - Web scraping
- [Docling](https://github.com/DS4SD/docling) - Document conversion
- [faster-whisper](https://github.com/SYSTRAN/faster-whisper) - Audio transcription
- [youtube-transcript-api](https://github.com/jdepoix/youtube-transcript-api) - YouTube transcripts
