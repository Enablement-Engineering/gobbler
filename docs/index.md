# Gobbler

<p align="center">
  <img src="assets/Gobby Feasting (small).png" alt="Gobby the Turkey mascot" width="300">
</p>

<p align="center">
  <strong>Universal Content Conversion to Markdown for AI</strong>
</p>

<p align="center">
  <a href="QUICK_START/">Get Started</a> &nbsp;|&nbsp;
  <a href="cli/">CLI Reference</a> &nbsp;|&nbsp;
  <a href="https://github.com/Enablement-Engineering/gobbler">GitHub</a>
</p>

---

## What is Gobbler?

Gobbler transforms any content into clean, structured markdown that AI systems can immediately use:

```bash
gobbler youtube "https://youtube.com/watch?v=..." -o transcript.md
gobbler document report.pdf -o report.md
gobbler audio meeting.mp3 -o meeting.md
gobbler webpage "https://docs.example.com" -o docs.md
```

**One tool. One output format. Every content type.**

---

## Project Status

Gobbler is an **active beta**, CLI-first content conversion tool for AI workflows. The supported automation path is the `gobbler` CLI plus markdown Skills for agents; MCP support was removed in v0.2.0 to keep the public interface simpler and more reliable.

[:octicons-arrow-right-24: Hermes/OpenClaw usage guide](agents.md) · [:octicons-arrow-right-24: Roadmap](https://github.com/Enablement-Engineering/gobbler/blob/main/ROADMAP.md) · [:octicons-arrow-right-24: Security policy](https://github.com/Enablement-Engineering/gobbler/blob/main/SECURITY.md)

---

## Install in 60 Seconds

```bash
# Clone and install
git clone https://github.com/Enablement-Engineering/gobbler.git
cd gobbler && make install

# Try it
gobbler youtube "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
```

[:octicons-arrow-right-24: Full installation guide](installation.md)

---

## What Can Gobbler Convert?

| Content | Command | Requirements |
|---------|---------|--------------|
| YouTube videos | `gobbler youtube URL` | None |
| Audio/video files | `gobbler audio FILE` | ffmpeg |
| PDF, DOCX, PPTX, XLSX | `gobbler document FILE` | Docker |
| Web pages | `gobbler webpage URL` | Docker |
| Browser sessions | `gobbler browser extract` | Browser extension |

---

## CLI-First Access

=== "CLI"

    Direct command-line usage for humans, agents, and scripts:
    
    ```bash
    gobbler youtube "URL" -o transcript.md
    gobbler audio recording.mp3 --model medium
    gobbler document report.pdf --no-ocr
    ```

=== "Skills"

    Markdown instruction files that teach AI agents how to use the CLI. Skills provide progressive disclosure—AI only loads what it needs.
    
    [:octicons-arrow-right-24: Learn about Skills](SKILLS.md)

=== "Browser Extension"

    A local extension plus relay lets the CLI extract authenticated browser sessions and automate supported AI chat surfaces.
    
    [:octicons-arrow-right-24: Set up the Browser Extension](browser-extension.md)

---

## Pluggable Providers

Swap backends without changing your workflow:

```bash
# Use local Whisper (default, free, private)
gobbler audio recording.mp3

# Use OpenAI's API (faster, paid)
gobbler audio recording.mp3 --provider openai-whisper
```

| Category | Providers |
|----------|-----------|
| Transcription | `whisper-local`, `openai-whisper` |
| Documents | `docling` |
| Web Pages | `crawl4ai` |

[:octicons-arrow-right-24: Provider documentation](providers.md)

---

## Output Format

Every conversion produces markdown with YAML frontmatter:

```markdown
---
source: https://youtube.com/watch?v=VIDEO_ID
type: youtube_transcript
title: "Video Title"
duration: 847
word_count: 2341
---

# Video Title

Content here, ready for AI consumption...
```

---

## Next Steps

<div class="grid cards" markdown>

-   :material-rocket-launch:{ .lg .middle } **Quick Start**

    Get up and running in 5 minutes

    [:octicons-arrow-right-24: Quick Start](QUICK_START.md)

-   :material-console:{ .lg .middle } **CLI Reference**

    All commands and options

    [:octicons-arrow-right-24: CLI Usage](cli.md)

-   :material-cog:{ .lg .middle } **Configuration**

    Customize Gobbler's behavior

    [:octicons-arrow-right-24: Configuration](configuration.md)

-   :material-puzzle:{ .lg .middle } **Browser Extension**

    Extract authenticated content

    [:octicons-arrow-right-24: Browser Extension](browser-extension.md)

-   :material-robot:{ .lg .middle } **Hermes/OpenClaw Usage**

    CLI-first patterns for Hermes and OpenClaw

    [:octicons-arrow-right-24: Hermes/OpenClaw Usage](agents.md)

</div>
