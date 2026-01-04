---
name: gobbler-youtube
description: Transcribes YouTube videos to markdown. Triggers on youtube, video transcript, youtu.be links, youtube.com links, or requests for captions/subtitles from videos.
---

# Gobbler YouTube

Convert YouTube videos to markdown transcripts.

## Transcribe Video

```bash
# Basic transcription (outputs to stdout)
gobbler youtube "https://youtube.com/watch?v=VIDEO_ID"

# Save to file
gobbler youtube "https://youtube.com/watch?v=VIDEO_ID" -o transcript.md

# With timestamps
gobbler youtube "https://youtube.com/watch?v=VIDEO_ID" --timestamps

# Specific language
gobbler youtube "https://youtube.com/watch?v=VIDEO_ID" --language es

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

## Saving Output

When saving transcripts to a file, follow these steps:

### Step 1: Check for default output directory

```bash
gobbler config get output.default_directory
```

### Step 2: Save to the default directory

If a default directory is configured, use it with a descriptive filename:

```bash
gobbler youtube "URL" -o "<default_directory>/Video Title.md"
```

### Step 3: If no default directory is configured

If the config returns empty/null, save to the current directory or ask the user where to save:

```bash
gobbler youtube "URL" -o "Video Title.md"
```

## Alternative: Using the Convert Subcommand

```bash
gobbler convert youtube "https://youtube.com/watch?v=VIDEO_ID" -o transcript.md
```

## Supported URL Formats

- `https://youtube.com/watch?v=VIDEO_ID`
- `https://youtu.be/VIDEO_ID`
- `https://www.youtube.com/watch?v=VIDEO_ID`
