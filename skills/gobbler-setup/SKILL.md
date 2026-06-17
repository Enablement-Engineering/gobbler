---
name: gobbler-setup
description: Installs, configures, and troubleshoots Gobbler. Triggers on install gobbler, setup, not working, connection refused, docker not running, or diagnostic/troubleshooting requests.
metadata:
  openclaw:
    emoji: 🔧
    requires:
      bins: []
    install: []
    homepage: https://github.com/Enablement-Engineering/gobbler
---

# Gobbler Setup & Troubleshooting

Complete guide for installing, configuring, and diagnosing Gobbler.

---

## Quick Health Check

Run this first to diagnose issues. `status --json` is the preferred agent-readable check:

```bash
# Check CLI is installed
gobbler --version

# Check core services and configuration
gobbler status --json

# Check Docker services when document/webpage conversion is degraded
docker ps --filter "name=gobbler" --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"

# Check individual services
curl -s http://localhost:5001/health && echo " ← Docling OK"
curl -s http://localhost:11235/health && echo " ← Crawl4AI OK"
```

---

## Installation

### Prerequisites

- Python 3.11+
- Docker runtime: Docker Desktop, Colima, or compatible Docker Engine
- uv (Python package manager)
- ffmpeg (for audio processing)

### Install Prerequisites (macOS)

```bash
# Install Homebrew if needed
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"

# Install dependencies
brew install uv ffmpeg

# Install Docker runtime (Docker Desktop or Colima)
brew install colima docker docker-compose
colima start --memory 10 --cpu 5
```

If you use Docker Desktop instead of Colima, install it from https://docker.com/products/docker-desktop and start the app before running Gobbler services. Gobbler's document service is configured for up to 8 GB RAM and 4 CPUs, so allocate enough Docker resources before starting Docling.

### Install Prerequisites (Linux/Ubuntu)

```bash
# Install uv
curl -LsSf https://astral.sh/uv/install.sh | sh

# Install ffmpeg
sudo apt update && sudo apt install -y ffmpeg

# Install Docker
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker $USER
```

### Install Gobbler

```bash
# Clone repository
git clone https://github.com/Enablement-Engineering/gobbler.git
cd gobbler

# Install Python packages
uv sync

# Install CLI globally
uv tool install .

# Verify installation
gobbler --version
```

### Start Docker Services

```bash
# Start all services
docker compose up -d || docker-compose up -d

# Wait for services to be healthy (30-60 seconds)
docker compose ps || docker-compose ps
```

### Verify Installation

```bash
# Test YouTube conversion
gobbler youtube "https://www.youtube.com/watch?v=dQw4w9WgXcQ"

# Test webpage conversion
gobbler webpage "https://example.com"
```

---

## Configuration

### Config File Location

```
~/.config/gobbler/config.yml
```

### Default Configuration

```yaml
# Proxy services (optional - for bypassing rate limits)
proxy_services:
  webshare:
    type: rotating
    username: ${WEBSHARE_USER}
    password: ${WEBSHARE_PASS}

# Provider configuration
providers:
  youtube:
    default: youtube-transcript-api
    youtube-transcript-api:
      proxy: webshare  # Optional: use proxy

  webpage:
    default: crawl4ai
    crawl4ai:
      timeout: 30
      proxy: webshare  # Optional: use proxy

# Service URLs
services:
  docling:
    host: localhost
    port: 5001
  crawl4ai:
    host: localhost
    port: 11235

# Output settings
output:
  default_format: frontmatter
  default_directory: null  # Set to auto-save, e.g., ~/Documents/Gobbler
```

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `GOBBLER_LOG_LEVEL` | Logging level | INFO |
| `TRANSCRIPTAPI_KEY` | TranscriptAPI.com key | - |
| `WEBSHARE_USER` | Webshare proxy username | - |
| `WEBSHARE_PASS` | Webshare proxy password | - |

---

## Common Issues & Solutions

### Issue: "Server disconnected without sending a response"

**Cause**: Docker service crashed (usually out of memory)

**Solution**:

```bash
# Check which service crashed
docker ps -a --filter "name=gobbler"

# For document conversion - disable OCR or increase memory
gobbler document file.pdf --no-ocr -o output.md

# Or increase memory in docker-compose.yml
# Change: memory: 4g → memory: 8g
docker compose up -d docling || docker-compose up -d docling
```

### Issue: "Connection refused" on port 5001/11235

**Cause**: Docker service not running

**Solution**:

```bash
# Start the services
docker compose up -d || docker-compose up -d

# Check they're running
docker compose ps || docker-compose ps

# View logs if still failing
docker logs gobbler-docling --tail 50
docker logs gobbler-crawl4ai --tail 50
```

### Issue: "Cannot connect to Docker daemon"

**Cause**: Docker runtime not running

**Solution**:

```bash
# Start Colima (macOS lightweight Docker runtime)
colima start --memory 10 --cpu 5
docker context use colima

# Or start Docker Desktop (macOS)
open -a Docker

# Start Docker (Linux)
sudo systemctl start docker

# Wait 30-60 seconds, then verify
docker info
```

### Issue: "command not found: gobbler"

**Cause**: CLI not installed or not in PATH

**Solution**:

```bash
# Option 1: Install globally with uv
cd /path/to/gobbler
uv tool install .

# Option 2: Run via uv
cd /path/to/gobbler
uv run gobbler --version

# Option 3: Add to PATH
export PATH="$PATH:$HOME/.local/bin"
```

### Issue: YouTube "IP blocked" or "No transcript available"

**Cause**: YouTube rate limiting or video has no captions

**Solution**:

```bash
# Check if video has captions (view on YouTube)

# Try different language
gobbler youtube "URL" --language en

# Configure proxy in ~/.config/gobbler/config.yml
# See Configuration section above
```

### Issue: Audio transcription slow or failing

**Cause**: Whisper model too large or ffmpeg missing

**Solution**:

```bash
# Check ffmpeg is installed
ffmpeg -version

# Use smaller model
gobbler audio file.mp3 --model tiny

# For faster processing on Apple Silicon
gobbler audio file.mp3 --model small
```

### Issue: "OCR failed" on document conversion

**Cause**: OCR requires more memory, or document is corrupted

**Solution**:

```bash
# Disable OCR for digital PDFs
gobbler document file.pdf --no-ocr -o output.md

# If OCR needed, increase Docker memory
# Edit docker-compose.yml: memory: 8g
docker compose up -d docling || docker-compose up -d docling
```

---

## Diagnostic Commands

### Full System Check

```bash
#!/bin/bash
echo "=== Gobbler Diagnostics ==="

echo -e "\n[CLI]"
gobbler --version 2>/dev/null || echo "CLI not found"

echo -e "\n[Docker]"
docker info 2>/dev/null | head -5 || echo "Docker not running"

echo -e "\n[Services]"
docker ps --filter "name=gobbler" --format "{{.Names}}: {{.Status}}" 2>/dev/null

echo -e "\n[Health Checks]"
curl -s http://localhost:5001/health 2>/dev/null && echo " ← Docling" || echo "Docling: FAILED"
curl -s http://localhost:11235/health 2>/dev/null && echo " ← Crawl4AI" || echo "Crawl4AI: FAILED"

echo -e "\n[Disk Space]"
df -h ~ | tail -1

echo -e "\n[Memory]"
vm_stat | head -5
```

### View Service Logs

```bash
# Docling logs
docker logs gobbler-docling --tail 100

# Crawl4AI logs
docker logs gobbler-crawl4ai --tail 100

# Daemon logs
gobbler daemon logs --lines 100
```

### Reset Everything

```bash
# Stop all services
docker compose down

# Remove containers and volumes
docker compose down -v

# Restart fresh
docker compose up -d || docker-compose up -d

# Verify
docker compose ps || docker-compose ps
```

---

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
        <string>cd /path/to/gobbler && (docker compose up -d || docker-compose up -d) && sleep 10 && gobbler daemon start</string>
    </array>
    <key>RunAtLoad</key>
    <true/>
    <key>StandardOutPath</key>
    <string>/tmp/gobbler-startup.log</string>
    <key>StandardErrorPath</key>
    <string>/tmp/gobbler-startup.log</string>
</dict>
</plist>
```

Load it:

```bash
launchctl load ~/Library/LaunchAgents/com.gobbler.plist
```

---

## Getting Help

- **Issues**: https://github.com/Enablement-Engineering/gobbler/issues
- **Check logs**: `gobbler daemon logs -f`
- **Docker logs**: `docker logs gobbler-docling --tail 50`
