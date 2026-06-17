---
icon: material/lightning-bolt
---

# Gobbler Skills

Skills are reusable, filesystem-based instructions that teach CLI-capable AI agents how to use the `gobbler` CLI to convert content to markdown.

## What are Skills?

Skills are markdown files (`SKILL.md`) with YAML frontmatter that agents discover and load on-demand. Each skill contains:

- **Metadata** (frontmatter) - `name` and `description` that tell agents when to use the skill
- **Instructions** - CLI commands, examples, and options for completing tasks
- **References** - optional supporting files loaded only when needed

Skills use **progressive disclosure**: agents can load lightweight metadata first, then read full instructions or references only when the task requires them.

## Skill Structure

Gobbler intentionally keeps the top-level skill list small:

```text
skills/
├── gobbler/          # Convert/extract/transcribe/archive content to markdown
│   └── references/   # YouTube, audio, document, webpage, and batch details
├── gobbler-browser/  # Browser/session automation and AI chat integrations
└── gobbler-setup/    # Installation, diagnostics, services, and troubleshooting
```

This avoids trigger competition between separate YouTube/audio/document/webpage skills while preserving detailed recipes through references.

## How Agents Use Skills

1. **Discovery** - The agent sees skill metadata in its workspace or system prompt.
2. **Trigger** - When the request matches a skill's description, the agent reads `SKILL.md`.
3. **Reference loading** - If the task needs details, the agent reads only the relevant reference file.
4. **Execute** - The agent runs the `gobbler` CLI commands from the instructions.
5. **Output** - CLI returns markdown that the agent can use or save.

Skills work with AI agents that can read `SKILL.md` files, run CLI commands, and inspect output files. They are discovered from:

- `skills/gobbler*/SKILL.md` in the Gobbler repo
- agent-specific skill folders or workspace instruction directories
- installs created by the open skills installer

## Available Skills

| Skill | Description | Primary command |
|-------|-------------|-----------------|
| `gobbler` | Convert, extract, transcribe, fetch, download, archive, or save external content as markdown | `gobbler ...` |
| `gobbler-browser` | Browser control, authenticated tab extraction, and AI chat integrations | `gobbler browser ...` |
| `gobbler-setup` | Installation, diagnostics, Docker/ffmpeg/service troubleshooting | `gobbler doctor --json` |

## Main `gobbler` Skill

Use `gobbler` for the normal content-to-markdown workflow:

```bash
gobbler doctor --json
gobbler youtube "https://youtube.com/watch?v=VIDEO_ID" -o ./outputs/video.md
gobbler audio ./meeting.mp3 --model small -o ./outputs/meeting.md
gobbler document ./paper.pdf --no-ocr -o ./outputs/paper.md
gobbler webpage "https://example.com" -o ./outputs/page.md
```

Detailed recipes live in:

- `skills/gobbler/references/youtube.md`
- `skills/gobbler/references/audio.md`
- `skills/gobbler/references/document.md`
- `skills/gobbler/references/webpage.md`
- `skills/gobbler/references/batch.md`

## Browser Skill

Use `gobbler-browser` for workflows that touch browser tabs, authenticated pages, or AI chat services. Browser automation has different safety boundaries than normal conversion.

```bash
gobbler browser status
gobbler browser list
gobbler browser extract -o page.md
gobbler browser inject
```

The browser skill includes integrations for NotebookLM, Claude.ai, ChatGPT, and Gemini. These use DOM automation and may break with site updates.

## Setup Skill

Use `gobbler-setup` when installing Gobbler or troubleshooting service readiness.

```bash
gobbler --version
gobbler doctor --json
make start-docker
```

## Installation

### Recommended: open skills installer

```bash
# Inspect available Gobbler skills without installing
npx skills@latest add Enablement-Engineering/gobbler --list

# Interactive install: choose skills and target agent(s)
npx skills@latest add Enablement-Engineering/gobbler

# Non-interactive example: install the main conversion skill globally
npx skills@latest add Enablement-Engineering/gobbler --skill gobbler --global --yes
```

The skills installer copies or symlinks skill files into the selected agent's skill directory. It does **not** install the `gobbler` CLI itself.

### Manual copy/symlink

```bash
mkdir -p ~/.local/share/gobbler-skills
cp -R skills/gobbler* ~/.local/share/gobbler-skills/
```

## Prerequisites

- **Python 3.11+** and **uv** package manager
- **Docker runtime** for webpage/document conversion: `make start-docker`
- **ffmpeg** for audio/video transcription
- **Browser extension** for browser skills: see [Browser Extension](browser-extension.md)

## Backend Services

The `gobbler` CLI connects to these backends:

| Backend | Port | Purpose | Required For |
|---------|------|---------|--------------|
| Crawl4AI | 11235 | Web scraping with JavaScript | `gobbler webpage` |
| Docling | 5001 | Document conversion | `gobbler document` |
| YouTube APIs | - | Transcript extraction | `gobbler youtube` |
| Whisper | - | Local audio transcription | `gobbler audio` |
| Relay | 4625 | Browser extension bridge | Browser commands |

Start Docker services with `make start-docker`.
