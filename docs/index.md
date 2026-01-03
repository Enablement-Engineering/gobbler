# Gobbler

<p align="center">
  <img src="assets/Gobby Feasting (small).png" alt="Gobby the Turkey mascot consuming PDF, HTML, DOCX, and VIDEO files, outputting clean MD blocks" width="400">
</p>

**Universal Content Conversion to Markdown for AI**

Gobbler transforms any content—YouTube videos, web pages, documents, audio files, even live browser sessions—into clean, structured markdown that AI systems can immediately reason about.

---

## The Problem

AI assistants work best with markdown. But content exists in countless formats—PDFs, videos, web pages behind logins, audio recordings. Getting that content into a format AI can use requires:

- Different tools for each content type
- Custom scripts to extract and format
- Lost metadata and inconsistent output
- No unified way for AI agents to access content

**Gobbler solves this.** One tool, one output format, multiple access patterns.

---

## Quick Example

```bash
# Every content type -> Same pattern -> Same output format
gobbler youtube "https://youtube.com/watch?v=..." -o transcript.md
gobbler document report.pdf -o report.md
gobbler audio meeting.mp3 -o meeting.md
gobbler webpage "https://docs.example.com" -o docs.md
```

Every conversion produces **markdown with YAML frontmatter**:

```markdown
---
source: https://youtube.com/watch?v=VIDEO_ID
type: youtube_transcript
title: "Video Title"
duration: 847
word_count: 2341
converted_at: 2026-01-03T10:30:00Z
---

# Video Title

Content here, ready for AI consumption...
```

---

## Three Ways to Use Gobbler

### 1. CLI (For Humans & Scripts)

```bash
gobbler youtube URL              # YouTube transcripts
gobbler audio FILE               # Audio/video transcription
gobbler document FILE            # PDF, DOCX, PPTX, XLSX
gobbler webpage URL              # Web pages (JS-rendered)
gobbler batch youtube-playlist URL  # Batch processing
```

### 2. Skills (For AI Agents)

Skills are markdown instruction files that teach AI agents how to use Gobbler. They provide **progressive disclosure**—AI only loads what it needs.

### 3. MCP Protocol (For Claude Desktop/Code)

```bash
# Add to Claude Code
claude mcp add gobbler-mcp -- uv --directory /path/to/gobbler run gobbler-mcp
```

---

## Features at a Glance

| Type | Command | Backend |
|------|---------|---------|
| YouTube | `gobbler youtube URL` | youtube-transcript-api |
| Audio/Video | `gobbler audio FILE` | faster-whisper (local) |
| Documents | `gobbler document FILE` | Docling (Docker) |
| Web Pages | `gobbler webpage URL` | Crawl4AI (Docker) |

---

## Get Started

<div class="grid cards" markdown>

-   :material-rocket-launch:{ .lg .middle } **Quick Start**

    ---

    Get up and running in 5 minutes

    [:octicons-arrow-right-24: Quick Start](QUICK_START.md)

-   :material-download:{ .lg .middle } **Installation**

    ---

    Detailed installation instructions

    [:octicons-arrow-right-24: Installation](installation.md)

-   :material-book-open-variant:{ .lg .middle } **Skills Guide**

    ---

    Learn about AI agent skills

    [:octicons-arrow-right-24: Skills](SKILLS.md)

-   :material-code-braces:{ .lg .middle } **Architecture**

    ---

    Understand how Gobbler works

    [:octicons-arrow-right-24: Architecture](ARCHITECTURE.md)

</div>

---

## Philosophy

> **"Markdown is the lingua franca of human-AI communication."**

Gobbler exists because:

1. AI works best with structured text
2. Content exists in many formats
3. Converting content shouldn't require expertise in each format
4. AI agents need reliable, documented procedures—not just raw tools

We provide **excellent operating procedures** wrapped around excellent tools.

---

## License

MIT License - see [LICENSE](https://github.com/Enablement-Engineering/gobbler/blob/main/LICENSE) for details.
