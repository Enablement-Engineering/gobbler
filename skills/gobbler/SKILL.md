---
name: gobbler
description: Converts external content into clean structured Markdown, including YouTube videos/playlists, URLs and web pages, PDFs and office documents, audio/video files, local files, batches, and intentionally selected browser tabs. Use when the user asks to convert, extract, transcribe, fetch, download, archive, or save content as Markdown for AI analysis, notes, research, or documentation.
version: 1.0.0
author: Enablement Engineering
license: MIT
metadata:
  agent:
    tags:
      - content-conversion
      - markdown
      - youtube
      - webpage
      - document
      - audio
      - batch
      - research
      - cli-first
    recommended_interface: cli
    requires:
      bins:
        - gobbler
    optional_requires:
      bins:
        - uv
        - docker
        - ffmpeg
  openclaw:
    emoji: 🦃
    requires:
      bins: [gobbler]
    homepage: https://github.com/Enablement-Engineering/gobbler
---

# Gobbler

Use Gobbler when the task begins with external content that must become markdown before an agent can reason over it: YouTube videos/playlists, URLs/webpages, PDFs/DOCX/PPTX/XLSX files, audio/video, batches of inputs, local files, or intentionally selected browser tabs.

Do not use this skill for ordinary summarization when the source content is already present in the conversation.

## Default behavior

- Prefer the `gobbler` CLI over ad hoc converters so outputs are consistent and reproducible.
- Prefer writing converted content to an explicit `.md` output file instead of only printing it in chat.
- Verify that the output file exists, has YAML frontmatter, and has a non-empty markdown body before reporting success.
- Report the source, output path, and command used.
- If processing multiple inputs, use deterministic filenames and summarize successes/failures.
- Run `gobbler doctor --json` before document, webpage, browser, troubleshooting, or large batch workflows.
- Keep private converted content local unless the user explicitly asks to send or publish it.

## Quick routing

| User intent/input | Command family | Details |
| --- | --- | --- |
| YouTube video, playlist, captions, subtitles | `gobbler youtube`, `gobbler batch youtube-playlist` | `references/youtube.md`, `references/batch.md` |
| Audio/video file, podcast, recording, voice memo, interview | `gobbler audio` | `references/audio.md` |
| PDF, DOCX, PPTX, XLSX, document text extraction | `gobbler document` | `references/document.md` |
| URL, webpage, article, web scrape, selector extraction | `gobbler webpage` | `references/webpage.md` |
| Multiple files, URL lists, playlist, bulk conversion | `gobbler batch ...` | `references/batch.md` |
| Authenticated browser tab/session content | `gobbler browser ...` | Load `gobbler-browser` skill |
| Install, service readiness, Docker, ffmpeg, connection refused | `gobbler doctor --json` | Load `gobbler-setup` skill if needed |

## Common commands

```bash
# Check CLI and service readiness
gobbler doctor --json

# YouTube transcript, no Docker required
gobbler youtube "https://youtube.com/watch?v=VIDEO_ID" -o ./outputs/video.md

# Deterministic visual overview, interpreted by the calling agent
gobbler youtube "https://youtube.com/watch?v=VIDEO_ID" \
  --frames-only --frames 8 -o ./outputs/overview.md

# Audio/video transcription
gobbler audio ./meeting.mp3 --model small -o ./outputs/meeting.md

# Document conversion
gobbler document ./paper.pdf --no-ocr -o ./outputs/paper.md

# Webpage conversion
gobbler webpage "https://example.com" -o ./outputs/page.md
```

If working from a source checkout without a global install, use `uv --directory`:

```bash
uv --directory /path/to/gobbler run gobbler doctor --json
uv --directory /path/to/gobbler run gobbler youtube "URL" -o ./outputs/transcript.md
```

## Output verification

After using `-o`, verify the file exists and has frontmatter plus a non-empty body:

```bash
test -s ./outputs/result.md
python - <<'PY'
from pathlib import Path
p = Path('./outputs/result.md')
text = p.read_text()
assert text.startswith('---'), 'missing YAML frontmatter'
assert len(text.split('---', 2)[-1].strip()) > 0, 'empty markdown body'
print('ok')
PY
```

## Safety boundaries

- Ask before browser automation against authenticated/private pages.
- Never extract secrets, cookies, tokens, private keys, unrelated tabs, or unrelated personal content.
- Use `gobbler-browser` for detailed browser/session automation instructions; it has a different safety model from normal conversion.

## Detailed references

Load only the relevant reference when needed:

- `references/youtube.md` — YouTube videos/playlists, captions, languages, timestamps, and deterministic frame refinement.
- `references/audio.md` — audio/video files, Whisper models, ffmpeg, timestamps.
- `references/document.md` — PDFs and office documents, OCR, Docling readiness.
- `references/webpage.md` — URLs/webpages, selector extraction, Crawl4AI readiness.
- `references/batch.md` — playlists, directories, URL lists, JSON progress, skip-existing behavior.
