---
icon: material/robot
---

# Hermes / OpenClaw / Agent Usage

This page is for **Hermes Agent**, **OpenClaw**, and other coding/task agents that need reliable content-to-markdown conversion. Gobbler is meant to be used by agents through the same stable interface humans use: the `gobbler` CLI plus focused markdown Skills.

Hermes, OpenClaw, and similar agents should call CLI commands, save explicit markdown outputs, and verify those files before using them in downstream reasoning.

## Recommended Hermes / OpenClaw / Agent Pattern

1. Load the narrowest Gobbler Skill or workspace instruction for the content type.
2. Run `gobbler` from a checked-out repo or installed tool environment.
3. Save outputs to explicit markdown paths when the result should persist.
4. Verify the output file exists and contains YAML frontmatter plus non-empty markdown.
5. Summarize the converted content or pass the markdown to the next workflow step.

```bash
# YouTube transcript, no Docker required
gobbler youtube "https://youtube.com/watch?v=VIDEO_ID" -o ./outputs/video.md

# Audio transcription, local Whisper
gobbler audio ./meeting.mp3 --model small -o ./outputs/meeting.md

# Document conversion, requires Docling service
gobbler document ./paper.pdf --no-ocr -o ./outputs/paper.md

# Web page conversion, requires Crawl4AI service
gobbler webpage "https://example.com" -o ./outputs/page.md
```

## Hermes Agent Workflow

Hermes should treat Gobbler as a local CLI dependency and use terminal/file tools with explicit verification. The preferred Hermes behavior is:

- Load a relevant Gobbler skill when a user asks to ingest YouTube, audio, documents, webpages, or browser-session content.
- Use `uv --directory /path/to/gobbler run gobbler ...` from a checkout, or plain `gobbler ...` after installation.
- Prefer `-o path.md` for durable outputs so Hermes can read the converted file back with file tools.
- Verify command success and file contents before summarizing or passing the markdown to another task.
- Keep private converted content local unless the user explicitly asks to publish or send it elsewhere.

```bash
# From a local checkout
uv --directory /path/to/gobbler run gobbler --version
uv --directory /path/to/gobbler run gobbler status --json
uv --directory /path/to/gobbler run gobbler youtube "https://youtube.com/watch?v=VIDEO_ID" -o transcript.md
```

For recurring use, install Gobbler once and call `gobbler` directly:

```bash
git clone https://github.com/Enablement-Engineering/gobbler.git
cd gobbler
make install
gobbler --version
```

## OpenClaw Workflow

OpenClaw should use Gobbler through filesystem Skills and the CLI. The `skills/` directory is designed for OpenClaw-style progressive disclosure: lightweight skill metadata is visible up front, and the full task recipe loads only when relevant.

Recommended OpenClaw setup:

```bash
git clone https://github.com/Enablement-Engineering/gobbler.git
cd gobbler
make install

# Symlink or copy Gobbler skills into the OpenClaw skills workspace
cp -R skills/gobbler-* ~/.openclaw/skills/
```

Then OpenClaw can trigger focused skills such as:

- `gobbler-youtube` for YouTube transcript and download workflows.
- `gobbler-audio` for audio/video transcription.
- `gobbler-document` for PDF, DOCX, PPTX, and XLSX conversion.
- `gobbler-webpage` for web page extraction.
- `gobbler-browser` for browser-extension workflows.
- `gobbler-setup` for installation and troubleshooting.

Skills are intentionally thin wrappers around the CLI. That keeps Hermes, OpenClaw, and other agent behavior auditable and makes failures easy to reproduce outside the agent.

## Service Readiness

Some commands work without Docker; others require local services.

| Command family | Requirement | Verify |
| --- | --- | --- |
| `gobbler youtube` | none | `gobbler youtube URL` |
| `gobbler audio` | ffmpeg, local model download | `gobbler audio FILE --model tiny` |
| `gobbler document` | Docling service | `make start-docker && gobbler status --json` |
| `gobbler webpage` | Crawl4AI service | `make start-docker && gobbler status --json` |
| `gobbler browser` | browser extension and relay | `gobbler browser status` |

## Verification Checklist for Hermes / OpenClaw / Agents

After every conversion, check:

- The command exited successfully.
- The output file exists when `-o` was used.
- The file starts with `---` YAML frontmatter.
- The content body is non-empty.
- The source URL/path is present in frontmatter.

Example:

```bash
test -s ./outputs/video.md
python - <<'PY'
from pathlib import Path
p = Path('./outputs/video.md')
text = p.read_text()
assert text.startswith('---'), 'missing YAML frontmatter'
assert len(text.split('---', 2)[-1].strip()) > 0, 'empty markdown body'
print('ok')
PY
```

## Why not MCP?

Gobbler previously carried an MCP server surface. For Hermes, OpenClaw, and similar agents, that duplicated the CLI, increased dependency churn, and made failures harder to reproduce. The supported agent contract is now CLI-first plus Skills: simpler for users, easier for agents to verify, and more maintainable for the project.
