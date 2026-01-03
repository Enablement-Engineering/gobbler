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
git clone https://github.com/dylanisaac/gobbler.git
cd gobbler && uv sync

# Start services (for web/document conversion)
docker compose up -d

# Convert content
gobbler youtube "https://youtube.com/watch?v=dQw4w9WgXcQ"
gobbler document paper.pdf --no-ocr -o paper.md
gobbler audio interview.mp3 --model small -o interview.md
```

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

Skills are markdown instruction files that teach AI agents how to use Gobbler. They provide **progressive disclosure**—AI only loads what it needs:

```
skills/
├── gobbler-youtube/     # YouTube transcription
├── gobbler-audio/       # Audio/video transcription
├── gobbler-document/    # Document conversion
├── gobbler-webpage/     # Web scraping
├── gobbler-browser/     # Browser automation
├── gobbler-notebooklm/  # NotebookLM integration
├── gobbler-chatgpt/     # ChatGPT via browser
├── gobbler-claude/      # Claude.ai via browser
└── gobbler-gemini/      # Gemini via browser
```

Each skill contains a `SKILL.md` with:
- YAML frontmatter for AI discovery (~100 tokens)
- Quick workflow for common tasks (~200 tokens)
- Full documentation for edge cases (~500+ tokens)

### 3. MCP Protocol (For Claude Desktop/Code)

```bash
# Add to Claude Code
claude mcp add gobbler-mcp -- uv --directory /path/to/gobbler run gobbler-mcp

# Or configure Claude Desktop (~/.config/claude/claude_desktop_config.json)
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

### Batch Processing

```bash
gobbler batch youtube-playlist "https://youtube.com/playlist?list=..."
gobbler batch directory ./documents --pattern "*.pdf"
gobbler batch webpages urls.txt --output-dir ./pages
```

## Architecture

Gobbler follows a **CLI-first architecture**. All interfaces wrap the same CLI:

```
┌─────────────────────────────────────────────────────────────┐
│                     Your Automations                        │
└──────────────┬──────────────┬──────────────┬───────────────┘
               │              │              │
      ┌────────▼────┐  ┌──────▼─────┐  ┌─────▼─────┐
      │   Skills    │  │  gobbler   │  │    MCP    │
      │ (AI Agents) │  │    CLI     │  │  Protocol │
      └────────┬────┘  └──────┬─────┘  └─────┬─────┘
               │       calls  │              │ wraps
               └──────────────┼──────────────┘
                              ▼
                    ┌─────────────────┐
                    │  gobbler_core   │
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

**Why CLI-first?**
- Single implementation to maintain
- Users can run the same commands AI runs
- Easy to test and debug
- Shell scripts can orchestrate complex workflows

## Installation

### Prerequisites

- Python 3.11+
- [uv](https://docs.astral.sh/uv/) (Python package manager)
- Docker Desktop (for web/document conversion)
- ffmpeg (for audio extraction from video)

### Install

```bash
# Install uv
curl -LsSf https://astral.sh/uv/install.sh | sh

# Clone and install
git clone https://github.com/dylanisaac/gobbler.git
cd gobbler
uv sync

# Start Docker services
docker compose up -d

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

## Philosophy

**"Markdown is the lingua franca of human-AI communication."**

Gobbler exists because:
1. AI works best with structured text
2. Content exists in many formats
3. Converting content shouldn't require expertise in each format
4. AI agents need reliable, documented procedures—not just raw tools

We provide **excellent operating procedures** wrapped around excellent tools. Each skill doesn't just expose commands—it teaches AI agents *how to succeed*.

## License

MIT License - see [LICENSE](LICENSE) file.

## Acknowledgments

Built on the shoulders of giants:
- [Crawl4AI](https://github.com/unclecode/crawl4ai) - Web scraping
- [Docling](https://github.com/DS4SD/docling) - Document conversion
- [faster-whisper](https://github.com/SYSTRAN/faster-whisper) - Audio transcription
- [youtube-transcript-api](https://github.com/jdepoix/youtube-transcript-api) - YouTube transcripts
