---
name: gobbler-setup
description: Installs, configures, and troubleshoots Gobbler. Triggers on install gobbler, setup, not working, connection refused, Docker/service failures, ffmpeg problems, browser relay failures, or diagnostic requests.
metadata:
  openclaw:
    emoji: 🔧
    requires:
      bins: []
    install: []
    homepage: https://github.com/Enablement-Engineering/gobbler
---

# Gobbler setup and troubleshooting

Use this Skill for installation, configuration, dependency checks, Docker services, the SQLite worker, and browser-relay problems.

## Start with diagnostics

```bash
gobbler --version
gobbler doctor --json
gobbler status --json
```

- `doctor --json` is the broad setup report: Python, ffmpeg, Docker, config, and conversion services.
- `status --json` focuses on provider readiness and YouTube fallback/proxy state.
- `status --json` can emit a useful JSON body and exit nonzero when degraded.

Do not assume every degraded service blocks every workflow. YouTube needs no local service; local audio needs ffmpeg; documents need Docling; web pages need Crawl4AI.

## Install

Requirements: Python 3.11+ and uv. ffmpeg is needed for audio/video. Docker is needed for documents/web pages.

```bash
git clone https://github.com/Enablement-Engineering/gobbler.git
cd gobbler
uv sync
uv run gobbler --version
uv run gobbler doctor --json
```

Optional isolated global tool:

```bash
uv tool install .
gobbler --version
```

After pulling updates:

```bash
uv tool install . --force
```

## Docker services

The Compose stack has Docling and Crawl4AI only:

```bash
make start-docker
docker compose ps
gobbler doctor --json
```

Default endpoints:

- Docling: `http://localhost:5001`
- Crawl4AI: `http://localhost:11235`

Inspect failures:

```bash
docker compose logs --tail 100 docling
docker compose logs --tail 100 crawl4ai
```

Do not tell users Redis or RQ is required. The current queue is SQLite-backed.

## Configuration

Path:

```text
~/.config/gobbler/config.yml
```

Commands:

```bash
gobbler config path
gobbler config show --format json
gobbler config init
```

Edit the YAML file directly; the current CLI has no `config set` or `config validate` command. There is no universal environment override system and `GOBBLER_CONFIG` does not select another config file. Current integration variables include:

- `TRANSCRIPTAPI_KEY`
- `WEBSHARE_USER`, `WEBSHARE_PASS`, `YOUTUBE_PROXY`
- `CRAWL4AI_PROXY`
- `OPENAI_API_KEY`
- `CRAWL4AI_API_TOKEN` for Compose, paired with config
- `GOBBLER_MODELS_PATH` for the Docling cache mount

Do not print secrets. `doctor --json` redacts sensitive config values, but inspect any report before publishing it.

## Common recovery paths

### Docker unavailable

```bash
docker info
# macOS/Colima
colima start --cpu 5 --memory 10
make start-docker
```

### Docling disconnect or OCR memory pressure

```bash
gobbler document digital.pdf --no-ocr -o output.md
docker compose logs --tail 100 docling
```

### Crawl4AI unavailable

```bash
docker compose up -d crawl4ai
gobbler doctor --json
gobbler webpage "https://example.com" --no-proxy -o /tmp/example.md
```

### Local audio failure

```bash
ffmpeg -version
gobbler audio recording.mp3 --model tiny -o recording.md
```

Current faster-whisper integration requests CPU execution through CTranslate2. Do not promise Metal, CoreML, or CUDA selection from the CLI.

### YouTube rate limit or IP block

```bash
gobbler status --json
gobbler youtube "URL" --language auto
```

Then wait/retry, configure a proxy, or set `TRANSCRIPTAPI_KEY` for the documented fallback. Never preserve credential-bearing URLs in notes or issue reports.

### Queue worker

```bash
gobbler jobs worker status
gobbler jobs worker start
gobbler jobs list
```

Queueing is explicit, for example:

```bash
gobbler batch webpages urls.txt -o ./pages --queue --json
```

Do not claim `queue.auto_queue_threshold` currently auto-queues commands. `gobbler daemon` is a browser-relay compatibility wrapper, not the job worker.

### Browser extension

```bash
gobbler relay restart
gobbler browser status
gobbler browser list --json
gobbler browser inject
```

Command guards target tabs matching the extension's stored group ID. A different group with the same title does not match, while manually moving a tab into the existing managed group makes it eligible. Origin permissions gate extraction/page-API scripting, but debugger-based `browser exec` only checks group eligibility. Third-party AI chat adapters are DOM-dependent; generic browser success does not prove NotebookLM/Claude/ChatGPT/Gemini selectors remain current.

## Verification before reporting success

Run the smallest real workflow relevant to the user's issue:

```bash
# YouTube
# gobbler youtube "USER_URL" -o /tmp/test.md

# Document
# gobbler document USER_FILE --no-ocr -o /tmp/test.md

# Webpage
# gobbler webpage "https://example.com" --no-proxy -o /tmp/test.md
```

Verify the command exit code and output file. Do not infer readiness from a container being listed alone.

Full reference: <https://enablement-engineering.github.io/gobbler/setup-troubleshooting/>
