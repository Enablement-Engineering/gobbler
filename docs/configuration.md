---
icon: material/cog
---

# Configuration

## File location and commands

Gobbler reads one user config file:

```text
~/.config/gobbler/config.yml
```

Use the CLI to discover and manage it:

```bash
gobbler config path
gobbler config show
gobbler config show --format json
gobbler config init
gobbler config get services.docling.port
```

`config init` refuses to overwrite an existing file unless `--force` is supplied. Edit the YAML file directly to change values; the current CLI has no `config set` or `config validate` subcommand.

The user file is recursively merged over built-in defaults. A missing file is valid and uses defaults.

## Precedence

For behavior that a command exposes directly, the practical order is:

1. CLI option.
2. Relevant config-file value.
3. Integration-specific environment variable.
4. Built-in default.

Gobbler does **not** implement a universal `GOBBLER_*` environment-variable override layer, and it does not currently support selecting an alternate config path with `GOBBLER_CONFIG`. Environment variables listed below are read by specific providers or Docker Compose.

## Recommended minimal config

```yaml
services:
  crawl4ai:
    host: localhost
    port: 11235
    api_token: gobbler-local-token
  docling:
    host: localhost
    port: 5001

whisper:
  model: small
  language: auto

crawl4ai:
  timeout: 30
  max_timeout: 120

docling:
  ocr: true
  vlm: false

providers:
  youtube:
    default: youtube-transcript-api
    youtube-transcript-api: {}
    transcriptapi: {}
  transcription:
    # Compatibility/schema metadata; the no-flag CLI currently selects whisper-local.
    default: whisper-local
    whisper-local:
      model: small
  document:
    # Compatibility/schema metadata; the no-flag CLI currently selects docling.
    default: docling
    docling:
      ocr: true
  webpage:
    # Compatibility/schema metadata; the no-flag CLI currently selects crawl4ai.
    default: crawl4ai
    crawl4ai:
      timeout: 30

proxy_services: {}

output:
  default_format: frontmatter
  timestamp_format: iso8601
  default_directory: null
```

The authoritative commented example is [`config/config.example.yml`](https://github.com/Enablement-Engineering/gobbler/blob/main/config/config.example.yml). Run `gobbler config show` to inspect the effective configuration for the installed version.

## Service endpoints

```yaml
services:
  crawl4ai:
    host: localhost
    port: 11235
    api_token: gobbler-local-token
  docling:
    host: localhost
    port: 5001
```

These values are consumed when the default Docling and Crawl4AI providers are created. If you change the Compose token, update both `CRAWL4AI_API_TOKEN` for the container and `services.crawl4ai.api_token` for the CLI.

## YouTube transcripts and fallback

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

Set `TRANSCRIPTAPI_KEY` to make the paid fallback ready:

```bash
export TRANSCRIPTAPI_KEY="..."
gobbler status --json
```

Without the key, direct `youtube-transcript-api` conversion still works when YouTube allows the request. `status --json` reports fallback readiness separately.

### YouTube proxy

Reusable proxy services support `${VAR_NAME}` substitution in proxy fields:

```yaml
proxy_services:
  webshare:
    type: rotating
    username: ${WEBSHARE_USER}
    password: ${WEBSHARE_PASS}

providers:
  youtube:
    youtube-transcript-api:
      proxy: webshare
```

Or use environment-only proxy settings:

```bash
export WEBSHARE_USER="..."
export WEBSHARE_PASS="..."
# alternatively: export YOUTUBE_PROXY="http://user:pass@host:port"
```

Do not commit proxy credentials or API keys.

## Audio transcription

The current `gobbler audio` command defaults to `whisper-local`; `--model` and `--language` are the reliable per-command controls:

```bash
gobbler audio meeting.mp3 --model medium --language en -o meeting.md
gobbler audio meeting.mp3 --provider openai-whisper -o meeting.md
```

`openai-whisper` reads `OPENAI_API_KEY`. The `providers.transcription.default` key is part of the provider schema, but the CLI's no-flag audio path currently instantiates local Whisper directly. Do not rely on changing that key to switch the CLI default; use `--provider`.

## Webpage proxy

`gobbler webpage` uses configured proxy settings by default and supports `--no-proxy` for a direct request.

```bash
export CRAWL4AI_PROXY="http://user:pass@proxy.example:8080"
gobbler webpage "https://example.com"
gobbler webpage "https://example.com" --no-proxy
```

A configured `providers.webpage.crawl4ai.proxy` may also reference an entry under `proxy_services`.

## Output behavior

Individual conversion commands write Markdown to stdout unless `-o/--output` is supplied. `--format json` emits a JSON object. Explicit command flags control the current output destination and format.

Some keys under `output`, `queue`, `redis`, and `monitoring` remain in the compatibility schema but are not a universal runtime-control surface. In particular:

- `output.default_directory` does not replace an omitted `-o` on current conversion commands.
- `queue.auto_queue_threshold` does not automatically queue long commands.
- The current job queue is SQLite-backed; Redis settings are not used by it.
- Monitoring keys do not start a metrics server by themselves.

These compatibility keys are retained to avoid breaking existing files. Prefer documented CLI flags and runtime commands.

## Job queue

Queue submission is explicit:

```bash
gobbler batch webpages urls.txt -o ./pages --queue --json
gobbler jobs worker start
gobbler jobs list
```

The job database defaults to `~/.local/share/gobbler/jobs.db`. Worker lifecycle is controlled through `gobbler jobs worker`, not through Redis or RQ.

## Environment variables actually read

| Variable | Consumer | Purpose |
| --- | --- | --- |
| `TRANSCRIPTAPI_KEY` | YouTube provider | TranscriptAPI fallback key |
| `WEBSHARE_USER`, `WEBSHARE_PASS` | YouTube proxy helper | Webshare credentials |
| `YOUTUBE_PROXY` | YouTube proxy helper | Explicit proxy URL |
| `CRAWL4AI_PROXY` | Webpage provider | Explicit Crawl4AI proxy URL |
| `OPENAI_API_KEY` | `openai-whisper` | OpenAI transcription API key |
| `CRAWL4AI_API_TOKEN` | Docker Compose | Container token; manually mirror it to `services.crawl4ai.api_token` for the client |
| `GOBBLER_MODELS_PATH` | Docker Compose | Host Docling model-cache path |

## Inspection and diagnostics

```bash
gobbler config show --format json
gobbler doctor --json
gobbler status --json
```

`config show` confirms what the current loader accepted and displays the deep-merged effective values. It is not a strict schema/type validator for every nested key. Configuration is loaded per process; restart long-running workers or relays after changing values they consume.
