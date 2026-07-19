# YouTube Conversion

Use for YouTube videos, youtu.be links, captions, subtitles, deterministic frame extraction, and playlists.

## Single video

```bash
# Basic transcription
gobbler youtube "https://youtube.com/watch?v=VIDEO_ID" -o ./outputs/video.md

# Include timestamps
gobbler youtube "https://youtube.com/watch?v=VIDEO_ID" --timestamps -o ./outputs/video.md

# Preferred language
gobbler youtube "https://youtube.com/watch?v=VIDEO_ID" --language es -o ./outputs/video-es.md

# JSON or table output
gobbler youtube "https://youtube.com/watch?v=VIDEO_ID" --format json
gobbler youtube "https://youtube.com/watch?v=VIDEO_ID" -f table
```

## Deterministic frame extraction

Gobbler extracts timestamp-selected JPEGs; it does not interpret images or run an AI model. Frame requests require system `ffmpeg` and durable `--output` or `--frames-dir` storage.

```bash
# Overview without fetching captions
gobbler youtube "URL" --frames-only --frames 8 -o ./outputs/overview.md

# Repeat exact millisecond timestamps
gobbler youtube "URL" --frames-only \
  --frame-at 24:16.500 --frame-at 24:18.200 \
  -o ./outputs/exact.md

# Inclusive range sampling for iterative refinement
gobbler youtube "URL" --frames-only \
  --frame-range 23:41-25:00 --range-frames 6 \
  -o ./outputs/refinement.md
```

### Answering a visually grounded YouTube question

1. Fetch a timestamped transcript.
2. Use transcript content to identify likely intervals.
3. Request four to eight frames across each interval with `--frame-range`.
4. Inspect the returned frame files.
5. Narrow the range or request exact timestamps until the visual fact is clear.
6. Cite both transcript and frame timestamps.

Frame selectors are additive. `--frames-only` never calls transcript providers. This release does not support playlist frames, local-video frames, contact sheets, semantic frame queries, or a persistent video cache.

## Useful options

- `--output`, `-o`: output file path.
- `--language`, `-l`: preferred transcript language, default `en`.
- `--timestamps`: include timestamps.
- `--clean`, `-c`: merge choppy captions into flowing paragraphs.
- `--format`, `-f`: `markdown`, `json`, or `table`.
- `--skip-if-exists`: skip existing output files in repeatable/batch workflows.
- `--frames`: overview midpoint samples, maximum 24.
- `--frame-at`: repeatable exact timestamp.
- `--frame-range`: repeatable inclusive timestamp range.
- `--range-frames`: samples per range, default 6, range 2..24.
- `--frames-only`: skip caption/transcript work.
- `--frames-dir`: explicit durable JPEG directory.

## Supported URL formats

- `https://youtube.com/watch?v=VIDEO_ID`
- `https://youtu.be/VIDEO_ID`
- `https://www.youtube.com/watch?v=VIDEO_ID`

## Notes

- YouTube conversion does not require Docker.
- Output markdown includes YAML frontmatter with video metadata when available.
- Use `--clean` for AI-consumption transcripts unless the user needs raw caption breaks.
- For playlists, use `references/batch.md`.
