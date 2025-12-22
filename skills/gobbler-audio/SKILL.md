---
name: gobbler-audio
description: Transcribe audio and video files to markdown using Whisper. Use when user wants to transcribe audio files, video files, podcasts, recordings, or any spoken content to text.
version: 2.0.0
---

# Gobbler Audio

Transcribe audio and video files to markdown using Whisper.

**Requires**: ffmpeg installed, Whisper model (auto-downloads on first use)

## Transcribe Audio/Video

```bash
# Basic transcription
gobbler audio /path/to/audio.mp3

# Choose model size (tiny, base, small, medium, large)
gobbler audio /path/to/video.mp4 --model medium

# Specify language (auto-detect by default)
gobbler audio /path/to/audio.wav --language en

# Save to file
gobbler audio /path/to/recording.m4a -o transcript.md
```

## Model Sizes

| Model | Speed | Accuracy | Memory |
|-------|-------|----------|--------|
| tiny | Fastest | Lower | ~1GB |
| base | Fast | Moderate | ~1GB |
| small | Moderate | Good (default) | ~2GB |
| medium | Slower | Better | ~5GB |
| large | Slowest | Best | ~10GB |

## Supported Formats

- **Audio**: mp3, wav, flac, m4a, ogg, aac
- **Video**: mp4, mov, avi, mkv, webm (audio extracted automatically)

## Alternative: Using the Convert Subcommand

```bash
gobbler convert audio /path/to/recording.mp3 --model small -o transcript.md
```

## Python SDK

```python
from gobbler_sdk import GobblerClient

client = GobblerClient()

# Transcribe audio
result = client.convert.audio(
    "/path/to/audio.mp3",
    model="small",
    language="en"
)
print(result.markdown)
print(result.metadata)  # duration, word_count, etc.
```

## REST API

```bash
curl -X POST http://localhost:4600/convert/audio \
  -H "Content-Type: application/json" \
  -d '{
    "file_path": "/path/to/audio.mp3",
    "model": "small",
    "language": "en"
  }'
```

## Tips

- For long recordings, `small` model offers best speed/accuracy tradeoff
- Pre-extract audio from large videos to speed up processing
- Language auto-detection works well for most content
