# Gobbler Architecture Diagrams

Accurate diagrams of the current Gobbler architecture as of January 2026.

---

## 1. Package Dependency Diagram

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           GOBBLER PACKAGE STRUCTURE                          │
└─────────────────────────────────────────────────────────────────────────────┘

                              ┌──────────────────┐
                              │   gobbler_mcp    │
                              │ (MCP Server)     │
                              │                  │
                              │ - FastMCP server │
                              │ - Tool wrappers  │
                              │ - Config/metrics │
                              └────────┬─────────┘
                                       │ imports
                    ┌──────────────────┼──────────────────┐
                    │                  │                  │
                    ▼                  ▼                  ▼
         ┌──────────────────┐  ┌──────────────┐  ┌──────────────────┐
         │   gobbler_cli    │  │ gobbler_core │  │  gobbler_relay   │
         │ (CLI Interface)  │  │ (Core Logic) │  │ (Browser Relay)  │
         │                  │  │              │  │                  │
         │ - typer commands │  │ - providers  │  │ - aiohttp server │
         │ - progress bars  │  │ - converters │  │ - WebSocket mgmt │
         │ - JSON output    │  │ - utilities  │  │ - HTTP client    │
         └────────┬─────────┘  └──────────────┘  └────────┬─────────┘
                  │                    ▲                  │
                  │ imports            │ imports          │ imports
                  │                    │                  │
                  └────────────────────┼──────────────────┘
                                       │
                              ┌────────┴─────────┐
                              │  gobbler_queue   │
                              │ (Job Queue)      │
                              │                  │
                              │ - SQLite backend │
                              │ - JobManager     │
                              │ - Worker process │
                              └──────────────────┘
                                       │
                                       │ NO package imports
                                       │ (standalone)
                                       ▼

LEGEND:
  ────►  Package imports from
  ┌───┐  Python package
  │   │
  └───┘
```

### Dependency Summary Table

| Package        | Depends On                           | Used By                      |
|----------------|--------------------------------------|------------------------------|
| gobbler_core   | (no internal deps)                   | cli, mcp, relay              |
| gobbler_cli    | gobbler_core                         | mcp (via subprocess)         |
| gobbler_relay  | gobbler_core.utils                   | mcp, cli                     |
| gobbler_queue  | (standalone - no internal deps)      | mcp, cli                     |
| gobbler_mcp    | gobbler_core, gobbler_relay          | (entry point)                |

---

## 2. Data Flow Diagrams

### 2a. YouTube Transcription via CLI

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    YOUTUBE TRANSCRIPTION - CLI PATH                          │
└─────────────────────────────────────────────────────────────────────────────┘

  User                                                            External
    │                                                             Services
    │ $ gobbler youtube "https://youtube.com/watch?v=ABC123"         │
    ▼                                                                │
┌─────────┐                                                          │
│  CLI    │──────────────────────────────────────────────────────────┤
│ (typer) │                                                          │
└────┬────┘                                                          │
     │                                                               │
     │ calls                                                         │
     ▼                                                               │
┌────────────────────────────┐                                       │
│ gobbler_cli/commands/      │                                       │
│ convert.py:youtube()       │                                       │
└─────────────┬──────────────┘                                       │
              │                                                      │
              │ imports & calls                                      │
              ▼                                                      │
┌────────────────────────────┐      ┌────────────────────────┐       │
│ gobbler_core/converters/   │─────►│ gobbler_core/providers/│       │
│ youtube.py                 │      │ youtube.py             │       │
│                            │      │                        │       │
│ convert_youtube_to_markdown│      │ - AutoFallbackProvider │       │
└────────────┬───────────────┘      │ - YouTubeTranscriptAPI │       │
             │                      │ - TranscriptAPIProvider│       │
             │                      └───────────┬────────────┘       │
             │                                  │                    │
             │                                  │ HTTP requests      │
             │                                  ▼                    │
             │                      ┌───────────────────────┐        │
             │ uses                 │   YouTube APIs        │        │
             │                      │                       │◄───────┘
             ▼                      │ - youtube-transcript- │
┌────────────────────────────┐      │   api (primary)       │
│ gobbler_core/utils/        │      │ - TranscriptAPI.io    │
│ frontmatter.py             │      │   (fallback)          │
│                            │      └───────────────────────┘
│ create_youtube_frontmatter │
└────────────┬───────────────┘
             │
             │ also uses
             ▼
┌────────────────────────────┐
│ yt-dlp (library)           │
│ Extracts video metadata    │
│ (title, channel, duration) │
└────────────────────────────┘
             │
             ▼
      ┌──────────────┐
      │  stdout or   │
      │  -o file.md  │
      └──────────────┘

OUTPUT EXAMPLE:
---
source_type: youtube
video_url: https://youtube.com/watch?v=ABC123
title: "Video Title"
channel: "Channel Name"
duration: 1234
language: en
word_count: 5678
converted_at: 2026-01-03T12:00:00Z
---

# Video Transcript

Full transcript text here...
```

### 2b. YouTube Transcription via MCP

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    YOUTUBE TRANSCRIPTION - MCP PATH                          │
└─────────────────────────────────────────────────────────────────────────────┘

  AI Agent                                                        External
  (Claude)                                                        Services
    │                                                                │
    │ tool call: transcribe_youtube(video_url="...")                 │
    ▼                                                                │
┌──────────────────────────┐                                         │
│ gobbler_mcp/server.py    │                                         │
│ (FastMCP Server)         │                                         │
└───────────┬──────────────┘                                         │
            │                                                        │
            │ dispatches to                                          │
            ▼                                                        │
┌────────────────────────────┐                                       │
│ gobbler_mcp/tools/         │                                       │
│ conversion.py              │                                       │
│                            │                                       │
│ transcribe_youtube()       │                                       │
└───────────┬────────────────┘                                       │
            │                                                        │
            │ subprocess.run()    ┌────────────────────────────────┐ │
            │────────────────────►│ gobbler youtube <url>          │ │
            │                     │ (CLI as subprocess)            │ │
            │                     └─────────────┬──────────────────┘ │
            │                                   │                    │
            │                                   │ (same as CLI path) │
            │                                   ▼                    │
            │                     ┌────────────────────────────────┐ │
            │                     │ gobbler_core/converters/       │ │
            │                     │ youtube.py                     │ │
            │◄────────────────────│ convert_youtube_to_markdown()  │ │
            │  stdout captured    └────────────────────────────────┘ │
            │                                   │                    │
            ▼                                   ▼                    │
┌────────────────────────────┐    ┌────────────────────────────────┐ │
│ Return markdown to Claude  │    │ YouTube Transcript APIs       │◄┘
└────────────────────────────┘    └────────────────────────────────┘

KEY INSIGHT: MCP tools are THIN WRAPPERS around CLI
  - Most MCP tools call `subprocess.run(["gobbler", ...])
  - CLI does the heavy lifting via gobbler_core converters
  - This keeps MCP server lightweight and avoids code duplication
```

### 2c. Browser Automation (NotebookLM Query)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    BROWSER AUTOMATION - NOTEBOOKLM QUERY                     │
└─────────────────────────────────────────────────────────────────────────────┘

  AI Agent                         Relay Server              Browser
  or CLI                              (4625)                Extension
    │                                    │                      │
    │ gobbler notebooklm query "..."     │                      │
    ▼                                    │                      │
┌───────────────────┐                    │                      │
│ gobbler_cli/      │                    │                      │
│ commands/         │                    │                      │
│ notebooklm.py     │                    │                      │
└─────────┬─────────┘                    │                      │
          │                              │                      │
          │ HTTP POST /command           │                      │
          │ (via gobbler_relay.client)   │                      │
          ▼                              │                      │
┌─────────────────────────────────┐      │                      │
│ gobbler_relay/client.py         │      │                      │
│ send_command()                  │──────┤                      │
│ execute_script_in_tab()         │      │                      │
└─────────────────────────────────┘      │                      │
                                         │                      │
                                         ▼                      │
                              ┌────────────────────┐            │
                              │ gobbler_relay/     │            │
                              │ relay.py           │            │
                              │                    │            │
                              │ - aiohttp server   │            │
                              │ - WebSocket hub    │            │
                              │ - /command handler │            │
                              └─────────┬──────────┘            │
                                        │                       │
                                        │ WebSocket message     │
                                        │ {type: "command",     │
                                        │  command: "execute_   │
                                        │    script_in_tab",    │
                                        │  params: {...}}       │
                                        ▼                       │
                              ┌────────────────────┐            │
                              │ WebSocket          │────────────┤
                              │ Connection         │            │
                              └────────────────────┘            │
                                                                │
                                                                ▼
                                                    ┌──────────────────────┐
                                                    │ browser-extension/   │
                                                    │ content.js           │
                                                    │                      │
                                                    │ - Injects JS into    │
                                                    │   NotebookLM page    │
                                                    │ - Submits query      │
                                                    │ - Polls for response │
                                                    │ - Returns result     │
                                                    └──────────┬───────────┘
                                                               │
                                                               │ Uses page-specific API
                                                               ▼
                                                    ┌──────────────────────┐
                                                    │ browser-extension/   │
                                                    │ page-apis/           │
                                                    │ notebooklm.js        │
                                                    │                      │
                                                    │ NotebookLMAPI:       │
                                                    │ - submitQuery()      │
                                                    │ - getLastResponse()  │
                                                    │ - getChatHistory()   │
                                                    └──────────────────────┘
                                                               │
                                                               │ DOM manipulation
                                                               ▼
                                                    ┌──────────────────────┐
                                                    │ notebooklm.google.   │
                                                    │ com (browser tab)    │
                                                    └──────────────────────┘

RELAY SERVER LIFECYCLE:
  - Auto-starts as daemon when first needed (by MCP or CLI)
  - Runs on port 4625
  - Auto-shuts down after 4 hours of inactivity
  - Pidfile: ~/.cache/gobbler/relay.pid
```

### 2d. Batch Processing

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    BATCH PROCESSING - YOUTUBE PLAYLIST                       │
└─────────────────────────────────────────────────────────────────────────────┘

  User/Agent
    │
    │ gobbler batch youtube-playlist <url> --output <dir>
    │ OR
    │ MCP: batch_transcribe_youtube_playlist(playlist_url, output_dir)
    ▼
┌───────────────────────────────────────────────────────────────────────────┐
│                              Entry Point                                   │
│                                                                           │
│  CLI: gobbler_cli/commands/batch.py                                       │
│  MCP: gobbler_mcp/tools/batch.py (thin wrapper → CLI subprocess)          │
└─────────────────────────────────────────────────────────────────────────┬─┘
                                                                          │
                                                                          ▼
┌───────────────────────────────────────────────────────────────────────────┐
│ Batch Orchestration (conceptual - actual impl in CLI batch commands)      │
│                                                                           │
│ 1. Extract video URLs from playlist (yt-dlp)                              │
│ 2. Create work queue with concurrency limit                               │
│ 3. Process items in parallel                                              │
│ 4. Aggregate results and generate report                                  │
└─────────────────────────────────────────────────────────────────────────┬─┘
                                                                          │
                  ┌───────────────────────────────────────────────────────┤
                  │                                                       │
                  ▼                                                       ▼
    ┌──────────────────────────┐                      ┌──────────────────────────┐
    │ Concurrent Worker 1      │                      │ Concurrent Worker N      │
    │                          │                      │                          │
    │ convert_youtube_to_      │        ...          │ convert_youtube_to_      │
    │ markdown(video_url_1)    │                      │ markdown(video_url_N)    │
    └──────────────┬───────────┘                      └──────────────┬───────────┘
                   │                                                 │
                   ▼                                                 ▼
    ┌──────────────────────────┐                      ┌──────────────────────────┐
    │ Write to:                │                      │ Write to:                │
    │ <output_dir>/            │                      │ <output_dir>/            │
    │   <video_title_1>.md     │                      │   <video_title_N>.md     │
    └──────────────────────────┘                      └──────────────────────────┘
                   │                                                 │
                   └───────────────────────┬─────────────────────────┘
                                           │
                                           ▼
                             ┌───────────────────────────┐
                             │ Batch Report Summary      │
                             │                           │
                             │ - Total: N items          │
                             │ - Successful: X           │
                             │ - Failed: Y               │
                             │ - Processing time: Z      │
                             └───────────────────────────┘

CONCURRENCY LIMITS (from constants.py):
  - YouTube: max 10 concurrent
  - Webpages: max 10 concurrent  
  - Audio: max 4 concurrent (resource intensive)
  - Documents: max 5 concurrent
```

---

## 3. Skills Integration Diagram

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    SKILLS ARCHITECTURE                                       │
│            How AI Agents Discover and Use Gobbler                            │
└─────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────┐
│                           AI AGENT (Claude/OpenCode)                         │
│                                                                              │
│  Agent reads SKILL.md files from skills/ directory                          │
│  Each SKILL.md has YAML frontmatter + markdown instructions                 │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      │ Agent parses
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                          skills/gobbler-*/SKILL.md                           │
│                                                                              │
│  ┌───────────────────────────────────────────────────────────────────────┐  │
│  │ ---                                                                    │  │
│  │ name: gobbler-youtube                          ◄── Skill identifier   │  │
│  │ description: "Transcribe YouTube videos..."    ◄── When to use        │  │
│  │ version: 2.0.0                                                        │  │
│  │ ---                                                                    │  │
│  │                                                                        │  │
│  │ # Gobbler YouTube                              ◄── Human-readable     │  │
│  │                                                    documentation       │  │
│  │ ## Transcribe Video                                                    │  │
│  │                                                                        │  │
│  │ ```bash                                                                │  │
│  │ gobbler youtube "https://..."   ◄── CLI commands for agent to execute │  │
│  │ ```                                                                    │  │
│  └───────────────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      │ Agent decides to use skill
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                          Agent Executes CLI Command                          │
│                                                                              │
│  Uses Bash tool to run: gobbler youtube "https://youtube.com/..."           │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                          gobbler CLI                                         │
│                          (Entry point: gobbler_cli/main.py)                  │
│                                                                              │
│  Processes command and returns markdown to stdout                            │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                          Agent Receives Output                               │
│                                                                              │
│  Markdown with YAML frontmatter, ready to use or save                        │
└─────────────────────────────────────────────────────────────────────────────┘


AVAILABLE SKILLS:
┌────────────────────┬────────────────────────────────────────────────────────┐
│ Skill              │ Description                                            │
├────────────────────┼────────────────────────────────────────────────────────┤
│ gobbler-youtube    │ YouTube video transcription                            │
│ gobbler-audio      │ Audio/video file transcription (Whisper)               │
│ gobbler-document   │ PDF, DOCX, PPTX, XLSX conversion                       │
│ gobbler-webpage    │ Web page to markdown                                   │
│ gobbler-browser    │ Browser automation + AI chat integrations*             │
│ gobbler-setup      │ Setup and installation instructions                    │
│ gobbler-utils      │ Utility commands (relay, jobs, etc.)                   │
└────────────────────┴────────────────────────────────────────────────────────┘

* gobbler-browser includes NotebookLM, Claude.ai, ChatGPT, and Gemini
  integrations (DOM automation - may break with site updates)

SKILL LOADING FLOW:
  1. Agent context includes skills/ directory
  2. Agent sees list of SKILL.md files
  3. Agent reads relevant SKILL.md based on user request
  4. Agent follows instructions to execute CLI commands
  5. Agent captures output and processes/saves result
```

---

## 4. External Dependencies Map

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    EXTERNAL DEPENDENCIES                                     │
└─────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────┐
│                              GOBBLER                                         │
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │                     gobbler_core/gobbler_cli                         │    │
│  │                                                                      │    │
│  │  ┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐   │    │
│  │  │ YouTube Provider │  │ Audio Converter  │  │ Document Conv.   │   │    │
│  │  │                  │  │                  │  │                  │   │    │
│  │  │ Uses:            │  │ Uses:            │  │ Uses:            │   │    │
│  │  │ - yt-dlp         │  │ - faster-whisper │  │ - Docling API    │   │    │
│  │  │ - youtube-       │  │   (local)        │  │   (Docker)       │   │    │
│  │  │   transcript-api │  │                  │  │                  │   │    │
│  │  │ - TranscriptAPI  │  │ Whisper runs     │  │                  │   │    │
│  │  │   (paid backup)  │  │ locally via      │  │                  │   │    │
│  │  │                  │  │ Metal/CoreML     │  │                  │   │    │
│  │  └───────┬──────────┘  └───────┬──────────┘  └───────┬──────────┘   │    │
│  │          │                     │                     │              │    │
│  │          │                     │                     │              │    │
│  │  ┌───────┴──────────┐  ┌───────┴──────────┐  ┌───────┴──────────┐   │    │
│  │  │ Webpage Conv.    │  │ gobbler_relay    │  │ gobbler_queue    │   │    │
│  │  │                  │  │                  │  │                  │   │    │
│  │  │ Uses:            │  │ Uses:            │  │ Uses:            │   │    │
│  │  │ - Crawl4AI       │  │ - aiohttp        │  │ - SQLite         │   │    │
│  │  │   (Docker)       │  │ - WebSocket      │  │   (local file)   │   │    │
│  │  │                  │  │                  │  │                  │   │    │
│  │  └──────────────────┘  └──────────────────┘  └──────────────────┘   │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────────────────┘
                │                     │                     │
                │                     │                     │
                ▼                     ▼                     ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                         EXTERNAL SERVICES                                    │
│                                                                              │
│  ┌────────────────────────────────────────────────────────────────────┐     │
│  │                        REQUIRED SERVICES                            │     │
│  │  (functionality will fail without these)                           │     │
│  │                                                                     │     │
│  │  NONE - All core functionality can run without external services   │     │
│  │  YouTube transcription uses free APIs that don't require Docker    │     │
│  │  Audio transcription runs locally via faster-whisper               │     │
│  └────────────────────────────────────────────────────────────────────┘     │
│                                                                              │
│  ┌────────────────────────────────────────────────────────────────────┐     │
│  │                        OPTIONAL SERVICES                            │     │
│  │  (functionality enhanced when available)                           │     │
│  │                                                                     │     │
│  │  ┌────────────────────┐  ┌────────────────────┐                    │     │
│  │  │ Crawl4AI           │  │ Docling            │                    │     │
│  │  │ (Docker container) │  │ (Docker container) │                    │     │
│  │  │                    │  │                    │                    │     │
│  │  │ Port: 11235        │  │ Port: 5001         │                    │     │
│  │  │ Protocol: HTTP     │  │ Protocol: HTTP     │                    │     │
│  │  │                    │  │                    │                    │     │
│  │  │ For: webpage       │  │ For: PDF, DOCX,    │                    │     │
│  │  │ conversion with    │  │ PPTX, XLSX with    │                    │     │
│  │  │ JS rendering       │  │ OCR support        │                    │     │
│  │  └────────────────────┘  └────────────────────┘                    │     │
│  │                                                                     │     │
│  │  ┌────────────────────┐  ┌────────────────────┐                    │     │
│  │  │ Redis              │  │ Relay Server       │                    │     │
│  │  │ (Docker container) │  │ (Python daemon)    │                    │     │
│  │  │                    │  │                    │                    │     │
│  │  │ Port: 6380         │  │ Port: 4625         │                    │     │
│  │  │ Protocol: Redis    │  │ Protocol: HTTP/WS  │                    │     │
│  │  │                    │  │                    │                    │     │
│  │  │ For: future task   │  │ For: browser       │                    │     │
│  │  │ queue scaling      │  │ extension comms    │                    │     │
│  │  │ (not currently     │  │ (auto-starts)      │                    │     │
│  │  │ used)              │  │                    │                    │     │
│  │  └────────────────────┘  └────────────────────┘                    │     │
│  └────────────────────────────────────────────────────────────────────┘     │
│                                                                              │
│  ┌────────────────────────────────────────────────────────────────────┐     │
│  │                     EXTERNAL APIs (Optional)                        │     │
│  │                                                                     │     │
│  │  ┌────────────────────┐  ┌────────────────────┐                    │     │
│  │  │ TranscriptAPI.io   │  │ Webshare Proxy     │                    │     │
│  │  │ (Paid API)         │  │ (Optional)         │                    │     │
│  │  │                    │  │                    │                    │     │
│  │  │ Env: TRANSCRIPTAPI │  │ Env: WEBSHARE_USER │                    │     │
│  │  │      _KEY          │  │      WEBSHARE_PASS │                    │     │
│  │  │                    │  │                    │                    │     │
│  │  │ Fallback when free │  │ Rotating proxy for │                    │     │
│  │  │ YouTube transcript │  │ YouTube when IPs   │                    │     │
│  │  │ API fails          │  │ get blocked        │                    │     │
│  │  └────────────────────┘  └────────────────────┘                    │     │
│  └────────────────────────────────────────────────────────────────────┘     │
└─────────────────────────────────────────────────────────────────────────────┘


PORTS & PROTOCOLS SUMMARY:
┌──────────────────┬───────┬──────────┬─────────────────────────────────────────┐
│ Service          │ Port  │ Protocol │ Notes                                   │
├──────────────────┼───────┼──────────┼─────────────────────────────────────────┤
│ Crawl4AI         │ 11235 │ HTTP     │ Docker, optional for webpages           │
│ Docling          │ 5001  │ HTTP     │ Docker, optional for documents          │
│ Redis            │ 6380  │ Redis    │ Docker, reserved for future use         │
│ Relay Server     │ 4625  │ HTTP/WS  │ Local daemon, auto-starts when needed   │
│ MCP Server       │ stdio │ MCP/JSON │ Communicates via stdin/stdout           │
└──────────────────┴───────┴──────────┴─────────────────────────────────────────┘

DOCKER COMPOSE SERVICES (docker-compose.yml):
  - gobbler-crawl4ai  (2GB RAM, 1 CPU)
  - gobbler-docling   (8GB RAM, 4 CPU)
  - gobbler-redis     (512MB RAM, 0.5 CPU)
```

---

## Summary

### Architecture Principles (Current State)

1. **CLI-First Design**: All functionality accessible via `gobbler` CLI
2. **MCP as Thin Wrapper**: MCP tools call CLI via subprocess, avoiding duplication
3. **gobbler_core for Portability**: Converters and providers are standalone
4. **Skills for AI Discoverability**: SKILL.md files teach agents how to use Gobbler
5. **Optional External Services**: Core features work without Docker
6. **Auto-Starting Relay**: Browser automation relay starts on demand

### Key Flows

| Use Case | Entry Point | Core Logic | External Service |
|----------|-------------|------------|------------------|
| YouTube transcript | CLI or MCP | gobbler_core/converters/youtube | YouTube APIs |
| Audio transcription | CLI or MCP | gobbler_core/converters/audio | Local Whisper |
| Web page | CLI or MCP | gobbler_core/converters/webpage | Crawl4AI (Docker) |
| Document | CLI or MCP | gobbler_core/converters/document | Docling (Docker) |
| NotebookLM query | CLI | gobbler_relay + extension | Browser (via WS) |
| Batch processing | CLI or MCP | Concurrent CLI invocations | Various |
