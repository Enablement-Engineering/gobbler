---
name: gobbler-audio
description: Transcribes audio and video files to markdown using Whisper. Triggers on .mp3, .wav, .m4a, .mp4, .mov files, or requests to transcribe podcasts, recordings, voice memos, interviews, or spoken content.
---

# Gobbler Audio

Transcribe audio and video files to markdown using Whisper.

**Requires**: ffmpeg installed, Whisper model (auto-downloads on first use)

## Transcribe Audio/Video

```bash
# Basic transcription (outputs to stdout)
gobbler audio /path/to/audio.mp3

# Save to file
gobbler audio /path/to/recording.m4a -o transcript.md

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

## Saving Output

When saving transcripts to a file, follow these steps:

### Step 1: Check for default output directory

```bash
gobbler config get output.default_directory
```

### Step 2: Save to the default directory

If a default directory is configured, use it with a descriptive filename:

```bash
gobbler audio /path/to/recording.m4a -o "<default_directory>/Recording Transcript.md"
```

### Step 3: If no default directory is configured

If the config returns empty/null, save to the current directory or ask the user where to save:

```bash
gobbler audio /path/to/recording.m4a -o "Recording Transcript.md"
```

## Tips

- For long recordings, `small` model offers best speed/accuracy tradeoff
- Pre-extract audio from large videos to speed up processing
- Language auto-detection works well for most content
