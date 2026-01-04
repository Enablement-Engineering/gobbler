---
icon: material/wrench
---

# Setup & Troubleshooting

Complete guide for diagnosing and fixing Gobbler issues.

## Quick Health Check

Run this first to diagnose issues:

```bash
# Check CLI is installed
gobbler --version

# Check Docker services
docker ps --filter "name=gobbler" --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"

# Check individual services
curl -s http://localhost:5001/health && echo " - Docling OK"
curl -s http://localhost:11235/health && echo " - Crawl4AI OK"
```

## Common Issues & Solutions

### "Server disconnected without sending a response"

**Cause**: Docker service crashed (usually out of memory)

```bash
# Check which service crashed
docker ps -a --filter "name=gobbler"

# For document conversion - disable OCR or increase memory
gobbler document file.pdf --no-ocr -o output.md

# Or increase memory in docker-compose.yml
# Change: memory: 4g → memory: 8g
docker compose up -d docling
```

### "Connection refused" on port 5001/11235

**Cause**: Docker service not running

```bash
# Start the services
docker compose up -d

# Check they're running
docker compose ps

# View logs if still failing
docker logs gobbler-docling --tail 50
docker logs gobbler-crawl4ai --tail 50
```

### "Cannot connect to Docker daemon"

**Cause**: Docker Desktop not running

```bash
# macOS - Start Docker Desktop
open -a Docker

# Linux
sudo systemctl start docker

# Wait 30-60 seconds, then verify
docker info
```

### "command not found: gobbler"

**Cause**: CLI not installed or not in PATH

```bash
# Option 1: Run via uv
cd /path/to/gobbler
uv run gobbler --version

# Option 2: Install as tool
uv tool install .

# Option 3: Add to PATH
export PATH="$PATH:/path/to/gobbler/.venv/bin"
```

### YouTube "IP blocked" or "No transcript available"

```bash
# Check if video has captions (view on YouTube)

# Try different language
gobbler youtube "URL" --language en

# Use TranscriptAPI.com (paid, reliable)
export TRANSCRIPTAPI_KEY=your_key
gobbler youtube "URL"
```

### Audio transcription slow or failing

```bash
# Check ffmpeg is installed
ffmpeg -version

# Use smaller model
gobbler audio file.mp3 --model tiny

# For faster processing on Apple Silicon
gobbler audio file.mp3 --model small
```

### "OCR failed" on document conversion

```bash
# Disable OCR for digital PDFs
gobbler document file.pdf --no-ocr -o output.md

# If OCR needed, increase Docker memory
# Edit docker-compose.yml: memory: 8g
docker compose up -d docling
```

## Diagnostic Commands

### Full System Check

```bash
echo "=== Gobbler Diagnostics ==="

echo "\n[CLI]"
gobbler --version 2>/dev/null || echo "CLI not found"

echo "\n[Docker]"
docker info 2>/dev/null | head -5 || echo "Docker not running"

echo "\n[Services]"
docker ps --filter "name=gobbler" --format "{{.Names}}: {{.Status}}" 2>/dev/null

echo "\n[Health Checks]"
curl -s http://localhost:5001/health && echo " - Docling" || echo "Docling: FAILED"
curl -s http://localhost:11235/health && echo " - Crawl4AI" || echo "Crawl4AI: FAILED"
```

### View Service Logs

```bash
# Docling logs
docker logs gobbler-docling --tail 100

# Crawl4AI logs
docker logs gobbler-crawl4ai --tail 100
```

### Reset Everything

```bash
# Stop all services
docker compose down

# Remove containers and volumes
docker compose down -v

# Restart fresh
docker compose up -d

# Verify
docker compose ps
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
        <string>cd /path/to/gobbler && docker compose up -d</string>
    </array>
    <key>RunAtLoad</key>
    <true/>
</dict>
</plist>
```

Load it:

```bash
launchctl load ~/Library/LaunchAgents/com.gobbler.plist
```

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `GOBBLER_LOG_LEVEL` | Logging level | INFO |
| `TRANSCRIPTAPI_KEY` | TranscriptAPI.com key | - |
| `GOBBLER_CONFIG` | Config file path | `~/.config/gobbler/config.yaml` |

## Getting Help

- **Run diagnostics**: `make diagnose`
- **Check logs**: `docker logs gobbler-docling --tail 50`
- **GitHub Issues**: [Enablement-Engineering/gobbler/issues](https://github.com/Enablement-Engineering/gobbler/issues)
