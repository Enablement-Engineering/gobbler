---
name: gobbler-youtube
description: Transcribe YouTube videos to markdown and download video/audio files. Use when user wants to get transcripts, captions, subtitles from YouTube videos, or download YouTube content as video/audio files.
---

# Gobbler YouTube

Convert YouTube videos to markdown transcripts or download video/audio files.

## Transcribe Video

Extract transcript/captions from a YouTube video:

```bash
uv run scripts/transcribe.py "https://youtube.com/watch?v=VIDEO_ID"

# With timestamps
uv run scripts/transcribe.py "https://youtube.com/watch?v=VIDEO_ID" --timestamps

# Specific language
uv run scripts/transcribe.py "https://youtube.com/watch?v=VIDEO_ID" --language es

# Save to file
uv run scripts/transcribe.py "https://youtube.com/watch?v=VIDEO_ID" --output transcript.md
```

Output includes YAML frontmatter with metadata (title, channel, duration, word count).

## Provider Options

Multiple transcript providers are available:

| Provider | Cost | Reliability | Notes |
|----------|------|-------------|-------|
| `youtube-transcript-api` | Free | May get IP blocked | Default provider |
| `transcriptapi` | ~$0.01/video | High, no IP blocks | Paid API |
| `auto` | Free + fallback | Best of both | Tries free first, falls back to paid |

```bash
# Use TranscriptAPI.com directly (paid, reliable)
uv run scripts/transcribe.py "https://youtube.com/watch?v=VIDEO_ID" \
  --provider transcriptapi --api-key YOUR_KEY

# Auto-fallback: try free first, use paid API if blocked
uv run scripts/transcribe.py "https://youtube.com/watch?v=VIDEO_ID" \
  --provider auto --api-key YOUR_KEY

# Set env var to avoid passing --api-key each time
export TRANSCRIPTAPI_KEY=your_api_key
uv run scripts/transcribe.py "https://youtube.com/watch?v=VIDEO_ID" --provider auto
```

Get TranscriptAPI key at: https://transcriptapi.com/dashboard/api-keys

## Bypassing IP Blocks (Free Provider)

If using the free provider and you get an `IpBlocked` error:

```bash
# Option 1: Use TranscriptAPI.com (recommended)
uv run scripts/transcribe.py "URL" --provider transcriptapi --api-key KEY

# Option 2: Webshare rotating residential proxies (~$4/mo)
uv run scripts/transcribe.py "URL" --webshare-user USER --webshare-pass PASS

# Option 3: Generic HTTP/SOCKS proxy
uv run scripts/transcribe.py "URL" --proxy "http://user:pass@host:port"
```

## Download Video

Download video file from YouTube:

```bash
uv run scripts/download.py "https://youtube.com/watch?v=VIDEO_ID" --output-dir ./downloads

# Specific quality
uv run scripts/download.py "https://youtube.com/watch?v=VIDEO_ID" --quality 720p

# Audio only
uv run scripts/download.py "https://youtube.com/watch?v=VIDEO_ID" --audio-only
```

Quality options: `best`, `1080p`, `720p`, `480p`, `360p`

## Get Metadata

Get video metadata without downloading:

```bash
uv run scripts/get_metadata.py "https://youtube.com/watch?v=VIDEO_ID"
```

Returns JSON with title, channel, duration, description, thumbnail URL.

## Environment Variables

| Variable | Description |
|----------|-------------|
| `TRANSCRIPTAPI_KEY` | API key for TranscriptAPI.com |
| `WEBSHARE_USER` | Webshare proxy username |
| `WEBSHARE_PASS` | Webshare proxy password |
| `YOUTUBE_PROXY` | Generic proxy URL |

## Supported URL Formats

- `https://youtube.com/watch?v=VIDEO_ID`
- `https://youtu.be/VIDEO_ID`
- `https://www.youtube.com/watch?v=VIDEO_ID`
- Bare video ID: `dQw4w9WgXcQ`
