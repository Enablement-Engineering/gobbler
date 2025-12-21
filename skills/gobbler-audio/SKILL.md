---
name: gobbler-audio
description: Transcribe audio and video files to markdown using Whisper. Use when user wants to transcribe audio files, video files, podcasts, recordings, or any spoken content to text.
version: 1.0.0
---

# Gobbler Audio

Transcribe audio and video files to markdown using faster-whisper with Metal/CoreML acceleration on M-series Macs.

**Requires**: ffmpeg installed, faster-whisper Python package

## Transcribe Audio/Video

```bash
uv run scripts/transcribe.py /path/to/audio.mp3

# Choose model size (tiny, base, small, medium, large)
uv run scripts/transcribe.py /path/to/video.mp4 --model medium

# Specify language (auto-detect by default)
uv run scripts/transcribe.py /path/to/audio.wav --language en

# Save to file
uv run scripts/transcribe.py /path/to/recording.m4a --output transcript.md
```

## Extract Audio from Video

For large video files, extract audio first to reduce processing time:

```bash
uv run scripts/extract_audio.py /path/to/video.mp4

# Save to specific location
uv run scripts/extract_audio.py /path/to/video.mov --output extracted.mp3
```

## Supported Formats

- **Audio**: mp3, wav, flac, m4a, ogg
- **Video**: mp4, mov, avi, mkv, webm

## Model Sizes

| Model | Speed | Accuracy | VRAM |
|-------|-------|----------|------|
| tiny | Fastest | Lower | ~1GB |
| base | Fast | Moderate | ~1GB |
| small | Moderate | Good | ~2GB |
| medium | Slower | Better | ~5GB |
| large | Slowest | Best | ~10GB |
