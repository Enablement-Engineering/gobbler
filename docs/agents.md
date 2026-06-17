---
icon: material/robot
---

# Agent Usage: Hermes, OpenClaw, and CLI-First Automation

Gobbler is designed to be easy for AI agents to use without requiring a custom server integration. The stable contract is the `gobbler` CLI: agents can run the same commands, inspect the same files, and verify the same outputs as humans.

## Recommended Agent Pattern

1. Use a Gobbler Skill or workspace instruction to select the right command.
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

## Hermes Workflow

Hermes agents should treat Gobbler as a local CLI dependency and use shell commands with explicit verification.

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

## OpenClaw and Skill-Based Agents

The `skills/` directory contains focused instructions for each content type. Agents should load the narrowest matching skill:

- `gobbler-youtube` for YouTube transcript and download workflows.
- `gobbler-audio` for audio/video transcription.
- `gobbler-document` for PDF, DOCX, PPTX, and XLSX conversion.
- `gobbler-webpage` for web page extraction.
- `gobbler-browser` for browser-extension workflows.
- `gobbler-setup` for installation and troubleshooting.

Skills are intentionally thin wrappers around the CLI. That keeps agent behavior auditable and makes failures easy to reproduce outside the agent.

## Service Readiness

Some commands work without Docker; others require local services.

| Command family | Requirement | Verify |
| --- | --- | --- |
| `gobbler youtube` | none | `gobbler youtube URL` |
| `gobbler audio` | ffmpeg, local model download | `gobbler audio FILE --model tiny` |
| `gobbler document` | Docling service | `make start-docker && gobbler status --json` |
| `gobbler webpage` | Crawl4AI service | `make start-docker && gobbler status --json` |
| `gobbler browser` | browser extension and relay | `gobbler browser status` |

## Verification Checklist for Agents

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

## Why CLI-First?

Gobbler previously carried an MCP server surface. That integration duplicated the CLI, increased dependency churn, and made tests more fragile. As of v0.2.0, the supported contract is CLI-first plus Skills. This is simpler for users, easier for agents to verify, and more maintainable for the project.
