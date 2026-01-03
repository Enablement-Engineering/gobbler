# Audio Transcription

Transcribe audio and video files to markdown using Whisper.

**Requires**: ffmpeg installed, Whisper model (auto-downloads on first use)

## Quick Start

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

| Model | Speed | Accuracy | Memory | Use Case |
|-------|-------|----------|--------|----------|
| tiny | ~32x realtime | Lower | ~1GB | Quick drafts |
| base | ~16x realtime | Moderate | ~1GB | General use |
| **small** | ~6x realtime | Good | ~2GB | **Default - recommended** |
| medium | ~2x realtime | Better | ~5GB | Important content |
| large | ~1x realtime | Best | ~10GB | Critical accuracy |

## Supported Formats

### Audio
- MP3, WAV, FLAC, M4A, OGG, AAC

### Video
- MP4, MOV, AVI, MKV, WebM

Audio is extracted automatically from video files.

## Options

| Option | Description | Default |
|--------|-------------|---------|
| `--model` | Whisper model size | `small` |
| `--language` | Audio language (ISO 639-1) | `auto` |
| `--provider` | Transcription provider | `whisper-local` |
| `-o, --output` | Save to file | stdout |

## Choosing a Provider

Gobbler supports multiple transcription providers through its [provider abstraction](../providers.md). Currently available:

| Provider | Description | Best For |
|----------|-------------|----------|
| `whisper-local` | Local transcription using faster-whisper | Privacy, offline use, large volumes |

### whisper-local vs API Providers

**whisper-local (default)**:
- Fully offline - no API keys or internet required
- CoreML acceleration on M-series Macs
- No per-request costs
- Your audio never leaves your machine

**Future API providers** (planned):
- OpenAI Whisper API - no local setup, latest models
- Deepgram - real-time streaming support

### Using --provider Flag

```bash
# Explicit provider selection
gobbler audio recording.mp3 --provider whisper-local

# With model options
gobbler audio recording.mp3 --provider whisper-local --model medium
```

## Alternative Command

```bash
gobbler convert audio /path/to/recording.mp3 --model small -o transcript.md
```

## Tips

- For long recordings, `small` model offers best speed/accuracy tradeoff
- Pre-extract audio from large videos to speed up processing
- Language auto-detection works well for most content
- On Apple Silicon Macs, Whisper uses Metal acceleration

## Performance

On Apple M-series Macs with Metal acceleration:

| Model | Speed vs Realtime |
|-------|-------------------|
| tiny | 32x faster |
| base | 16x faster |
| small | 6x faster |
| medium | 2x faster |
| large | 1x (realtime) |

## Troubleshooting

### "ffmpeg not found"

Install ffmpeg:

```bash
# macOS
brew install ffmpeg

# Ubuntu/Debian
sudo apt-get install ffmpeg

# Windows
# Download from https://ffmpeg.org/download.html
```

### Slow transcription

- Use a smaller model: `--model tiny` or `--model base`
- Pre-extract audio: `ffmpeg -i video.mp4 -vn audio.mp3`
