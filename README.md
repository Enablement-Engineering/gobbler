<p align="center">
  <img src="docs/assets/Gobby Feasting (small).png" alt="Gobby the Turkey mascot consuming PDF, HTML, DOCX, and VIDEO files, outputting clean MD blocks" width="500">
</p>

# Gobbler

> **CLI-first content conversion to Markdown for humans and AI agents**

Gobbler converts YouTube transcripts, audio/video files, documents, web pages, and intentionally selected browser tabs into structured Markdown. The public automation contract is the `gobbler` CLI; the Skills in this repository teach agents to use that same CLI.

[![Tests](https://github.com/Enablement-Engineering/gobbler/actions/workflows/test.yml/badge.svg)](https://github.com/Enablement-Engineering/gobbler/actions/workflows/test.yml)
[![Security](https://github.com/Enablement-Engineering/gobbler/actions/workflows/security.yml/badge.svg)](https://github.com/Enablement-Engineering/gobbler/actions/workflows/security.yml)
[![Docs](https://img.shields.io/badge/docs-GitHub%20Pages-blue)](https://enablement-engineering.github.io/gobbler/)
[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/license-MIT-yellow.svg)](LICENSE)

## Project status

Gobbler is an **active beta**. Current supported surfaces are:

- `gobbler` for conversion, diagnostics, batches, jobs, providers, and browser automation.
- Local Markdown Skills for CLI-capable AI agents.
- An optional Chromium extension and local relay for tabs deliberately placed in a **Gobbler** tab group.

Websites and AI chat products can change their DOM without notice, so browser integrations are more fragile than direct file and URL conversion.

## Install from source

Requirements: Python 3.11+ and [uv](https://docs.astral.sh/uv/). Docker is optional for document/webpage conversion; ffmpeg is required for audio/video transcription and YouTube frame extraction.

```bash
git clone https://github.com/Enablement-Engineering/gobbler.git
cd gobbler

# Reproducible source-checkout environment
uv sync
uv run gobbler --version
uv run gobbler doctor --json
```

Run commands from the checkout with `uv run gobbler ...`, or install an isolated global CLI:

```bash
uv tool install .
gobbler --version
```

For local development, use `uv sync --extra dev`. See the [installation guide](https://enablement-engineering.github.io/gobbler/installation/) for Docker and browser setup.

## Convert content

```bash
# YouTube transcript; URL can also come from stdin
uv run gobbler youtube "https://youtube.com/watch?v=VIDEO_ID" -o transcript.md

# Deterministic visual overview; no transcript provider is called
uv run gobbler youtube "https://youtube.com/watch?v=VIDEO_ID" \
  --frames-only --frames 8 -o overview.md

# Repeat exact timestamps or refine an inclusive range
uv run gobbler youtube "https://youtube.com/watch?v=VIDEO_ID" \
  --frames-only --frame-at 24:16.500 --frame-at 24:18.200 -o exact.md
uv run gobbler youtube "https://youtube.com/watch?v=VIDEO_ID" \
  --frames-only --frame-range 24:12-24:24 --range-frames 5 -o refinement.md

# Local faster-whisper transcription
uv run gobbler audio meeting.mp3 --model small -o meeting.md

# Docling service required
uv run gobbler document report.pdf --no-ocr -o report.md

# Crawl4AI service required
uv run gobbler webpage "https://example.com" --no-proxy -o page.md
```

Without `-o`, normal Markdown output is written to stdout. `--format json` produces a single JSON object for individual conversions. Batch commands use `--json` for newline-delimited JSON events.

Frame requests require durable storage through `--output` or `--frames-dir`. Gobbler writes deterministic JPEG files under `<output-stem>.assets/frames/` by default and returns timestamped Markdown/JSON manifests. Gobbler extracts the requested frames; the calling human or agent interprets them. This release does not add frame extraction for playlists or local video files. See the [YouTube frame workflow](https://enablement-engineering.github.io/gobbler/guides/youtube/).

## Service readiness

YouTube and local audio conversion do not need Docker. Document and webpage conversion use the services in `docker-compose.yml`:

```bash
make start-docker
uv run gobbler doctor --json
```

- Crawl4AI: `http://localhost:11235`
- Docling: `http://localhost:5001`

`gobbler doctor --json` is the broad agent-friendly diagnostic. `gobbler status --json` focuses on conversion-provider readiness and exits nonzero when overall status is degraded while still emitting JSON.

## Batch and queued work

```bash
# Playlist output directory is required
uv run gobbler batch youtube-playlist \
  "https://youtube.com/playlist?list=PLAYLIST_ID" \
  -o ./transcripts --dry-run

# Local files
uv run gobbler batch directory ./documents -o ./markdown --pattern "*.pdf"

# URL list; one URL per line
uv run gobbler batch webpages urls.txt -o ./pages --dry-run

# Explicitly queue a webpage batch in the SQLite job store
uv run gobbler batch webpages urls.txt -o ./pages --queue --json
uv run gobbler jobs worker start
uv run gobbler jobs list
```

Queued work is opt-in through `--queue`. The current queue is SQLite-backed; Redis/RQ is not required.

## Providers and configuration

Inspect the runtime instead of relying on a static provider list:

```bash
uv run gobbler providers list --format json
uv run gobbler config path
uv run gobbler config show
uv run gobbler config init
```

The default config file is `~/.config/gobbler/config.yml`. Configuration is deep-merged over built-in defaults. CLI flags take precedence for the commands that expose them. Environment variables are used by specific integrations, not as a general override system:

- `TRANSCRIPTAPI_KEY`: paid YouTube transcript fallback.
- `WEBSHARE_USER` / `WEBSHARE_PASS` or `YOUTUBE_PROXY`: YouTube proxy configuration.
- `CRAWL4AI_PROXY`: webpage proxy fallback.
- `OPENAI_API_KEY`: `openai-whisper` transcription provider.
- `CRAWL4AI_API_TOKEN`: Docker Compose API token.
- `GOBBLER_MODELS_PATH`: Docling model-cache mount.

See the [configuration guide](https://enablement-engineering.github.io/gobbler/configuration/) for the current schema.

## Browser extension

The extension communicates with a local relay on port `4625`. Most browser operations auto-start it; `browser status` is intentionally read-only and does not.

```bash
uv run gobbler relay start
uv run gobbler browser status
uv run gobbler browser list
uv run gobbler browser extract -o page.md
uv run gobbler notebooklm query "Summarize the current notebook"
```

Browser command guards target tabs whose group ID matches the extension's stored Gobbler group. Use **Allow & Add**/**Add Tab** to create or populate it and grant origin access for extraction and page APIs. A different group with the same title does not match, while manually moving a tab into the existing managed group makes it eligible for commands; debugger-based `browser exec` does not require the separate origin permission. The extension does not bypass authentication, access controls, rate limits, or bot detection. See the [browser extension guide](https://enablement-engineering.github.io/gobbler/browser-extension/).

## AI-agent Skills

```bash
# Inspect available Skills
npx skills@latest add Enablement-Engineering/gobbler --list

# Interactive install
npx skills@latest add Enablement-Engineering/gobbler

# Install the main conversion Skill globally
npx skills@latest add Enablement-Engineering/gobbler \
  --skill gobbler --global --yes
```

This installs Skill files only; it does not install the Gobbler CLI. The repository currently provides:

- `gobbler`: conversion and batch workflows.
- `gobbler-browser`: authenticated-tab and supported AI-chat workflows.
- `gobbler-setup`: installation, diagnostics, and service troubleshooting.

## Output contract

Successful Markdown conversions include YAML frontmatter when the selected converter provides metadata. For automation:

- Individual `--format json` commands emit one JSON object.
- Batch `--json` commands emit JSON Lines.
- Versioned conversion, diagnostic, batch, and job JSON contracts include `schema_version: 1`.
- Configuration, provider-registry, and browser JSON outputs are command-specific and currently unversioned.
- Error payloads use stable `error_code` values where documented.
- Credential-bearing URL components are sanitized in diagnostic payloads.

## Development

```bash
uv sync --extra dev
uv run pytest tests/unit/ -q --tb=short
uv run ruff format --check src/ tests/
uv run ruff check src/ tests/
uv run --extra docs mkdocs build --strict
```

Project layout:

```text
src/gobbler_cli/       Typer CLI
src/gobbler_core/      converters, providers, configuration, utilities
src/gobbler_queue/     SQLite job queue and worker
src/gobbler_relay/     browser-extension HTTP/WebSocket relay
browser-extension/     Chromium extension
skills/                CLI instruction Skills
```

See [CONTRIBUTING.md](CONTRIBUTING.md), [SECURITY.md](SECURITY.md), and the [full documentation](https://enablement-engineering.github.io/gobbler/).

## License

MIT License. See [LICENSE](LICENSE).
