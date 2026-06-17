<p align="center">
  <img src="docs/assets/Gobby Feasting (small).png" alt="Gobby the Turkey mascot consuming PDF, HTML, DOCX, and VIDEO files, outputting clean MD blocks" width="500">
</p>

# Gobbler

> **Universal Content Conversion to Markdown for AI**

Gobbler transforms any content—YouTube videos, web pages, documents, audio files, even live browser sessions—into clean, structured markdown that AI systems can immediately reason about.

[![Tests](https://github.com/Enablement-Engineering/gobbler/actions/workflows/test.yml/badge.svg)](https://github.com/Enablement-Engineering/gobbler/actions/workflows/test.yml)
[![Security](https://github.com/Enablement-Engineering/gobbler/actions/workflows/security.yml/badge.svg)](https://github.com/Enablement-Engineering/gobbler/actions/workflows/security.yml)
[![Docs](https://img.shields.io/badge/docs-GitHub%20Pages-blue)](https://enablement-engineering.github.io/gobbler/)
[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/license-MIT-yellow.svg)](LICENSE)

## The Problem

AI assistants work best with markdown. But content exists in countless formats—PDFs, videos, web pages behind logins, audio recordings. Getting that content into a format AI can use requires:

- Different tools for each content type
- Custom scripts to extract and format
- Lost metadata and inconsistent output
- No unified way for AI agents to access content

**Gobbler solves this.** One CLI, one output format, multiple content types.

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

## Project Status

Gobbler is an **active beta** project focused on reliable, agent-friendly content conversion. The supported automation surface is intentionally CLI-first:

- **Primary interface:** `gobbler` CLI for humans, scripts, and AI agents.
- **Agent experience:** markdown Skills and setup docs teach agents the same commands a human can run and verify.
- **Browser support:** optional local extension for authenticated browser sessions and supported AI chat surfaces.

See the [security policy](SECURITY.md) and [agent usage guide](https://enablement-engineering.github.io/gobbler/agents/) for the supported automation workflow.

## CLI-First, Skills-Ready

Gobbler's primary interface is the `gobbler` CLI. Agents use Skills to learn those same commands, and the browser extension adds authenticated browser-session access through the CLI. For agent workflows, start with the [agent usage guide](https://enablement-engineering.github.io/gobbler/agents/).

### 1. CLI

```bash
gobbler youtube URL              # YouTube transcripts
gobbler audio FILE               # Audio/video transcription
gobbler document FILE            # PDF, DOCX, PPTX, XLSX
gobbler webpage URL              # Web pages (JS-rendered)
gobbler batch youtube-playlist URL  # Batch processing
```

### 2. Skills (For CLI-Capable AI Agents)

Skills are markdown instruction files (`SKILL.md`) that teach AI agents how to use the `gobbler` CLI. The language in this repo is intentionally platform-neutral: a Gobbler skill is for any AI agent that can read skill files, run shell commands, and inspect output files.

```text
skills/
├── gobbler/          # 🦃 Convert/extract/transcribe/archive to markdown
│   └── references/   # YouTube, audio, document, webpage, and batch details
├── gobbler-browser/  # 🔌 Browser automation + AI chat integrations
└── gobbler-setup/    # 🔧 Installation and troubleshooting
```

The main `gobbler` skill covers normal content-to-markdown conversion. Detailed recipes live in `skills/gobbler/references/`, so agents can load YouTube, audio, document, webpage, or batch specifics only when needed.

**Install skills with the open skills installer:**

```bash
# Inspect available Gobbler skills
npx skills@latest add Enablement-Engineering/gobbler --list

# Interactive install: choose skills and target agent(s)
npx skills@latest add Enablement-Engineering/gobbler

# Non-interactive example: install the main conversion skill globally
npx skills@latest add Enablement-Engineering/gobbler --skill gobbler --global --yes
```

The installer copies or symlinks skill files into the selected agent's skill directory. It does **not** install the `gobbler` CLI itself; install Gobbler with `make install` or `uv tool install .` first.

Skills use **progressive disclosure**—agents see lightweight metadata first, then read full CLI instructions or reference files when triggered.

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

Gobbler provides a CLI-first architecture. Skills teach AI agents to call the
same CLI that humans and scripts use.

```
┌─────────────────────────────────────────────────────────────┐
│                     Your Automations                        │
└──────────────┬──────────────────────┬──────────────────────┘
               │                      │
      ┌────────▼────┐          ┌──────▼─────┐
      │   Skills    │          │  gobbler   │
      │(CLI instrs) │          │    CLI     │
      └────────┬────┘          └──────┬─────┘
               │                      │
               └──────────────┬───────┘
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

**Skills** are markdown files that teach agents which CLI commands to run.

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
- [Agent Usage](https://Enablement-Engineering.github.io/gobbler/agents/) - CLI-first patterns for agents
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
