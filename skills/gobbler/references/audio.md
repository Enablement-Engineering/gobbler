# Audio and Video Transcription

Use for audio/video files, podcasts, recordings, voice memos, interviews, meetings, lectures, or other spoken content.

## Commands

```bash
# Basic transcription
gobbler audio ./recording.mp3 -o ./outputs/recording.md

# Video files work too; audio is extracted automatically
gobbler audio ./video.mp4 -o ./outputs/video-transcript.md

# Choose model size
gobbler audio ./meeting.m4a --model small -o ./outputs/meeting.md

# Specify language for faster processing
gobbler audio ./meeting.wav --language en -o ./outputs/meeting.md

# Include timestamps
gobbler audio ./interview.mp3 --timestamps -o ./outputs/interview.md

# JSON output
gobbler audio ./recording.mp3 --format json
```

## Requirements

- `ffmpeg` installed and available on PATH.
- Whisper model downloads automatically on first use.
- Run `gobbler doctor --json` if audio fails.

## Useful options

- `--output`, `-o`: output file path.
- `--language`, `-l`: audio language; auto-detect if omitted.
- `--model`, `-m`: `tiny`, `base`, `small`, `medium`, `large`; default `small`.
- `--timestamps`: include timestamps.
- `--format`, `-f`: `markdown`, `json`, or `table`.
- `--provider`, `-p`: transcription provider, usually `whisper-local`.
- `--skip-if-exists`: skip existing output files in repeatable/batch workflows.

## Model guidance

- `tiny`/`base`: fastest, lower accuracy.
- `small`: best default speed/accuracy tradeoff.
- `medium`/`large`: higher quality, slower, more memory.

## Tips

- Specify known language with `--language` to avoid auto-detection overhead.
- Pre-extract audio from very large videos if processing is slow.
- For directories of audio/video files, use `references/batch.md`.
