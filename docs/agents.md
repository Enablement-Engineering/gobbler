---
icon: material/robot
---

# Agent Usage

Gobbler is designed for **CLI-capable AI agents**: agents that can read skill files, run shell commands, and inspect output files. The stable contract is simple: run the same `gobbler` CLI commands a human would run, save outputs to explicit markdown files, then verify those files before using them in downstream reasoning.

## Recommended agent pattern

1. Load `gobbler` for conversion, `gobbler-browser` for browser/session automation, or `gobbler-setup` for installation/troubleshooting.
2. Run `gobbler doctor --json` when setup or service readiness matters.
3. Run the relevant `gobbler` conversion command.
4. Save durable outputs with `-o ./outputs/<descriptive-name>.md`.
5. Verify the output file exists, starts with YAML frontmatter, and has a non-empty markdown body.
6. Summarize the converted content or pass the markdown file to the next workflow step.

When using JSON modes, parse stdout as data. `gobbler doctor --json`, `gobbler status --json`, and conversion commands with `--format json` write one JSON object to stdout without progress text. Batch commands with `--json` write newline-delimited JSON events.

```bash
# YouTube transcript, no Docker required
gobbler youtube "https://youtube.com/watch?v=VIDEO_ID" -o ./outputs/video.md

# Audio transcription, local Whisper
gobbler audio ./meeting.mp3 --model small -o ./outputs/meeting.md

# Document conversion, requires the document service
gobbler document ./paper.pdf --no-ocr -o ./outputs/paper.md

# Web page conversion, requires the webpage service
gobbler webpage "https://example.com" -o ./outputs/page.md
```

## Skill installation

Gobbler skills can be installed with the open skills installer used across many AI agents:

```bash
# Inspect available Gobbler skills without installing
npx skills@latest add Enablement-Engineering/gobbler --list

# Interactive install: choose skills and target agent(s)
npx skills@latest add Enablement-Engineering/gobbler

# Non-interactive example: install the main conversion skill globally
npx skills@latest add Enablement-Engineering/gobbler --skill gobbler --global --yes
```

This installs the skill files only. Install the `gobbler` CLI separately:

```bash
git clone https://github.com/Enablement-Engineering/gobbler.git
cd gobbler
make install
gobbler --version
gobbler doctor --json
```

Agents working from a source checkout can also use `uv --directory` so commands are reproducible without a global install:

```bash
uv --directory /path/to/gobbler run gobbler --version
uv --directory /path/to/gobbler run gobbler doctor --json
uv --directory /path/to/gobbler run gobbler youtube "https://youtube.com/watch?v=VIDEO_ID" -o ./outputs/transcript.md
```

## Skills workflow

The `skills/` directory contains markdown skills that teach AI agents the CLI patterns without loading every detail up front.

Use:

- `gobbler` for broad convert, extract, transcribe, fetch, download, archive, or save-as-markdown workflows.
- `gobbler-browser` for browser-extension workflows, authenticated tabs, and AI chat integrations.
- `gobbler-setup` for installation, diagnostics, Docker/ffmpeg/service readiness, and troubleshooting.

The `gobbler` skill keeps conversion details in `references/` files for progressive disclosure:

- `references/youtube.md`
- `references/audio.md`
- `references/document.md`
- `references/webpage.md`
- `references/batch.md`

## Service readiness

Some commands work without local services; others require local helpers.

| Command family | Requirement | Verify |
| --- | --- | --- |
| any | local CLI/runtime | `gobbler doctor --json` |
| `gobbler youtube` | none | `gobbler youtube URL` |
| `gobbler audio` | ffmpeg, local model download | `gobbler audio FILE --model tiny` |
| `gobbler document` | document conversion service | `gobbler doctor --json` |
| `gobbler webpage` | webpage conversion service | `gobbler doctor --json` |
| `gobbler browser` | browser extension and relay | `gobbler browser status` |

## Verification checklist

After every conversion, check:

- The command exited successfully.
- The output file exists when `-o` was used.
- The file starts with `---` YAML frontmatter.
- The content body is non-empty.
- The source URL/path is present in frontmatter when applicable.

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

## Browser safety

Browser workflows can touch authenticated pages. Agents should only use `gobbler browser` when the user has clearly asked to use the browser session, and should limit extraction to pages intentionally placed in the Gobbler tab group.

Do not extract secrets, cookies, tokens, private keys, unrelated tabs, or unrelated personal content.
