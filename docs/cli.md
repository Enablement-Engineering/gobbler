---
icon: material/console
---

# CLI usage

The installed command is `gobbler`. When running from a source checkout, prefix examples with `uv run`.

```bash
gobbler --help
gobbler COMMAND --help
gobbler --version
```

Typer's live `--help` output is the authoritative option list for the installed version. This page documents command families, stable patterns, and output behavior.

## Top-level commands

| Command | Current purpose |
| --- | --- |
| `youtube` | Fetch a YouTube transcript |
| `audio` | Transcribe a local audio/video file |
| `document` | Convert a document through Docling |
| `webpage` | Convert a URL through Crawl4AI |
| `batch` | Playlist, directory, and webpage-list batches |
| `status` | Conversion-provider readiness |
| `doctor` | Agent-friendly runtime, dependency, config, and service diagnostics |
| `explain` | Match an error message to known causes and actions |
| `config` | Inspect and edit `~/.config/gobbler/config.yml` |
| `providers` | Inspect the registered provider runtime |
| `jobs` | SQLite job queue and worker management |
| `browser` | Generic browser-extension commands |
| `relay` | Browser relay lifecycle |
| `notebooklm`, `claude`, `chatgpt`, `gemini` | Site-specific browser integrations |
| `daemon` | Compatibility wrapper around the relay; not the job worker |

## Individual conversions

### YouTube

```bash
gobbler youtube "https://youtube.com/watch?v=VIDEO_ID"
gobbler youtube "URL" -o transcript.md --language en --timestamps
gobbler youtube "URL" --format json
gobbler youtube "URL" --clean --timeout 90 -o transcript.md
printf '%s\n' "URL" | gobbler youtube -o transcript.md
```

Important options:

- `-o, --output PATH`: output file; stdout when omitted for transcript mode.
- `-l, --language TEXT`: preferred caption language; default `en`.
- `--timestamps/--no-timestamps`: transcript timestamps.
- `--clean/--no-clean`: merge short caption chunks into flowing paragraphs.
- `-f, --format markdown|json|table`: output representation.
- `-t, --timeout INTEGER`: full conversion timeout; default 120 seconds.
- `--skip-if-exists`: do not replace an existing output file.
- `--open`: open an explicitly written output after success.

A YouTube URL may be passed as an argument, `-`, or omitted and read from stdin.
Provider, fallback, and proxy behavior is configured through `config.yml` and environment variables;
the current `youtube` command has no `--provider` or `--proxy` option.

### Audio/video

```bash
gobbler audio meeting.mp3 -o meeting.md
gobbler audio meeting.mp3 --model medium --language en --timestamps
gobbler audio meeting.mp3 --provider openai-whisper --format json
```

Supported local provider formats include common audio and video containers. ffmpeg is used for media preprocessing. Local model choices are `tiny`, `base`, `small`, `medium`, and `large`.

The reliable CLI default is `whisper-local`. `openai-whisper` requires `OPENAI_API_KEY`.

### Documents

```bash
gobbler document report.pdf -o report.md
gobbler document scan.pdf --ocr -o scan.md
gobbler document digital.pdf --no-ocr --format json
```

Docling must be reachable at the configured service endpoint. OCR is enabled by default; disable it for digital documents when speed or memory matters.

### Web pages

```bash
gobbler webpage "https://example.com" -o page.md
gobbler webpage "https://example.com" --selector "article" --clean
gobbler webpage "https://example.com" --no-images --no-proxy --timeout 60
echo "https://example.com" | gobbler webpage -o page.md
```

A URL may be passed as an argument, `-`, or omitted and read from stdin. Crawl4AI must be reachable. Proxy use is enabled by default only when proxy configuration is present; use `--no-proxy` for an explicit direct request.

## Batch commands

All batch output directories are required. All batch families support `--dry-run`.

### YouTube playlist

```bash
gobbler batch youtube-playlist \
  "https://youtube.com/playlist?list=PLAYLIST_ID" \
  -o ./transcripts --concurrency 3 --dry-run

gobbler batch youtube-playlist "URL" -o ./transcripts --json
```

### Directory

```bash
gobbler batch directory ./recordings -o ./transcripts --pattern "*.mp3"
gobbler batch directory ./documents -o ./markdown --pattern "*.pdf" --type document
gobbler batch directory ./mixed -o ./output --dry-run
```

`--type` accepts `audio` or `document`; omit it for extension-based auto-detection.

### Webpage list

```bash
gobbler batch webpages urls.txt -o ./pages
gobbler batch webpages urls.txt -o ./pages --skip-existing
gobbler batch webpages urls.txt -o ./pages --no-proxy --dry-run
cat urls.txt | gobbler batch webpages -o ./pages
```

Blank lines and lines beginning with `#` are ignored. Webpage batches alone currently expose `--queue`:

```bash
gobbler batch webpages urls.txt -o ./pages --queue --json
gobbler jobs worker start
gobbler jobs list
```

Queueing is opt-in, not automatic.

Although the current help surface accepts `batch webpages --selector`, the batch implementation does not yet forward it to Crawl4AI. Use single-page `gobbler webpage --selector ...` when CSS selection is required.

## Diagnostics

```bash
gobbler doctor --json
gobbler status --json
gobbler status --verbose
gobbler explain "connection refused"
gobbler explain --list --json
```

- `doctor`: broad report including Python, ffmpeg, Docker, config, and conversion services.
- `status`: provider-focused readiness report and actionable fallback information.
- `status --json` may exit nonzero while still writing a valid diagnostic JSON object.
- `explain`: local pattern matching; it does not call an LLM or remote diagnostic service.

## Configuration and providers

```bash
gobbler config path
gobbler config show
gobbler config get services.crawl4ai.port
gobbler config init

gobbler providers list
gobbler providers list --category transcription --format json
gobbler providers info transcription whisper-local
```

`providers list` reports the runtime registry. YouTube's transcript providers use a separate compatibility interface and therefore are not included in the three-category registry listing.

Edit `~/.config/gobbler/config.yml` directly to change values. The current CLI does not expose `config set` or `config validate`.

## Jobs

```bash
gobbler jobs list
gobbler jobs get JOB_ID
gobbler jobs count
gobbler jobs cancel JOB_ID
gobbler jobs clear --status completed
gobbler jobs worker start
gobbler jobs worker status
gobbler jobs worker stop
```

The queue is stored in SQLite. `gobbler daemon` does not run this worker.

## Browser and relay

```bash
gobbler relay start
gobbler browser status
gobbler browser list --json
gobbler browser open "https://example.com"
gobbler browser navigate "https://example.com"
gobbler browser extract --selector article -o page.md
gobbler browser exec "document.title" --json
gobbler browser inject

gobbler relay start
gobbler relay status
gobbler relay stop
```

Most browser operations auto-start the relay unless their top-level `--no-auto-start` option is supplied. `browser status` is the exception: it only reports current state and does not start the relay.

```bash
gobbler browser --no-auto-start list
```

Browser command guards target tabs whose group ID matches the extension's stored `gobblerGroupId`, not every group sharing its visible title. Manually moving a tab into that existing managed group makes it eligible. Origin permissions gate extraction/page-API scripting, but debugger-based `browser exec` only checks group eligibility.

## AI chat integrations

The extension currently provides command groups for NotebookLM, Claude.ai, ChatGPT, and Gemini:

```bash
gobbler notebooklm list
gobbler notebooklm info
gobbler notebooklm query "Summarize the notebook"
gobbler notebooklm last
gobbler notebooklm history

gobbler claude query "Draft a concise answer"
gobbler chatgpt query "Create an image prompt"
gobbler chatgpt download -o ./images
gobbler gemini query "Compare these sources"
gobbler gemini download -o ./images
```

These commands automate third-party web UIs through page scripts. They are beta, DOM-dependent, and require a matching page inside the Gobbler tab group.

## Output and exit contracts

### Normal Markdown

Without `-o`, individual conversion Markdown is written to stdout. With `-o`, the command writes the file and prints status information outside machine-readable JSON modes.

### JSON

- Individual conversions: `--format json`, one JSON object.
- Diagnostics: `--json`, one JSON object.
- Batch work: `--json`, newline-delimited JSON events.
- Queued webpage batch submission: one `job_queued` or `queue_error` object.
- Conversion, diagnostic, batch, and job JSON contracts include `schema_version: 1`.
- Configuration, provider-registry, and browser JSON outputs are currently unversioned and may use command-specific shapes.
- A final `batch_complete` event includes `summary.total`, `successful`, `failed`, and `skipped`.

Conversion, diagnostic, batch, and job JSON modes reserve stdout for machine-readable data. Browser JSON modes do not yet provide that universal guarantee: some browser commands can print relay startup or progress text to stdout before their JSON payload. Treat browser JSON output as command-specific until that implementation is hardened.

### Exit codes

- `0`: successful operation or healthy status.
- `1`: conversion, validation, service, or degraded-status failure.
- `2`: Typer usage error, such as an invalid option or missing required argument.

## Security notes

- Diagnostic URL fields sanitize credential-bearing components.
- Never place API keys directly in documented commands or committed config.
- Browser automation is limited to deliberately grouped tabs but can still read authenticated page content.
- Treat `browser exec` as arbitrary JavaScript execution in the selected tab and use it only with explicit intent.
