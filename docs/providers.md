---
icon: material/swap-horizontal
---

# Providers

Gobbler has two provider mechanisms:

1. A runtime registry for transcription, document, and webpage conversion.
2. A separate YouTube transcript provider interface retained for compatibility and fallback handling.

Inspect the installed runtime:

```bash
gobbler providers list --format json
gobbler providers info transcription whisper-local
gobbler status --json
```

## Registered conversion providers

The current registry contains:

| Category | Provider | Backend |
| --- | --- | --- |
| `transcription` | `whisper-local` | local faster-whisper/CTranslate2 |
| `transcription` | `openai-whisper` | OpenAI audio transcription API |
| `document` | `docling` | local/configured Docling HTTP service |
| `webpage` | `crawl4ai` | local/configured Crawl4AI HTTP service |

YouTube providers do not appear in `gobbler providers list` because they implement a separate transcript-specific interface.

## Local Whisper

```bash
gobbler audio recording.mp3 --provider whisper-local --model small -o recording.md
```

- No API key.
- Uses `faster-whisper` with CTranslate2.
- Current implementation requests `device="cpu"` and `compute_type="auto"`.
- Models: `tiny`, `base`, `small`, `medium`, `large`.
- Models are downloaded on first use and cached by the underlying libraries.
- ffmpeg is used to extract or compress audio when preprocessing is needed.

Gobbler does not currently select CUDA or Apple's Metal/CoreML through a CLI device option. Performance depends on the CTranslate2 build and host CPU.

## OpenAI Whisper

```bash
export OPENAI_API_KEY="..."
gobbler audio recording.mp3 --provider openai-whisper -o recording.md
```

- Reads `OPENAI_API_KEY` when no key is passed programmatically.
- Uses the `whisper-1` model.
- Supports automatic language detection or a language supplied with `--language`.
- Files over the API's 25 MB limit are preprocessed with ffmpeg; conversion fails if the compressed result remains too large.

The CLI still passes its `--model` value when explicitly constructing a transcription provider. `openai-whisper` ignores local model names and uses `whisper-1`.

## Docling

```bash
make start-docker
gobbler document report.pdf --provider docling --no-ocr -o report.md
```

The default provider reads `services.docling.host` and `services.docling.port` from the effective config. Defaults:

```yaml
services:
  docling:
    host: localhost
    port: 5001
```

Supported inputs include PDF, DOCX, PPTX, and XLSX. OCR is a per-command option and is enabled by default.

## Crawl4AI

```bash
make start-docker
gobbler webpage "https://example.com" --provider crawl4ai --no-proxy -o page.md
```

The default provider reads its endpoint and token from:

```yaml
services:
  crawl4ai:
    host: localhost
    port: 11235
    api_token: gobbler-local-token
```

The client sends Crawl4AI-compatible crawl requests and normalizes supported response shapes. `gobbler doctor --json` performs both a health check and a conversion probe, which is more useful than checking only whether the port is open.

Webpage proxy selection can come from `CRAWL4AI_PROXY` or a configured proxy service. Use `--no-proxy` to force a direct request.

## YouTube transcript providers

### `youtube-transcript-api`

The default free provider requests YouTube captions directly. It requires no local service or API key, but YouTube can rate-limit or block a host.

This is the no-flag provider selected by the default configuration.

### `transcriptapi`

The paid fallback reads `TRANSCRIPTAPI_KEY`:

```bash
export TRANSCRIPTAPI_KEY="..."
gobbler youtube "URL"
```

A typical fallback configuration is:

```yaml
providers:
  youtube:
    default: youtube-transcript-api
    youtube-transcript-api:
      fallback:
        provider: transcriptapi
        on: [ip_blocked, rate_limited]
    transcriptapi: {}
```

`gobbler status --json` reports whether the fallback is configured and whether the required key is visible.

## Provider selection behavior

```bash
gobbler audio file.mp3 --provider whisper-local
gobbler audio file.mp3 --provider openai-whisper
gobbler document file.pdf --provider docling
gobbler webpage "https://example.com" --provider crawl4ai
```

The `providers.*.default` config keys describe the provider schema, but current CLI behavior is not uniform:

- Document and webpage no-flag paths currently select Docling and Crawl4AI respectively and read `services.*` endpoint settings. They do not consult `providers.document.default` or `providers.webpage.default`.
- Audio's no-flag path currently uses local Whisper directly. Use `--provider openai-whisper` rather than relying on `providers.transcription.default`.
- YouTube has its own configured default and fallback implementation. The current YouTube CLI does not expose `--provider`; change `providers.youtube.default` or configure fallback instead.

This distinction is intentional documentation of current behavior, not a promise that all categories are configured identically.

## Fallback conditions

The generic provider package defines these condition names:

- `error`
- `timeout`
- `rate_limited`
- `ip_blocked`
- `unavailable`

The user-visible automatic fallback path currently matters most for YouTube transcript retrieval. Do not assume every registry provider automatically consults a fallback config merely because the schema accepts one.

## Proxy services

```yaml
proxy_services:
  webshare:
    type: rotating
    username: ${WEBSHARE_USER}
    password: ${WEBSHARE_PASS}
  datacenter:
    type: static
    url: ${PROXY_URL}
```

Provider entries may reference a named proxy where supported. Environment substitution is applied to proxy fields. Keep credentials in the environment and never commit them.

## Diagnosing provider failures

```bash
gobbler providers list --format json
gobbler status --json
gobbler doctor --json
gobbler explain "connection refused" --json
```

- Unknown provider: compare the requested name to `providers list`.
- Docling/Crawl4AI connection failure: start Compose and inspect `docker compose ps` and logs.
- Local Whisper failure: verify ffmpeg, supported file extension, disk space, and model download access.
- OpenAI failure: verify `OPENAI_API_KEY`, file size, and network access.
- YouTube IP block: wait, use a configured proxy, or configure TranscriptAPI fallback.
