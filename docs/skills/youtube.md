---
icon: material/youtube
---

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
| `--provider` | Provider to use | `auto` |

## Transcript Providers

Gobbler uses a provider system for YouTube transcripts that handles reliability and IP blocking automatically.

### Available Providers

| Provider | Cost | Reliability | Best For |
|----------|------|-------------|----------|
| `youtube-transcript-api` | Free | May get IP blocked | Light usage, testing |
| `transcriptapi` | ~$0.01/video | High, no IP blocks | Production, heavy usage |
| `auto` | Free + paid fallback | Best of both | **Recommended** |

### How Provider Selection Works

When you run a YouTube transcription, Gobbler selects a provider based on your configuration:

```
┌─────────────────────────────────────────────────────────────┐
│                    Provider Selection                        │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  Is TRANSCRIPTAPI_KEY set?                                   │
│       │                                                      │
│       ├── YES → Use AutoFallbackProvider                     │
│       │         (tries free first, falls back to paid)       │
│       │                                                      │
│       └── NO → Is proxy configured?                          │
│                    │                                         │
│                    ├── YES → Use free API with proxy         │
│                    │                                         │
│                    └── NO → Use free API directly            │
│                             (warns about IP blocking risk)   │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

### Default Behavior (No Configuration)

If you haven't set any environment variables:

1. Gobbler uses the free `youtube-transcript-api` library
2. You'll see a warning about potential IP blocking
3. Works fine for occasional use, but YouTube may block your IP after many requests

### AutoFallbackProvider (Recommended)

When `TRANSCRIPTAPI_KEY` is set, Gobbler uses smart fallback:

1. **First**: Tries the free `youtube-transcript-api`
2. **If blocked**: Automatically retries with the paid TranscriptAPI.com
3. **Result**: Best of both worlds - free when possible, reliable when needed

This means you only pay for transcripts when the free API fails.

## Environment Variables

Configure these in your `~/.zshrc`, `~/.bashrc`, or shell profile:

| Variable | Purpose | Required |
|----------|---------|----------|
| `TRANSCRIPTAPI_KEY` | TranscriptAPI.com API key for paid fallback | No |
| `WEBSHARE_USER` | Webshare.io proxy username | No |
| `WEBSHARE_PASS` | Webshare.io proxy password | No |
| `YOUTUBE_PROXY` | Generic HTTP/SOCKS proxy URL | No |

### Setting Environment Variables

```bash
# Add to ~/.zshrc or ~/.bashrc

# Option 1: Paid API fallback (recommended for reliability)
export TRANSCRIPTAPI_KEY=your_api_key_here

# Option 2: Rotating proxy (keeps free API working)
export WEBSHARE_USER=your_username
export WEBSHARE_PASS=your_password

# Option 3: Custom proxy
export YOUTUBE_PROXY=http://user:pass@proxy.example.com:8080
```

After adding, reload your shell:
```bash
source ~/.zshrc  # or ~/.bashrc
```

## Avoiding IP Blocks

YouTube may block your IP when making many transcript requests. Here are your options:

### Option 1: TranscriptAPI.com (Recommended)

A paid API service that never gets blocked.

**Setup:**

1. Sign up at [transcriptapi.com](https://transcriptapi.com/)
2. Get your API key from [dashboard](https://transcriptapi.com/dashboard/api-keys)
3. Set the environment variable:
   ```bash
   export TRANSCRIPTAPI_KEY=your_api_key
   ```

**Cost:** ~$0.01 per video (with free tier available)

**Benefit:** When combined with auto-fallback, you only pay when the free API fails.

### Option 2: Webshare Rotating Proxy

Uses rotating residential IPs to avoid blocks on the free API.

**Setup:**

1. Sign up at [webshare.io](https://www.webshare.io/)
2. Get credentials from [proxy settings](https://proxy.webshare.io/proxy/rotating)
3. Set environment variables:
   ```bash
   export WEBSHARE_USER=your_username
   export WEBSHARE_PASS=your_password
   ```

**Cost:** ~$3.50/month for residential proxies

### Option 3: Custom Proxy

Use any HTTP or SOCKS proxy you have access to.

**Setup:**

```bash
# HTTP proxy
export YOUTUBE_PROXY=http://user:pass@proxy.example.com:8080

# SOCKS5 proxy
export YOUTUBE_PROXY=socks5://user:pass@proxy.example.com:1080
```

### Proxy Priority

If multiple proxy options are configured, Gobbler uses this priority:

1. **Webshare** (if `WEBSHARE_USER` and `WEBSHARE_PASS` are set)
2. **Generic proxy** (if `YOUTUBE_PROXY` is set)
3. **Direct connection** (no proxy)

## Troubleshooting

### "No transcript available"

- The video may not have captions enabled
- Try specifying a language: `--language en`
- Some videos disable captions entirely
- Live streams may not have transcripts yet

### "IP blocked" or "Too Many Requests" (429)

Your IP has been rate-limited by YouTube. Solutions:

1. **Quick fix**: Wait 15-30 minutes and try again
2. **Permanent fix**: Set up `TRANSCRIPTAPI_KEY` for auto-fallback
3. **Alternative**: Configure a proxy (Webshare or custom)

### "TranscriptAPI error"

- Verify your API key is correct: `echo $TRANSCRIPTAPI_KEY`
- Check your account has credits at [transcriptapi.com/dashboard](https://transcriptapi.com/dashboard)
- Ensure the environment variable is exported (not just set)

### "Proxy connection failed"

- Verify proxy credentials are correct
- Check proxy URL format: `http://user:pass@host:port`
- Ensure the proxy service is active and has available bandwidth

### Checking Your Configuration

Verify your environment variables are set:

```bash
# Check all YouTube-related env vars
env | grep -E "(TRANSCRIPT|WEBSHARE|YOUTUBE_PROXY)"
```

## CLI Examples

```bash
# Basic usage (uses auto provider selection)
gobbler youtube "https://youtube.com/watch?v=dQw4w9WgXcQ"

# With timestamps
gobbler youtube "https://youtube.com/watch?v=dQw4w9WgXcQ" --timestamps

# Force paid API (skip free attempt)
gobbler youtube "https://youtube.com/watch?v=dQw4w9WgXcQ" --provider transcriptapi

# Force free API only (no fallback)
gobbler youtube "https://youtube.com/watch?v=dQw4w9WgXcQ" --provider youtube-transcript-api

# Spanish transcript
gobbler youtube "https://youtube.com/watch?v=dQw4w9WgXcQ" --language es

# Save to file
gobbler youtube "https://youtube.com/watch?v=dQw4w9WgXcQ" -o transcript.md
```

## Alternative Command

```bash
gobbler convert youtube "https://youtube.com/watch?v=VIDEO_ID" -o transcript.md
```

## Language Support

When `--language auto` (default), Gobbler tries to find transcripts in this order:

1. Auto-generated English transcript
2. Manual transcripts in: `en`, `es`, `de`, `fr`, `pt`, `ja`, `ko`, `zh`
3. Any available transcript

Specify a language code to request a specific transcript:

```bash
gobbler youtube "URL" --language es  # Spanish
gobbler youtube "URL" --language de  # German
gobbler youtube "URL" --language ja  # Japanese
```

