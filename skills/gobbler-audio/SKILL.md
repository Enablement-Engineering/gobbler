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

# Include timestamps in output
gobbler audio /path/to/audio.mp3 --timestamps

# Choose output format (markdown, json, table)
gobbler audio /path/to/audio.mp3 --format json

# Use a different transcription provider
gobbler audio /path/to/audio.mp3 --provider whisper-local

# Save to file
gobbler audio /path/to/recording.m4a -o transcript.md
```

## CLI Options

| Option | Short | Description | Default |
|--------|-------|-------------|---------|
| `--output` | `-o` | Output file path (stdout if not specified) | - |
| `--language` | `-l` | Audio language (auto-detect if not specified) | auto |
| `--model` | `-m` | Whisper model size | small |
| `--timestamps` | - | Include timestamps in output | no-timestamps |
| `--format` | `-f` | Output format (markdown/json/table) | markdown |
| `--provider` | `-p` | Transcription provider | whisper-local |

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

## Tips

- For long recordings, `small` model offers best speed/accuracy tradeoff
- Pre-extract audio from large videos to speed up processing
- Language auto-detection works well for most content
