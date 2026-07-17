---
icon: material/rocket-launch
---

# Quick start

This path gets the current source checkout running without assuming a global Python environment.

## 1. Install

Requirements: Python 3.11+ and [uv](https://docs.astral.sh/uv/).

```bash
git clone https://github.com/Enablement-Engineering/gobbler.git
cd gobbler
uv sync
```

Check the CLI and local runtime:

```bash
uv run gobbler --version
uv run gobbler doctor --json
```

`doctor --json` may report document or webpage conversion as degraded when Docker services are not running. That does not prevent YouTube or local audio conversion.

## 2. Run a conversion

```bash
# Print Markdown to stdout
uv run gobbler youtube "https://youtube.com/watch?v=VIDEO_ID"

# Save Markdown to a file
uv run gobbler youtube \
  "https://youtube.com/watch?v=VIDEO_ID" \
  -o ./outputs/video.md
```

YouTube URLs can also be read from stdin:

```bash
printf '%s\n' "https://youtube.com/watch?v=VIDEO_ID" | uv run gobbler youtube -o video.md
```

## 3. Add optional backends

### Audio/video

Install ffmpeg, then use local faster-whisper:

```bash
# macOS
brew install ffmpeg

uv run gobbler audio meeting.mp3 --model small -o meeting.md
```

The first local transcription downloads the selected Whisper model.

### Documents and web pages

Docker services provide Docling and Crawl4AI:

```bash
make start-docker
uv run gobbler doctor --json

uv run gobbler document report.pdf --no-ocr -o report.md
uv run gobbler webpage "https://example.com" --no-proxy -o page.md
```

`make start-docker` starts only the two Compose services. It does not start a queue worker.

## Batch work

All three batch commands support `--dry-run`:

```bash
uv run gobbler batch youtube-playlist \
  "https://youtube.com/playlist?list=PLAYLIST_ID" \
  -o ./transcripts --dry-run

uv run gobbler batch directory ./documents -o ./markdown --pattern "*.pdf" --dry-run

uv run gobbler batch webpages urls.txt -o ./pages --dry-run
```

Queueing is explicit and currently available for webpage batches:

```bash
uv run gobbler batch webpages urls.txt -o ./pages --queue --json
uv run gobbler jobs worker start
uv run gobbler jobs list
```

The queue uses a local SQLite database. There is no Redis/RQ requirement and no automatic queueing of long commands.

## Install the CLI globally

If you prefer `gobbler` without `uv run`:

```bash
uv tool install .
gobbler --version
```

Reinstall after pulling source changes:

```bash
uv tool install . --force
```

## Install Skills for an AI agent

```bash
npx skills@latest add Enablement-Engineering/gobbler --list
npx skills@latest add Enablement-Engineering/gobbler
```

The Skills installer does not install the CLI.

## Next steps

- [Installation](installation.md): platform prerequisites, Docker, and browser setup.
- [CLI usage](cli.md): current command families and output contracts.
- [Configuration](configuration.md): exact YAML schema and integration-specific environment variables.
- [Setup and troubleshooting](setup-troubleshooting.md): diagnostics and recovery.
- [Browser extension](browser-extension.md): intentionally selected authenticated tabs.
