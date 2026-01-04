---
icon: material/lightning-bolt
---

# Gobbler Skills

Skills are reusable, filesystem-based instructions that teach Claude how to use the `gobbler` CLI to convert content to markdown.

## What are Skills?

Skills are markdown files (`SKILL.md`) with YAML frontmatter that Claude discovers and loads on-demand. Each skill contains:

- **Metadata** (frontmatter) - `name` and `description` that tell Claude when to use the skill
- **Instructions** - CLI commands, examples, and options for completing tasks

Skills use **progressive disclosure**: Claude only loads ~100 tokens of metadata at startup. The full instructions are read only when the skill is triggered.

## Skill Structure

Each Gobbler skill is a `SKILL.md` file:

```
skills/gobbler-youtube/
└── SKILL.md           # Instructions with YAML frontmatter
```

Example `SKILL.md`:

```yaml
---
name: gobbler-youtube
description: Transcribe YouTube videos to markdown. Use when user wants to get transcripts from YouTube.
---

# Gobbler YouTube

Convert YouTube videos to markdown transcripts.

## Transcribe Video

```bash
# Basic transcription
gobbler youtube "https://youtube.com/watch?v=VIDEO_ID"

# With timestamps
gobbler youtube "https://youtube.com/watch?v=VIDEO_ID" --timestamps

# Save to file
gobbler youtube "https://youtube.com/watch?v=VIDEO_ID" -o transcript.md
```
```

## How Claude Uses Skills

1. **Discovery** - Claude sees skill metadata in its system prompt
2. **Trigger** - When your request matches a skill's description, Claude reads `SKILL.md`
3. **Execute** - Claude runs the `gobbler` CLI commands from the instructions
4. **Output** - CLI returns markdown that Claude can use or save

Skills work with Claude Code, Claude Desktop, and OpenCode. They're discovered from:
- `skills/gobbler-*/SKILL.md` (in the Gobbler repo)
- `.claude/skills/*/SKILL.md` (Claude Code compatible)

## Available Skills

| Skill | Description | CLI Command |
|-------|-------------|-------------|
| `gobbler-youtube` | YouTube transcription | `gobbler youtube URL` |
| `gobbler-audio` | Audio/video transcription | `gobbler audio FILE` |
| `gobbler-document` | PDF, DOCX, PPTX, XLSX conversion | `gobbler document FILE` |
| `gobbler-webpage` | Web page to markdown | `gobbler webpage URL` |
| `gobbler-browser` | Browser control + AI chat integrations | `gobbler browser ...` |
| `gobbler-setup` | Installation and troubleshooting | Various |

The `gobbler-browser` skill includes integrations for NotebookLM, Claude.ai, ChatGPT, and Gemini. These use DOM automation and may break with site updates.

## Skill Reference

### gobbler-youtube

Transcribe YouTube videos to markdown.

```bash
gobbler youtube "https://youtube.com/watch?v=VIDEO_ID"
gobbler youtube "URL" --timestamps           # Include timestamps
gobbler youtube "URL" --language es          # Specific language
gobbler youtube "URL" -o transcript.md       # Save to file
```

### gobbler-audio

Transcribe audio and video files using Whisper.

```bash
gobbler audio /path/to/audio.mp3
gobbler audio /path/to/video.mp4 --model medium    # Larger model
gobbler audio /path/to/audio.mp3 --timestamps      # With timestamps
gobbler audio /path/to/audio.mp3 -o transcript.md  # Save to file
```

**Models:** tiny, base, small (default), medium, large

### gobbler-document

Convert documents to markdown using Docling.

**Requires:** Docling Docker container (`make start-docker`)

```bash
gobbler document /path/to/file.pdf
gobbler document /path/to/file.docx --no-ocr    # Skip OCR (faster)
gobbler document /path/to/file.pdf -o output.md # Save to file
```

**Supported formats:** PDF, DOCX, PPTX, XLSX

### gobbler-webpage

Convert web pages to markdown using Crawl4AI.

**Requires:** Crawl4AI Docker container (`make start-docker`)

```bash
gobbler webpage "https://example.com"
gobbler webpage "https://example.com" -o page.md
```

### gobbler-browser

Control browser tabs via the Gobbler extension. Includes AI chat integrations for NotebookLM, Claude.ai, ChatGPT, and Gemini.

**Requires:** Browser extension installed, tabs in "Gobbler" group

> **Note:** AI chat integrations use DOM automation and may break when sites update their UI.

```bash
# Core browser commands
gobbler browser status              # Check connection
gobbler browser list                # List controlled tabs
gobbler browser extract             # Extract current page
gobbler browser inject              # Inject APIs (required for AI chats)

# AI Chat Integrations (all follow same pattern)
gobbler notebooklm list                              # List notebooks
gobbler notebooklm query "What are the key points?"  # Query notebook

gobbler chatgpt list                        # List ChatGPT tabs
gobbler chatgpt query "Your message here"   # Send message

gobbler claude list                         # List Claude tabs
gobbler claude query "Your message here"    # Send message

gobbler gemini list                         # List Gemini tabs
gobbler gemini query "Your message here"    # Send message

# Common commands for all AI chats
gobbler <service> last                      # Get last response
gobbler <service> history --count 10        # Get history
gobbler <service> info                      # Get metadata
```

## Installation

### For OpenCode

OpenCode discovers skills from `.opencode/skill/` or `~/.config/opencode/skill/`. Clone Gobbler and symlink the skills:

```bash
# Clone the repo
git clone https://github.com/Enablement-Engineering/gobbler.git
cd gobbler && make install

# Symlink skills to OpenCode's skill directory
mkdir -p ~/.config/opencode/skill
for skill in skills/gobbler-*/; do
  ln -sf "$(pwd)/$skill" ~/.config/opencode/skill/
done
```

For MCP tools, add to your `opencode.json`:

```json
{
  "mcp": {
    "gobbler": {
      "type": "local",
      "command": ["uv", "--directory", "/path/to/gobbler", "run", "gobbler-mcp"]
    }
  }
}
```

### For Claude Code

Clone the repo and add to Claude Code:

```bash
git clone https://github.com/Enablement-Engineering/gobbler.git
cd gobbler && make install

# Add MCP server to Claude Code
claude mcp add gobbler-mcp -- uv --directory /path/to/gobbler run gobbler-mcp
```

Skills are auto-discovered from `skills/gobbler-*/SKILL.md` when working in the repo.

### Via Git Clone (Manual)

```bash
git clone https://github.com/Enablement-Engineering/gobbler.git
cd gobbler
make install
```

Skills are in `skills/gobbler-*/SKILL.md`.

### Prerequisites

- **Python 3.11+** and **uv** package manager
- **Docker** (for webpage/document conversion): `make start-docker`
- **ffmpeg** (for audio): `brew install ffmpeg`
- **Browser extension** (for browser skills): See [Browser Extension](browser-extension.md)

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
