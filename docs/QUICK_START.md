# Gobbler MCP - Quick Start Guide

Get up and running with Gobbler in 5 minutes! This guide covers the essentials to get your first transcription.

## Prerequisites Checklist

Before you begin, ensure you have:

- [ ] **Python 3.11+** - Check with `python3 --version`
- [ ] **uv package manager** - Install with `curl -LsSf https://astral.sh/uv/install.sh | sh`
- [ ] **Docker** (optional, for web/document conversion) - [Download Docker](https://docs.docker.com/get-docker/)
- [ ] **ffmpeg** (optional, for audio extraction) - Install with `brew install ffmpeg` (macOS)

## 3 Simple Steps to Your First Transcription

### Step 1: Install Gobbler

```bash
# Clone the repository
git clone https://github.com/Enablement-Engineering/gobbler.git
cd gobbler

# Install dependencies
make install
```

### Step 2: Install to Claude Code

```bash
# Show the installation command
make claude-install

# Run the displayed command (example):
claude mcp add gobbler-mcp -- uv --directory /path/to/gobbler run gobbler-mcp
```

Restart Claude Code after installation.

### Step 3: Try Your First Transcription

Open Claude Code and try:

```
"Transcribe this YouTube video: https://www.youtube.com/watch?v=dQw4w9WgXcQ"
```

That's it! Gobbler will extract the transcript and return it as clean markdown.

## Verify It Works

Run these verification commands to ensure everything is set up correctly:

```bash
# Verify installation
make verify

# Check for any issues
make diagnose
```

You should see:
- ✅ Python 3.11+ detected
- ✅ uv installed
- ✅ Gobbler MCP installed

## Need Web Scraping or Document Conversion?

If you want to use Gobbler's full feature set (web scraping, document conversion):

```bash
# Start Docker services
make start

# Verify services are running
make status
```

This starts:
- **Crawl4AI** - Web scraping with JavaScript rendering
- **Docling** - Document conversion (PDF, DOCX, PPTX, XLSX)
- **Redis** - Background job queue
- **RQ Worker** - Processes long-running tasks

## Common First-Run Issues

### Issue: "Python 3.11+ required"
**Solution:** Install Python 3.11 or higher from [python.org](https://www.python.org/downloads/)

### Issue: "uv not found"
**Solution:** Install uv package manager:
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

### Issue: "Gobbler MCP not installed"
**Solution:** Run the installation:
```bash
make install
```

### Issue: "Docker daemon not running"
**Solution:** Start Docker Desktop or run:
```bash
# macOS
open -a Docker

# Linux
sudo systemctl start docker
```

### Issue: "Services unavailable"
**Solution:** Start the services:
```bash
make start-docker
```

### Issue: YouTube transcription works, but web scraping doesn't
**Solution:** This is normal! YouTube transcription doesn't need Docker. For web scraping:
```bash
make start-docker
```

## What You Can Do Without Docker

Gobbler works great even without Docker! These features are available out of the box:

- ✅ **YouTube transcripts** - Extract official video transcripts
- ✅ **YouTube playlist batch** - Process entire playlists
- ✅ **YouTube downloads** - Download videos in various qualities
- ✅ **Audio/video transcription** - Whisper-based transcription with Metal acceleration
- ✅ **Batch audio processing** - Transcribe entire directories

## Available Commands

Here are the most useful commands for getting started:

```bash
make help           # Show all available commands
make verify         # Check installation and system health
make diagnose       # Run diagnostics and suggest fixes
make start          # Start all services (Docker + worker)
make stop           # Stop all services
make status         # Check service health
make logs           # View service logs
```

## Next Steps

Now that you're up and running:

1. **Explore capabilities** - Try different types of content:
   ```
   "Fetch this webpage as markdown: https://example.com"
   "Convert this PDF to markdown: /path/to/document.pdf"
   "Transcribe this audio file: /path/to/audio.mp3"
   ```

2. **Read the CLI guide** - Learn about all available commands in the [CLI Usage](cli.md) guide

3. **Explore skills** - See all available skills in the [Skills Reference](SKILLS.md)

4. **Configure Gobbler** - Customize settings at `~/.config/gobbler/config.yml` (optional)

## Getting Help

If you run into issues:

1. Run diagnostics: `make diagnose`
2. Check service logs: `make logs`
3. Review common issues above
4. Open an issue on [GitHub](https://github.com/Enablement-Engineering/gobbler/issues)

## Pro Tips

- **Background processing** - Long tasks automatically queue with `auto_queue=true`
- **Batch operations** - Process multiple items efficiently with batch tools
- **Health checks** - Use `make status` to verify all services are healthy
- **Configuration** - Customize behavior in `~/.config/gobbler/config.yml`

Happy Gobbling! 🦃
