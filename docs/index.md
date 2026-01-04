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

## Three Ways to Use Gobbler

=== "CLI"

    Direct command-line usage for humans and scripts:
    
    ```bash
    gobbler youtube "URL" -o transcript.md
    gobbler audio recording.mp3 --model medium
    gobbler document report.pdf --no-ocr
    ```

=== "MCP Protocol"

    For Claude Desktop and Claude Code:
    
    ```bash
    claude mcp add gobbler-mcp -- uv --directory /path/to/gobbler run gobbler-mcp
    ```
    
    Then ask Claude: *"Transcribe this YouTube video: URL"*

=== "Skills"

    Markdown instruction files for AI agents. Skills provide progressive disclosure—AI only loads what it needs.
    
    [:octicons-arrow-right-24: Learn about Skills](SKILLS.md)

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

</div>
