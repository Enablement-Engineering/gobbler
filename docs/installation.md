---
icon: material/download
---

# Installation

Complete installation guide for Gobbler.

## Prerequisites

Before installing Gobbler, ensure you have:

| Requirement | Version | Check Command | Required |
|-------------|---------|---------------|----------|
| Python | 3.11+ | `python3 --version` | Yes |
| uv | Latest | `uv --version` | Yes |
| Docker | Latest | `docker --version` | For web/docs |
| ffmpeg | Latest | `ffmpeg -version` | For video |

### Installing Prerequisites

=== "macOS"

    ```bash
    # Install uv (Python package manager)
    curl -LsSf https://astral.sh/uv/install.sh | sh

    # Install ffmpeg (for audio extraction from video)
    brew install ffmpeg

    # Docker Desktop from https://docs.docker.com/desktop/mac/install/
    ```

=== "Linux"

    ```bash
    # Install uv
    curl -LsSf https://astral.sh/uv/install.sh | sh

    # Install ffmpeg
    sudo apt-get install ffmpeg  # Debian/Ubuntu
    sudo dnf install ffmpeg      # Fedora

    # Docker from https://docs.docker.com/engine/install/
    ```

=== "Windows"

    ```powershell
    # Install uv
    powershell -c "irm https://astral.sh/uv/install.ps1 | iex"

    # Install ffmpeg from https://ffmpeg.org/download.html

    # Docker Desktop from https://docs.docker.com/desktop/windows/install/
    ```

## Installation Steps

### 1. Clone the Repository

```bash
git clone https://github.com/dylanisaac/gobbler.git
cd gobbler
```

### 2. Install Dependencies

```bash
# Basic installation
make install

# With development dependencies (for contributing)
make dev

# Optional: For browser automation features
uv run playwright install chromium
```

### 3. Start Docker Services (Optional)

Docker services are needed for:

- **Web scraping** (Crawl4AI)
- **Document conversion** (Docling)

!!! note "Docker Resource Requirements"
    - **Docling** needs ~8GB RAM
    - **Crawl4AI** needs ~2GB RAM
    - Initial Docker image downloads can be large

```bash
# Start all services
make start-docker

# Check status
make status
```

### 4. Verify Installation

```bash
make verify
```

You should see:

```
✅ Python 3.11+ detected
✅ uv installed
✅ Gobbler installed
✅ Crawl4AI: Healthy
✅ Docling: Healthy
```

## What Works Without Docker

These features work immediately without Docker:

| Feature | Backend |
|---------|---------|
| YouTube transcripts | youtube-transcript-api |
| Audio transcription | faster-whisper (local) |
| YouTube downloads | yt-dlp |

## AI Assistant Integration

### OpenCode

Symlink Gobbler skills to OpenCode's skill directory:

```bash
mkdir -p ~/.config/opencode/skill
for skill in skills/gobbler-*/; do
  ln -sf "$(pwd)/$skill" ~/.config/opencode/skill/
done
```

### Claude Code

Skills are available from `skills/gobbler-*/SKILL.md` when working in the
Gobbler repo directory. You can also copy or symlink them into your agent's
skill directory.

## Configuration

Gobbler uses a YAML configuration file at `~/.config/gobbler/config.yml`:

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

### Common Issues

#### "Service unavailable"

```bash
# Start Docker services
make start-docker

# Check status
make status
```

#### "Python 3.11+ required"

Install Python 3.11 or higher from [python.org](https://www.python.org/downloads/).

#### "uv not found"

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

### Run Diagnostics

```bash
make diagnose
```

This checks all prerequisites and provides actionable fixes.

## Next Steps

- [Quick Start](QUICK_START.md) - Your first conversion
- [CLI Usage](cli.md) - Command reference
- [Skills](SKILLS.md) - AI agent integration
