# YouTube Conversion

Use for YouTube videos, youtu.be links, captions, subtitles, and playlists.

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

## Useful options

- `--output`, `-o`: output file path.
- `--language`, `-l`: preferred transcript language, default `en`.
- `--timestamps`: include timestamps.
- `--clean`, `-c`: merge choppy captions into flowing paragraphs.
- `--format`, `-f`: `markdown`, `json`, or `table`.
- `--skip-if-exists`: skip existing output files in repeatable/batch workflows.

## Supported URL formats

- `https://youtube.com/watch?v=VIDEO_ID`
- `https://youtu.be/VIDEO_ID`
- `https://www.youtube.com/watch?v=VIDEO_ID`

## Notes

- YouTube conversion does not require Docker.
- Output markdown includes YAML frontmatter with video metadata when available.
- Use `--clean` for AI-consumption transcripts unless the user needs raw caption breaks.
- For playlists, use `references/batch.md`.
