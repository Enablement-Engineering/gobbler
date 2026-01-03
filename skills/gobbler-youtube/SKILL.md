---
name: gobbler-youtube
description: Transcribe YouTube videos to markdown and download video/audio files. Use when user wants to get transcripts, captions, subtitles from YouTube videos, or download YouTube content as video/audio files.
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
```

Output includes YAML frontmatter with metadata (title, channel, duration, word count).

## Alternative: Using the Convert Subcommand

```bash
gobbler convert youtube "https://youtube.com/watch?v=VIDEO_ID" -o transcript.md
```

## Supported URL Formats

- `https://youtube.com/watch?v=VIDEO_ID`
- `https://youtu.be/VIDEO_ID`
- `https://www.youtube.com/watch?v=VIDEO_ID`


