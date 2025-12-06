# Gobbler Architecture - Visual Guide

This document provides comprehensive visual diagrams of Gobbler's architecture, data flows, and component interactions.

## Table of Contents

- [Overall System Architecture](#overall-system-architecture)
- [Data Flow Diagrams](#data-flow-diagrams)
  - [YouTube Transcript Flow](#youtube-transcript-flow)
  - [Web Scraping Flow](#web-scraping-flow)
  - [Document Conversion Flow](#document-conversion-flow)
  - [Audio/Video Transcription Flow](#audiovideo-transcription-flow)
  - [Batch Processing Flow](#batch-processing-flow)
- [Browser Extension Communication](#browser-extension-communication)
- [Background Queue System](#background-queue-system)

## Overall System Architecture

```mermaid
graph TB
    subgraph "Client Layer"
        CC[Claude Code/Desktop<br/>MCP Client]
        BE[Browser Extension<br/>Chrome/Edge]
    end

    subgraph "Host-Based Components"
        MCP[MCP Server<br/>FastMCP + Python]
        YT[YouTube Tools<br/>yt-dlp + API]
        FW[faster-whisper<br/>Metal/CoreML]
        RQ[RQ Worker<br/>Background Tasks]
        CFG[Config Manager<br/>~/.config/gobbler]
        HLT[Health Checker<br/>Service Monitor]
    end

    subgraph "Docker Services"
        C4[Crawl4AI<br/>Port 11235<br/>Web Scraping]
        DL[Docling<br/>Port 5001<br/>Doc Conversion]
        RD[Redis<br/>Port 6380<br/>Job Queue]
    end

    subgraph "External Services"
        YTA[YouTube API<br/>Transcripts]
        WEB[Web Pages<br/>HTTP/HTTPS]
        FS[File System<br/>Output Storage]
    end

    CC <-->|MCP Protocol<br/>JSON-RPC| MCP
    BE <-->|WebSocket<br/>Bidirectional| MCP

    MCP --> CFG
    MCP --> HLT
    MCP --> YT
    MCP --> FW
    MCP -->|HTTP REST| C4
    MCP -->|HTTP REST| DL
    MCP -->|Redis Protocol| RD

    RQ -->|Poll Jobs| RD
    RQ --> YT
    RQ --> FW
    RQ -->|HTTP REST| C4
    RQ -->|HTTP REST| DL

    YT -->|API Calls| YTA
    C4 -->|HTTP/Playwright| WEB

    MCP --> FS
    RQ --> FS

    HLT -.->|Health Check| C4
    HLT -.->|Health Check| DL
    HLT -.->|Health Check| RD

    style MCP fill:#4a9eff,stroke:#333,stroke-width:3px
    style BE fill:#ff9a4a,stroke:#333,stroke-width:2px
    style RD fill:#dc382d,stroke:#333,stroke-width:2px
    style C4 fill:#2ecc71,stroke:#333,stroke-width:2px
    style DL fill:#9b59b6,stroke:#333,stroke-width:2px
    style FS fill:#f39c12,stroke:#333,stroke-width:2px
```

## Data Flow Diagrams

### YouTube Transcript Flow

```mermaid
sequenceDiagram
    participant Claude
    participant MCP as MCP Server
    participant YT as YouTube Tools
    participant API as YouTube API
    participant FS as File System

    Claude->>MCP: transcribe_youtube(url, output_file)
    MCP->>YT: extract_transcript(video_id)
    YT->>API: get_transcript(video_id)
    API-->>YT: transcript_data
    YT->>API: get_video_info(video_id)
    API-->>YT: metadata
    YT->>YT: format_to_markdown()
    YT->>YT: generate_frontmatter()
    YT-->>MCP: markdown + metadata

    alt output_file specified
        MCP->>FS: write_file(output_file)
        FS-->>MCP: file_path
        MCP-->>Claude: Success + file_path
    else return content
        MCP-->>Claude: markdown_content
    end

    Note over MCP,API: < 1 second typical<br/>No Docker required
```

### Web Scraping Flow

```mermaid
sequenceDiagram
    participant Claude
    participant MCP as MCP Server
    participant C4 as Crawl4AI
    participant Web as Target Website
    participant FS as File System

    Claude->>MCP: fetch_webpage(url, selector, session_id)

    alt session_id provided
        MCP->>MCP: load_session(session_id)
        Note over MCP: Load cookies & localStorage
    end

    MCP->>C4: POST /crawl<br/>{url, selector, session}
    C4->>C4: Launch Browser<br/>(Playwright)
    C4->>Web: HTTP Request
    Web-->>C4: HTML + Resources
    C4->>C4: Execute JavaScript<br/>Wait for Content

    alt selector provided
        C4->>C4: Apply CSS/XPath Selector
    end

    C4->>C4: Convert HTML to Markdown
    C4->>C4: Extract Links & Images
    C4-->>MCP: markdown + metadata

    MCP->>MCP: Add YAML Frontmatter

    alt output_file specified
        MCP->>FS: write_file(output_file)
        FS-->>MCP: file_path
        MCP-->>Claude: Success + file_path
    else return content
        MCP-->>Claude: markdown_content
    end

    Note over MCP,Web: 2-10 seconds typical<br/>Requires Crawl4AI Docker
```

### Document Conversion Flow

```mermaid
sequenceDiagram
    participant Claude
    participant MCP as MCP Server
    participant DL as Docling
    participant FS as File System

    Claude->>MCP: convert_document(file_path, enable_ocr)
    MCP->>FS: read_file(file_path)
    FS-->>MCP: file_data

    MCP->>DL: POST /convert<br/>{file_data, ocr: true/false}

    DL->>DL: Detect Document Type<br/>(PDF/DOCX/PPTX/XLSX)

    alt enable_ocr = true
        DL->>DL: OCR Processing<br/>(Tesseract)
        Note over DL: Extract text from images
    end

    DL->>DL: Extract Structure<br/>(Tables, Headings, Lists)
    DL->>DL: Parse Content
    DL->>DL: Convert to Markdown
    DL-->>MCP: markdown + metadata

    MCP->>MCP: Add YAML Frontmatter

    alt output_file specified
        MCP->>FS: write_file(output_file)
        FS-->>MCP: file_path
        MCP-->>Claude: Success + file_path
    else return content
        MCP-->>Claude: markdown_content
    end

    Note over MCP,DL: 5-30 seconds typical<br/>OCR adds overhead<br/>Requires Docling Docker
```

### Audio/Video Transcription Flow

```mermaid
sequenceDiagram
    participant Claude
    participant MCP as MCP Server
    participant Queue as Job Queue Check
    participant RQ as RQ Worker
    participant FW as faster-whisper
    participant FS as File System

    Claude->>MCP: transcribe_audio(file_path, model, auto_queue)

    MCP->>MCP: Estimate Duration<br/>(ffprobe metadata)

    alt auto_queue=true AND duration > 1:45
        MCP->>Queue: enqueue_job(transcription_queue)
        Queue-->>MCP: job_id
        MCP-->>Claude: Queued: job_id + ETA

        Note over RQ: Worker picks up job
        RQ->>FS: read_file(file_path)
        FS-->>RQ: audio_data
        RQ->>FW: transcribe(audio_data, model)
    else immediate execution
        MCP->>FS: read_file(file_path)
        FS-->>MCP: audio_data
        MCP->>FW: transcribe(audio_data, model)
    end

    FW->>FW: Load Model<br/>(tiny/base/small/medium/large)
    FW->>FW: Detect Language<br/>(if auto)
    FW->>FW: Transcribe with Metal/CoreML<br/>(M-series acceleration)
    FW-->>RQ: transcript_data

    RQ->>RQ: Format to Markdown
    RQ->>RQ: Add YAML Frontmatter

    alt output_file specified
        RQ->>FS: write_file(output_file)
        FS-->>RQ: file_path
        RQ->>Queue: update_job(success)
    else return content
        RQ->>Queue: update_job(result)
    end

    Note over Claude,FW: Speed varies by model:<br/>small: 3x real-time<br/>large: 1.25x real-time
```

### Batch Processing Flow

```mermaid
sequenceDiagram
    participant Claude
    participant MCP as MCP Server
    participant Redis
    participant RQ as RQ Worker
    participant Tools as YouTube/Crawl4AI/Whisper
    participant FS as File System

    Claude->>MCP: batch_*_operation(items[], auto_queue)

    MCP->>MCP: Validate Items<br/>Check Limits

    alt auto_queue=true AND items > 10
        MCP->>Redis: create_batch_job(items)
        Redis-->>MCP: batch_id
        MCP-->>Claude: Queued: batch_id

        Note over RQ: Worker starts batch
        RQ->>Redis: get_batch_items(batch_id)
    else immediate execution
        MCP->>MCP: items = batch_items
    end

    loop For each item
        alt skip_existing=true
            RQ->>FS: check_file_exists()
            alt file exists
                RQ->>RQ: Skip item
                RQ->>Redis: update_progress(skipped)
            end
        end

        RQ->>Tools: process_item(item)
        Tools-->>RQ: result

        alt success
            RQ->>FS: write_file(output)
            RQ->>Redis: update_progress(success)
        else failure
            RQ->>Redis: update_progress(failure, error)
        end

        Note over RQ: Respect concurrency limit<br/>Add delay between requests
    end

    RQ->>RQ: Generate Summary Report
    RQ->>Redis: finalize_batch(summary)

    Note over Claude,FS: Real-time progress via<br/>get_batch_progress(batch_id)
```

## Browser Extension Communication

```mermaid
sequenceDiagram
    participant Claude
    participant MCP as MCP Server
    participant WS as WebSocket Server
    participant Ext as Browser Extension
    participant Browser as Chrome/Edge Tab
    participant TG as Tab Group<br/>(Gobbler)

    Note over Ext,TG: Extension manages tab group security

    Claude->>MCP: browser_list_tabs()
    MCP->>WS: list_tabs request
    WS->>Ext: {type: "list_tabs"}
    Ext->>TG: query_tabs(group: "Gobbler")
    TG-->>Ext: tabs[]
    Ext-->>WS: {tabs: [...]}
    WS-->>MCP: tabs_data
    MCP-->>Claude: Tab list with IDs

    Claude->>MCP: browser_execute_script_in_tab(tab_id, script)
    MCP->>WS: execute_script request
    WS->>Ext: {type: "execute", tab_id, script}

    Ext->>TG: verify_tab_in_group(tab_id)

    alt Tab in Gobbler group
        Ext->>Browser: chrome.scripting.executeScript()
        Browser->>Browser: Execute JavaScript
        Browser-->>Ext: result
        Ext-->>WS: {success: true, result}
        WS-->>MCP: execution_result
        MCP-->>Claude: Script output
    else Tab not in group
        Ext-->>WS: {error: "Tab not in Gobbler group"}
        WS-->>MCP: error
        MCP-->>Claude: Security error
    end

    Note over Ext,TG: Security Model:<br/>1. Only tabs in "Gobbler" group<br/>2. User explicitly adds tabs<br/>3. Prevents sensitive data access

    Claude->>MCP: browser_extract_current_page(selector)
    MCP->>WS: extract_page request
    WS->>Ext: {type: "extract", selector}
    Ext->>Browser: Get active tab
    Ext->>TG: verify_tab_in_group()
    Ext->>Browser: document.querySelector(selector).outerHTML
    Browser-->>Ext: html_content
    Ext->>Ext: Convert HTML to Markdown
    Ext-->>WS: {markdown, metadata}
    WS-->>MCP: markdown_data
    MCP->>MCP: Add YAML Frontmatter
    MCP-->>Claude: Markdown with metadata
```

## Background Queue System

```mermaid
graph TB
    subgraph "Job Submission"
        Claude[Claude Code]
        MCP[MCP Server]
        EST[Duration Estimator]
        DEC[Auto-Queue Decision]
    end

    subgraph "Redis Queue"
        Q1[Default Queue]
        Q2[Transcription Queue]
        Q3[Download Queue]
    end

    subgraph "Worker Pool"
        W1[RQ Worker 1]
        W2[RQ Worker 2]
        W3[RQ Worker 3]
    end

    subgraph "Job Processing"
        PROC[Process Job]
        TOOLS[YouTube/Whisper/Crawl4AI]
        FS[File System]
        META[Update Metadata]
    end

    subgraph "Status Tracking"
        STATUS[Job Status]
        PROG[Progress Updates]
        RES[Results Storage]
    end

    Claude -->|Tool Call| MCP
    MCP --> EST
    EST -->|Duration Check| DEC

    DEC -->|< 1:45 min| MCP
    DEC -->|> 1:45 min| Q1
    DEC -->|Transcription| Q2
    DEC -->|Download| Q3

    Q1 -.->|Poll| W1
    Q2 -.->|Poll| W2
    Q3 -.->|Poll| W3

    W1 --> PROC
    W2 --> PROC
    W3 --> PROC

    PROC --> TOOLS
    TOOLS --> FS
    PROC --> META

    META --> STATUS
    META --> PROG
    META --> RES

    STATUS -.->|Query| Claude
    PROG -.->|Query| Claude
    RES -.->|Retrieve| Claude

    style DEC fill:#f39c12,stroke:#333,stroke-width:2px
    style Q1 fill:#dc382d,stroke:#333,stroke-width:2px
    style Q2 fill:#dc382d,stroke:#333,stroke-width:2px
    style Q3 fill:#dc382d,stroke:#333,stroke-width:2px
    style PROC fill:#2ecc71,stroke:#333,stroke-width:2px
```

### Queue Job Lifecycle

```mermaid
stateDiagram-v2
    [*] --> Submitted: Tool call with auto_queue

    Submitted --> Queued: Add to Redis queue
    Queued --> Started: Worker picks up job

    Started --> Processing: Execute tool logic
    Processing --> Processing: Update progress

    Processing --> Completed: Success
    Processing --> Failed: Error occurred
    Processing --> Cancelled: User cancellation

    Completed --> [*]
    Failed --> [*]
    Cancelled --> [*]

    note right of Queued
        Job ID returned to Claude
        ETA calculated
    end note

    note right of Processing
        Progress updates stored
        Real-time tracking via
        get_job_status()
    end note

    note right of Completed
        Result stored
        File written
        Metadata saved
    end note
```

## Component Responsibilities

### MCP Server
- Handle MCP protocol communication with Claude clients
- Route tool calls to appropriate converters
- Manage configuration and health checking
- Coordinate between services
- Handle auto-queue decisions

### Browser Extension
- Maintain WebSocket connection to MCP server
- Enforce tab group security model
- Execute scripts in managed tabs
- Extract page content and convert to markdown
- Provide tab management UI

### RQ Worker
- Poll Redis queues for background jobs
- Execute long-running tasks
- Update job progress and status
- Handle retries and error reporting
- Write results to file system

### Docker Services
- **Crawl4AI**: Web scraping with JavaScript rendering
- **Docling**: Document conversion with OCR
- **Redis**: Job queue and state management

### Converters
- **YouTube Tools**: Transcript extraction and video downloads
- **faster-whisper**: Audio/video transcription with Metal acceleration
- **Webpage Converter**: HTML to markdown conversion
- **Document Converter**: Multi-format document processing

## Performance Characteristics

| Operation | Typical Duration | Requires Docker | Auto-Queue Eligible |
|-----------|-----------------|-----------------|---------------------|
| YouTube Transcript | < 1 second | No | No |
| Web Scraping | 2-10 seconds | Yes (Crawl4AI) | No |
| Document Conversion | 5-30 seconds | Yes (Docling) | Yes (if > 1:45) |
| Audio Transcription (small) | 3x real-time | No | Yes (if > 35 sec) |
| Video Download | Varies by size | No | Yes (always) |
| Batch Processing | Minutes-hours | Varies | Yes (if > 10 items) |

## Security Model

### Tab Group Security
1. Browser extension creates "Gobbler" tab group on first use
2. Only tabs explicitly added to group are accessible
3. All browser commands verify tab group membership
4. User controls which tabs Claude can access
5. Prevents accidental exposure of sensitive information

### Service Isolation
1. Docker services run in isolated containers
2. Host-based components use local-only connections
3. Redis queue isolated to localhost:6380
4. No external network access except for intended APIs
5. Configuration stored in user-specific directory

### API Security
1. Crawl4AI uses local API token
2. No cloud service credentials required
3. All processing happens locally
4. YouTube uses official public API
5. No data sent to external services except source URLs
