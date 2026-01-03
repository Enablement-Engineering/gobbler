# YouTube Transcription

Convert YouTube videos to markdown transcripts.

## Quick Start

```bash
# Basic transcription
gobbler youtube "https://youtube.com/watch?v=VIDEO_ID"

# With timestamps
gobbler youtube "https://youtube.com/watch?v=VIDEO_ID" --timestamps

# Specific language
gobbler youtube "https://youtube.com/watch?v=VIDEO_ID" --language es

# Save to file
gobbler youtube "https://youtube.com/watch?v=VIDEO_ID" -o transcript.md
```

## Supported URL Formats

- `https://youtube.com/watch?v=VIDEO_ID`
- `https://youtu.be/VIDEO_ID`
- `https://www.youtube.com/watch?v=VIDEO_ID`

## Output Format

Output includes YAML frontmatter with metadata:

```markdown
---
source: https://youtube.com/watch?v=VIDEO_ID
type: youtube_transcript
title: "Video Title"
channel: "Channel Name"
duration: 847
word_count: 2341
converted_at: 2026-01-03T10:30:00Z
---

# Video Title

Transcript content here...
```

## Options

| Option | Description | Default |
|--------|-------------|---------|
| `--timestamps` | Include timestamp markers | `false` |
| `--language` | Transcript language (ISO 639-1) | `auto` |
| `-o, --output` | Save to file | stdout |

## Alternative Command

```bash
gobbler convert youtube "https://youtube.com/watch?v=VIDEO_ID" -o transcript.md
```

## Troubleshooting

### "No transcript available"

- The video may not have captions
- Try a different language: `--language en`
- Some videos disable captions

### "IP blocked" or rate limited

Use TranscriptAPI.com for reliable access:

```bash
export TRANSCRIPTAPI_KEY=your_key
gobbler youtube "URL"
```
