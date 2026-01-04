---
icon: material/lightning-bolt
---

# Gobbler Skills

Skills are reusable, filesystem-based instructions that provide Claude with domain-specific expertise. Gobbler's skills give Claude the knowledge to convert content to markdown using YouTube APIs, Whisper transcription, browser automation, and more.

## What are Skills?

Skills are markdown files (`SKILL.md`) with YAML frontmatter that Claude discovers and loads on-demand. Each skill contains:

- **Metadata** (frontmatter) - `name` and `description` that tell Claude when to use the skill
- **Instructions** - Workflows, examples, and guidance for completing tasks
- **Scripts** - Executable Python scripts that Claude runs via bash

Skills use **progressive disclosure**: Claude only loads ~100 tokens of metadata at startup. The full instructions are read only when the skill is triggered, and scripts run without loading their code into context.

## Skill Structure

Each Gobbler skill follows this structure:

```
skills/gobbler-youtube/
├── SKILL.md           # Instructions with YAML frontmatter
└── scripts/
    ├── transcribe.py  # UV script for transcription
    ├── download.py    # UV script for downloads
    └── get_metadata.py
```

The `SKILL.md` file contains:

```yaml
---
name: gobbler-youtube
description: Transcribe YouTube videos to markdown. Use when the user wants to get a transcript, transcribe a video, or extract text from YouTube.
---

# YouTube Transcription

## Quick Start
Run the transcription script:
\`\`\`bash
uv run scripts/transcribe.py "https://youtube.com/watch?v=VIDEO_ID"
\`\`\`

## Available Scripts
- `transcribe.py` - Extract video transcripts
- `download.py` - Download video/audio files
...
```

## How Claude Uses Skills

1. **Discovery** - Claude sees skill metadata in its system prompt
2. **Trigger** - When your request matches a skill's description, Claude reads `SKILL.md`
3. **Execute** - Claude follows the instructions, running scripts via bash as needed
4. **Output** - Scripts return markdown that Claude can use or save

Skills work with Claude Code, Claude Desktop, and OpenCode. They're discovered from:
- `skills/gobbler-*/SKILL.md` (in the Gobbler repo)
- `.claude/skills/*/SKILL.md` (Claude Code compatible)

## Available Skills

| Skill | Description | Backend |
|-------|-------------|---------|
| `gobbler-youtube` | YouTube transcription and downloads | youtube-transcript-api, yt-dlp, TranscriptAPI.com |
| `gobbler-webpage` | Web page fetching and crawling | Crawl4AI Docker (port 11235) |
| `gobbler-document` | PDF/DOCX/PPTX/XLSX conversion | Docling Docker (port 5001) |
| `gobbler-audio` | Audio/video transcription | faster-whisper, ffmpeg |
| `gobbler-browser` | Browser control via extension | WebSocket (port 4625) |
| `gobbler-notebooklm` | NotebookLM interaction via browser | Browser extension + WebSocket |
| `gobbler-chatgpt` | ChatGPT interaction via browser | Browser extension + WebSocket |
| `gobbler-claude` | Claude.ai interaction via browser | Browser extension + WebSocket |
| `gobbler-gemini` | Google Gemini interaction via browser | Browser extension + WebSocket |
| `gobbler-setup` | Installation, configuration, and troubleshooting | Pure Python |
| `gobbler-utils` | Shared utilities | Pure Python |

## Backend Services

Skills execute UV scripts that connect to these backends:

| Backend | Port | Purpose |
|---------|------|---------|
| Crawl4AI | 11235 | Web scraping with JavaScript rendering |
| Docling | 5001 | Document conversion (PDF, DOCX, etc.) |
| YouTube APIs | - | Transcript extraction |
| Whisper | - | Local audio transcription |
| Relay | 4625 | WebSocket bridge to browser extension |

**Browser skills require:**

1. Relay server running on port 4625 (auto-starts when skill runs)
2. Browser extension installed and showing "Connected"
3. Target tabs in the "Gobbler" tab group

**Relay commands:**
```bash
uv run src/gobbler_relay/relay.py --status  # Check if running
uv run src/gobbler_relay/relay.py --daemon  # Start manually
uv run src/gobbler_relay/relay.py --stop    # Stop manually
```

## Installation

### Via Claude Code Plugin Marketplace (Recommended)

```bash
# Install Gobbler as a plugin
/plugin add Enablement-Engineering/gobbler
```

### Via Git Clone

Skills are located in `skills/gobbler-*/` at the project root. Clone and configure:

```bash
git clone https://github.com/Enablement-Engineering/gobbler.git
```

### Prerequisites

Skills require:

1. **UV** - Python package manager with script support
   ```bash
   curl -LsSf https://astral.sh/uv/install.sh | sh
   ```

2. **Docker services** (for webpage/document conversion)
   ```bash
   # Crawl4AI
   docker run -d -p 11235:11235 --name gobbler-crawl4ai unclecode/crawl4ai:basic

   # Docling
   docker run -d -p 5001:5001 --name gobbler-docling quay.io/docling-project/docling-serve:latest
   ```

3. **ffmpeg** (for audio transcription)
   ```bash
   brew install ffmpeg  # macOS
   ```

## Environment Variables

Add to your `~/.zshrc` or `~/.bashrc`:

```bash
# YouTube transcript providers
export WEBSHARE_USER=your_webshare_username      # Rotating proxy (free API)
export WEBSHARE_PASS=your_webshare_password
export TRANSCRIPTAPI_KEY=your_transcriptapi_key  # Paid API fallback
```

## Skill Details

### gobbler-youtube

Transcribe YouTube videos to markdown with multiple provider options.

**Scripts:**
- `transcribe.py` - Extract video transcripts
- `download.py` - Download video/audio files
- `get_metadata.py` - Get video metadata

**Providers:**

| Provider | Cost | Reliability | Usage |
|----------|------|-------------|-------|
| `youtube-transcript-api` | Free | May get IP blocked | Default |
| `transcriptapi` | ~$0.01/video | High, no IP blocks | `--provider transcriptapi` |
| `auto` | Free + fallback | Best of both | `--provider auto` |

**Usage:**
```bash
cd skills/gobbler-youtube/scripts

# Basic (uses free API with Webshare proxy if configured)
uv run transcribe.py "https://youtube.com/watch?v=VIDEO_ID"

# With timestamps
uv run transcribe.py "https://youtube.com/watch?v=VIDEO_ID" --timestamps

# Use paid API directly
uv run transcribe.py "https://youtube.com/watch?v=VIDEO_ID" --provider transcriptapi

# Auto-fallback (try free first, use paid if blocked)
uv run transcribe.py "https://youtube.com/watch?v=VIDEO_ID" --provider auto

# Download video
uv run download.py "https://youtube.com/watch?v=VIDEO_ID" --output-dir ./downloads
```

**Bypassing IP Blocks:**

YouTube may block your IP when using the free `youtube-transcript-api`. Solutions:

1. **Webshare Proxy** (~$3.50/month) - Rotating residential proxies
   - Sign up at https://www.webshare.io/
   - Get credentials from https://proxy.webshare.io/proxy/rotating
   - Set `WEBSHARE_USER` and `WEBSHARE_PASS` environment variables

2. **TranscriptAPI.com** (~$0.01/video) - Paid API, no IP blocks
   - Sign up at https://transcriptapi.com/
   - Get API key from https://transcriptapi.com/dashboard/api-keys
   - Set `TRANSCRIPTAPI_KEY` environment variable

---

### gobbler-webpage

Convert web pages to markdown using Crawl4AI.

**Requires:** Crawl4AI Docker container on port 11235

**Scripts:**
- `fetch.py` - Basic page fetch
- `fetch_with_selector.py` - Extract specific content with CSS/XPath
- `crawl.py` - Recursive site crawling

**Usage:**
```bash
cd skills/gobbler-webpage/scripts

# Basic fetch
uv run fetch.py "https://example.com"

# With CSS selector
uv run fetch_with_selector.py "https://example.com" --selector "article.main"

# Crawl entire site
uv run crawl.py "https://docs.example.com" --max-depth 2 --max-pages 50
```

---

### gobbler-document

Convert documents (PDF, DOCX, PPTX, XLSX) to markdown using Docling.

**Requires:** Docling Docker container on port 5001

**Scripts:**
- `convert.py` - Convert document to markdown

**Usage:**
```bash
cd skills/gobbler-document/scripts

# Convert PDF
uv run convert.py /path/to/document.pdf

# With OCR disabled (faster)
uv run convert.py /path/to/document.pdf --no-ocr

# Save to file
uv run convert.py /path/to/document.pdf --output document.md
```

---

### gobbler-audio

Transcribe audio/video files using faster-whisper with Metal/CoreML acceleration.

**Requires:** ffmpeg installed

**Scripts:**
- `transcribe.py` - Transcribe audio/video to text
- `extract_audio.py` - Extract audio from video files

**Usage:**
```bash
cd skills/gobbler-audio/scripts

# Transcribe audio
uv run transcribe.py /path/to/audio.mp3

# Use larger model for better accuracy
uv run transcribe.py /path/to/video.mp4 --model medium

# Extract audio from video first (for large files)
uv run extract_audio.py /path/to/video.mp4 --output audio.mp3
```

**Model Sizes:**

| Model | Speed | Accuracy | VRAM |
|-------|-------|----------|------|
| tiny | Fastest | Lower | ~1GB |
| base | Fast | Moderate | ~1GB |
| small | Moderate | Good | ~2GB |
| medium | Slower | Better | ~5GB |
| large | Slowest | Best | ~10GB |

---

### gobbler-browser

Control browser via Gobbler browser extension.

**Requires:**
- Gobbler browser extension installed
- MCP server running (provides WebSocket server on port 4625)

**Scripts:**
- `browser_api.py` - Browser control commands
- `notebooklm.py` - NotebookLM-specific interactions

**Note:** These scripts require the MCP server to be running as it provides the WebSocket relay to the browser extension.

**Usage:**
```bash
cd skills/gobbler-browser/scripts

# Check connection
uv run browser_api.py check

# List tabs
uv run browser_api.py tabs

# Extract current page
uv run browser_api.py extract

# Execute JavaScript
uv run browser_api.py execute "document.title"
```

---

### gobbler-notebooklm

Interact with NotebookLM via browser automation.

**Requires:**
- Gobbler browser extension installed
- MCP server running (provides WebSocket server on port 4625)
- NotebookLM tab in the Gobbler tab group

**Scripts:**
- `notebooklm.py` - NotebookLM CLI with query, list, and info commands

**Usage:**
```bash
cd skills/gobbler-notebooklm/scripts

# List available NotebookLM tabs
uv run notebooklm.py list

# Get notebook info
uv run notebooklm.py info

# Send a query and get response
uv run notebooklm.py query "What are the key points in this document?"

# Query specific tab with custom timeout
uv run notebooklm.py query "Summarize the main arguments" --tab-id 12345 --timeout 120
```

---

### gobbler-chatgpt

Interact with ChatGPT conversations via browser automation.

**Requires:**
- Gobbler browser extension installed
- MCP server running (provides WebSocket server on port 4625)
- ChatGPT tab in the Gobbler tab group

**Usage:**
```bash
# List ChatGPT tabs
gobbler chatgpt list

# Send message and wait for response
gobbler chatgpt query "Your message here" --timeout 150

# Get last response
gobbler chatgpt last

# Get chat history
gobbler chatgpt history --count 10
```

---

### gobbler-claude

Interact with Claude.ai conversations via browser automation.

**Requires:**
- Gobbler browser extension installed
- MCP server running (provides WebSocket server on port 4625)
- Claude.ai tab in the Gobbler tab group

**Usage:**
```bash
# List Claude tabs
gobbler claude list

# Send message and wait for response
gobbler claude query "Your message here" --timeout 150

# Get last response
gobbler claude last

# Get chat history
gobbler claude history --count 10
```

---

### gobbler-gemini

Interact with Google Gemini conversations via browser automation.

**Requires:**
- Gobbler browser extension installed
- MCP server running (provides WebSocket server on port 4625)
- Gemini tab in the Gobbler tab group
- Signed into Google account

**Usage:**
```bash
# List Gemini tabs
gobbler gemini list

# Send message and wait for response
gobbler gemini query "Your message here" --timeout 150

# Get last response
gobbler gemini last

# Get chat history
gobbler gemini history --count 10
```

---

### gobbler-setup

Install, configure, and troubleshoot Gobbler.

**Usage:**
```bash
# Quick health check
gobbler --version
gobbler daemon status
docker ps --filter "name=gobbler"

# Check individual services
curl -s http://localhost:5001/health
curl -s http://localhost:11235/health
```

See the full [Setup & Troubleshooting](setup-troubleshooting.md) guide for complete installation and troubleshooting information.

---

### gobbler-utils

Shared utilities used by other skills.

**Scripts:**
- `frontmatter.py` - Generate YAML frontmatter for different content types
- `docker_health.py` - Check Docker service health
- `http_client.py` - HTTP client with retry logic

**Usage:**
```bash
cd skills/gobbler-utils/scripts

# Check Docker services
uv run docker_health.py all
uv run docker_health.py crawl4ai
uv run docker_health.py docling

# Generate frontmatter
uv run frontmatter.py youtube --url "https://..." --title "Video" --duration 300
uv run frontmatter.py webpage --url "https://..." --title "Page" --word-count 1000
```

## UV Script Format

Skill scripts use PEP 723 inline dependencies, making them self-contained:

```python
#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "youtube-transcript-api>=0.6.0",
#   "yt-dlp>=2024.0.0",
# ]
# ///

import sys
# Script implementation...
```

When Claude runs `uv run scripts/transcribe.py`, UV automatically installs dependencies on first run. No separate `requirements.txt` or virtual environment setup is needed.
