---
name: gobbler-youtube
description: Transcribe YouTube videos to markdown. Use when user wants to get transcripts, captions, or subtitles from YouTube videos.
version: 2.0.0
---

# Gobbler YouTube

Convert YouTube videos to markdown transcripts.

## Transcribe Video

```bash
# Basic transcription
gobbler youtube "https://youtube.com/watch?v=VIDEO_ID"

# With timestamps
gobbler youtube "https://youtube.com/watch?v=VIDEO_ID" --timestamps

# Specific language
gobbler youtube "https://youtube.com/watch?v=VIDEO_ID" --language es

# Save to file
gobbler youtube "https://youtube.com/watch?v=VIDEO_ID" -o transcript.md

# Output as JSON
gobbler youtube "https://youtube.com/watch?v=VIDEO_ID" --format json

# Output as table
gobbler youtube "https://youtube.com/watch?v=VIDEO_ID" -f table
```

## CLI Options

| Option | Short | Description | Default |
|--------|-------|-------------|---------|
| `--output` | `-o` | Output file path (stdout if not specified) | - |
| `--language` | `-l` | Preferred transcript language | `en` |
| `--timestamps` | - | Include timestamps in output | `--no-timestamps` |
| `--format` | `-f` | Output format: `markdown`, `json`, `table` | `markdown` |

Output includes YAML frontmatter with metadata (title, channel, duration, word count).

## Alternative: Using the Convert Subcommand

```bash
gobbler convert youtube "https://youtube.com/watch?v=VIDEO_ID" -o transcript.md
```

## Supported URL Formats

- `https://youtube.com/watch?v=VIDEO_ID`
- `https://youtu.be/VIDEO_ID`
- `https://www.youtube.com/watch?v=VIDEO_ID`
