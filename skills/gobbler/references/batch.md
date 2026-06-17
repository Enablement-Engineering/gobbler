# Batch Conversion

Use for YouTube playlists, directories of files, URL lists, bulk conversion, repeated ingestion, or many inputs that should produce many markdown files.

## YouTube playlist

```bash
# Convert all videos in a playlist to markdown transcripts
gobbler batch youtube-playlist "https://youtube.com/playlist?list=PLxxx" -o ./transcripts

# With options
gobbler batch youtube-playlist "https://youtube.com/playlist?list=PLxxx" \
  -o ./transcripts \
  -l en \
  -c 5 \
  --timestamps

# JSON progress/results
gobbler batch youtube-playlist "https://youtube.com/playlist?list=PLxxx" -o ./out --json
```

Useful options:

- `-o, --output PATH`: output directory for transcripts; required.
- `-l, --language TEXT`: preferred transcript language.
- `--timestamps / --no-timestamps`: include timestamps.
- `-c, --concurrency INTEGER`: concurrent conversions.
- `-f, --format TEXT`: `markdown` or `json`.
- `-j, --json`: output progress/results as JSON lines.

## Directory batch

```bash
# Audio files
gobbler batch directory ./recordings -o ./transcripts --pattern "*.mp3"
gobbler batch directory ./recordings -o ./transcripts --pattern "*.wav" --type audio

# Documents
gobbler batch directory ./docs -o ./markdown --pattern "*.pdf"
gobbler batch directory ./docs -o ./markdown --pattern "*.docx" --type document

# Auto-detect file types
gobbler batch directory ./mixed-files -o ./output

# JSON progress/results
gobbler batch directory ./docs -o ./markdown --json
```

Useful options:

- `-o, --output PATH`: output directory; required.
- `-p, --pattern TEXT`: file pattern such as `*.mp3`, `*.pdf`.
- `-c, --concurrency INTEGER`: concurrent conversions.
- `-t, --type TEXT`: `audio` or `document`; auto-detects if omitted.
- `-j, --json`: output progress/results as JSON lines.

## Webpages batch

```bash
# From a file: one URL per line, # comments allowed
gobbler batch webpages urls.txt -o ./output

# From stdin
cat urls.txt | gobbler batch webpages -o ./output

# With selector/timeout/concurrency
gobbler batch webpages urls.txt -o ./output \
  -c 5 \
  -t 60 \
  -s ".article-body"

# Skip already converted URLs
gobbler batch webpages urls.txt -o ./output --skip-existing

# JSON progress/results
gobbler batch webpages urls.txt -o ./output --json
```

Useful options:

- `-o, --output-dir PATH`: output directory; required.
- `-c, --concurrency INTEGER`: concurrent conversions, usually 1-10.
- `-t, --timeout INTEGER`: timeout per page in seconds.
- `-s, --selector TEXT`: CSS selector for targeted extraction.
- `--skip-existing / --no-skip-existing`: skip URLs with existing output.
- `--queue`: queue the batch job instead of running inline.
- `-j, --json`: output progress/results as JSON lines.

## Batch operating rules

- Prefer deterministic filenames.
- Use `--skip-if-exists` or `--skip-existing` for repeatable reruns when available.
- In `--json` mode, parse stdout as newline-delimited JSON. Each event includes `schema_version: 1`; the final `batch_complete` event includes `summary.total`, `summary.successful`, `summary.failed`, and `summary.skipped`.
- Summarize successes/failures instead of pasting every converted document into chat.
- Verify the output directory contains expected markdown files before reporting success.
