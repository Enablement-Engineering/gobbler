---
icon: material/wrench
---

# Setup and troubleshooting

Start with machine-readable diagnostics instead of guessing from a single port:

```bash
gobbler doctor --json
gobbler status --json
```

## What the diagnostics mean

- `doctor`: CLI version, Python executable, ffmpeg, Docker CLI/daemon, effective config, and conversion-service probes.
- `status`: configured conversion providers, service URLs, proxy/fallback readiness, and Crawl4AI conversion readiness.
- `status --json` can emit valid JSON and exit nonzero when overall status is degraded.

YouTube and local audio can work while document/webpage services are degraded.

## Installation check

```bash
python3 --version
uv --version
ffmpeg -version
docker version

gobbler --version
# From a checkout if no global tool is installed:
uv run gobbler --version
```

For a source checkout:

```bash
uv sync
uv run gobbler doctor --json
```

For an isolated global tool:

```bash
uv tool install . --force
gobbler --version
```

## Document or webpage service unavailable

```bash
make start-docker
docker compose ps
gobbler doctor --json
```

Inspect logs:

```bash
docker compose logs --tail 100 docling
docker compose logs --tail 100 crawl4ai
```

Default endpoints:

```bash
curl -fsS http://localhost:5001/health
curl -fsS http://localhost:11235/health
```

A successful health endpoint does not prove Crawl4AI can complete a conversion; `gobbler doctor --json` includes a real conversion probe.

### Docker daemon unavailable

Start Docker Desktop, Colima, or Docker Engine first:

```bash
# Colima
colima start --cpu 5 --memory 10

# Linux service
sudo systemctl start docker

docker info
```

### Docling disconnects or runs out of memory

Use less expensive document settings first:

```bash
gobbler document digital.pdf --no-ocr -o output.md
```

The repository Compose file currently reserves up to 8 GB and 4 CPUs for Docling. Increase the Docker runtime's overall allocation if the container is killed despite those limits.

### Crawl4AI token mismatch

The Compose default token is `gobbler-local-token`. If `CRAWL4AI_API_TOKEN` changes the container token, set the same value in `services.crawl4ai.api_token`:

```yaml
services:
  crawl4ai:
    host: localhost
    port: 11235
    api_token: your-token
```

## Audio problems

```bash
ffmpeg -version
gobbler audio recording.mp3 --model tiny -o recording.md
```

The first local Whisper run downloads a model. Current local inference uses faster-whisper/CTranslate2 with `device="cpu"`; there is no CLI `--device` option.

Common causes:

- ffmpeg missing.
- Unsupported extension.
- Model download blocked or disk full.
- Silent/corrupt media.
- A model too large for available memory.

For OpenAI transcription:

```bash
export OPENAI_API_KEY="..."
gobbler audio recording.mp3 --provider openai-whisper -o recording.md
```

## YouTube transcript problems

```bash
gobbler youtube "URL" --language auto
gobbler status --json
```

Possible causes include missing captions, a private/age-restricted video, IP-based rate limiting, or malformed input.

When YouTube blocks direct transcript traffic:

1. Wait and retry.
2. Try another video or caption language.
3. Configure `WEBSHARE_USER`/`WEBSHARE_PASS` or `YOUTUBE_PROXY`.
4. Configure `TRANSCRIPTAPI_KEY` for the documented paid fallback.

Diagnostics sanitize credential-bearing URL components; do not paste live credential URLs into issue reports.

## Queue and worker problems

The current queue is SQLite-backed. Redis/RQ is not part of the active runtime.

```bash
gobbler jobs worker status
gobbler jobs list
gobbler jobs count
```

Start the worker:

```bash
gobbler jobs worker start
```

Submit work explicitly:

```bash
gobbler batch webpages urls.txt -o ./pages --queue --json
```

There is no automatic queue threshold in current command execution. `gobbler daemon` manages the browser relay compatibility surface, not the job worker.

## Browser extension and relay

```bash
gobbler relay status
gobbler browser status
gobbler browser list
```

If disconnected:

1. Confirm the unpacked extension is enabled.
2. Confirm the target tab was added with **Allow & Add** or **Add Tab** in the extension popup.
3. Restart the relay:

```bash
gobbler relay restart
gobbler browser status
```

Most browser operations normally auto-start the relay. `gobbler browser status` is intentionally read-only and only reports current state.

Third-party AI chat commands depend on changing site DOMs. If generic browser commands work but `notebooklm`, `claude`, `chatgpt`, or `gemini` commands fail, inspect extension errors and the page console, then verify the relevant page API still matches the live site.

## Configuration problems

```bash
gobbler config path
gobbler config show --format json
```

The path is `~/.config/gobbler/config.yml`. `GOBBLER_CONFIG` is not currently an alternate-path mechanism. Configuration is loaded per process; restart workers and relays after changing values they use.

The current CLI has no `config validate` command. `config show` confirms what the loader accepted, but it is not a strict nested schema validator.

## JSON troubleshooting

Capture stdout and the exit code separately:

```bash
set +e
gobbler status --json > status.json
code=$?
set -e
python -m json.tool status.json
echo "exit=$code"
```

For batches, parse each stdout line as a JSON event. The final `batch_complete` event contains the summary.

## Safe reset procedures

Restart services without deleting data or caches:

```bash
docker compose down
docker compose up -d
gobbler doctor --json
```

Do not use `docker compose down -v` unless you intentionally want to remove Compose volumes. Do not delete `~/.local/share/gobbler/jobs.db` unless queued-job history can be discarded.

## Report a bug

Include:

- `gobbler --version`
- Sanitized `gobbler doctor --json`
- The exact command and exit code
- The relevant Docker or relay log excerpt
- Operating system, Python version, and Docker runtime

Remove API keys, proxy credentials, private URLs, cookies, and converted private content before posting.

Issues: <https://github.com/Enablement-Engineering/gobbler/issues>
