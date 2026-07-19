# YouTube transcripts and deterministic frames

`gobbler youtube` can fetch captions, extract deterministic JPEG frames, or do both. Frame extraction is a CLI primitive: Gobbler resolves timestamps and creates artifacts, while the calling human or agent performs any visual interpretation.

## Requirements and durable output

Transcript-only conversion does not require FFmpeg. Any frame selector requires system `ffmpeg` and at least one durable destination:

- `--output/-o` derives `<output-stem>.assets/frames/`.
- `--frames-dir` writes to an explicit directory and can be used when Markdown or JSON is printed to stdout.

For `-o video.md`, the bundle looks like:

```text
video.md
video.assets/
  frames/
    frame-001-00-01-12-500.jpg
```

Markdown links and JSON metadata use paths relative to the output parent whenever possible. An explicitly unrelated absolute `--frames-dir` remains absolute.

## Overview, exact, and range selectors

Selectors are additive and repeatable. Overview frames use bucket midpoints across the full duration, exact timestamps retain millisecond precision, and ranges include both endpoints.

```bash
# Survey the complete video
gobbler youtube "URL" --frames-only --frames 8 -o overview.md

# Extract exact moments
gobbler youtube "URL" --frames-only \
  --frame-at 24:16.500 --frame-at 24:18.200 \
  -o exact.md

# Sample and then narrow an interval
gobbler youtube "URL" --frames-only \
  --frame-range 23:41-25:00 --range-frames 6 \
  -o refinement-1.md
gobbler youtube "URL" --frames-only \
  --frame-range 24:12-24:24 --range-frames 5 \
  -o refinement-2.md

# Append frames to an ordinary timestamped transcript
gobbler youtube "URL" --timestamps --frames 3 -o video.md
```

Timestamps accept bare seconds, `MM:SS[.mmm]`, or `HH:MM:SS[.mmm]`. Duplicate millisecond timestamps are extracted once with provenance precedence `exact`, then `range`, then `overview`. The command permits at most 24 overview frames, 24 frames per range, and 48 resolved frames total.

## Agent coarse-to-fine workflow

1. Fetch a timestamped transcript with `--timestamps`.
2. Use the transcript to identify likely intervals.
3. Request four to eight deterministic frames over each interval with `--frame-range`.
4. Inspect the returned JPEG files.
5. Narrow the range or request exact timestamps until the visual fact is clear.
6. Cite transcript timestamps and frame timestamps in the answer.

`--frames-only` skips transcript-provider construction and caption fetching, which makes repeated refinement independent of caption availability.

## Failure behavior

- Missing FFmpeg fails before transcript work when frames were explicitly requested.
- One failed frame preserves other successful frames and adds a structured warning to metadata and Markdown.
- A failed rerun leaves the previous durable frame bundle intact until the replacement succeeds.
- If every frame fails, the command exits nonzero.
- An expired/403 stream is refreshed once, and only expired timestamps are retried.
- JSON stdout remains a single payload, and transport diagnostics never expose signed stream URLs, cookies, URL userinfo, query values, fragments, or private path tokens.

This release intentionally excludes semantic frame queries, AI/vision processing, contact sheets, playlist frames, local-video frames, and persistent video caching.
