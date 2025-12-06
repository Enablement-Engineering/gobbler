# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Visual architecture diagrams in README and docs/ARCHITECTURE-VISUAL.md
- Trust signal badges (Python version, CI status, code style)
- "What's New" section highlighting recent features
- Verify installation step in Quick Start guide

## [0.1.0] - 2025-12-05

### Added
- **Browser Extension Integration**
  - Bidirectional communication with Chrome/Edge via WebSocket
  - Tab group security model (only access tabs in "Gobbler" group)
  - Multi-tab support with tab-specific script execution
  - Live page extraction and browser automation capabilities
  - Tools: `browser_check_connection`, `browser_list_tabs`, `browser_execute_script_in_tab`, `browser_navigate_to_url`, `browser_execute_script`, `browser_extract_current_page`

- **Batch Processing System**
  - YouTube playlist batch transcription with rate limiting
  - Batch webpage conversion with concurrency control
  - Directory-based audio/video transcription
  - Directory-based document conversion
  - Real-time progress tracking for batch operations
  - Tools: `batch_transcribe_youtube_playlist`, `batch_fetch_webpages`, `batch_transcribe_directory`, `batch_convert_documents`, `get_batch_progress`

- **YouTube Features**
  - Transcript extraction using official YouTube API
  - Video downloads with quality selection (best, 1080p, 720p, 480p, 360p)
  - Playlist support with metadata extraction
  - Auto-queue for long downloads
  - Tools: `transcribe_youtube`, `download_youtube_video`

- **Web Scraping**
  - JavaScript-rendered content support via Crawl4AI
  - CSS and XPath selector-based extraction
  - Authenticated crawling with session management
  - Recursive site crawling with link graph generation
  - Rate limiting and robots.txt respect
  - Tools: `fetch_webpage`, `fetch_webpage_with_selector`, `create_crawl_session`, `crawl_site`

- **Document Conversion**
  - PDF, DOCX, PPTX, XLSX to markdown conversion via Docling
  - OCR support for scanned documents
  - Batch directory conversion
  - Structure preservation (tables, headings, lists)
  - Tools: `convert_document`

- **Audio/Video Transcription**
  - Local Whisper transcription with Metal/CoreML acceleration (M-series Macs)
  - Multiple model sizes (tiny, base, small, medium, large)
  - Auto-language detection
  - Performance: 1.25x-6.7x faster than real-time depending on model
  - Tools: `transcribe_audio`

- **Background Queue System**
  - Redis + RQ-based job queue for long-running tasks
  - Auto-queue feature for tasks estimated > 1:45
  - Separate queues: default, transcription, download
  - Job status tracking and progress monitoring
  - Tools: `get_job_status`, `list_jobs`

- **Core Features**
  - MCP server implementation using FastMCP framework
  - YAML frontmatter + markdown output for all conversions
  - Comprehensive metadata preservation
  - Health checking for all services
  - Configuration management via ~/.config/gobbler/config.yml
  - Makefile commands for easy service management

- **Developer Experience**
  - Comprehensive test suite (72+ unit tests, integration tests, benchmarks)
  - GitHub Actions CI/CD pipeline
  - Code quality tools (ruff, mypy)
  - MCP Inspector support for testing
  - Custom slash commands for advanced workflows
  - Detailed documentation and architecture guides

### Infrastructure
- Docker Compose orchestration for services
- Hybrid architecture (host-based + Docker services)
- Port configuration to avoid conflicts (Redis: 6380, Crawl4AI: 11235, Docling: 5001)
- uv-based Python dependency management
- Support for Python 3.11, 3.12, 3.13

### Documentation
- Comprehensive README with tool documentation
- Architecture documentation
- Browser extension setup guide
- Custom slash command documentation
- Troubleshooting guide
- Development setup instructions

[Unreleased]: https://github.com/Enablement-Engineering/gobbler/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/Enablement-Engineering/gobbler/releases/tag/v0.1.0
