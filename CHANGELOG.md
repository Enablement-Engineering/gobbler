# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.2.3] - 2026-06-21

### Fixed
- Added `--proxy/--no-proxy` to `gobbler batch webpages` so batch webpage conversion can bypass configured Crawl4AI proxy settings when needed.

## [0.2.2] - 2026-06-20

### Fixed
- Rejected malformed or schemeless `gobbler webpage` URLs locally before dispatching to the webpage provider.
- Added a stable `WEBPAGE_INVALID_URL` JSON error code for invalid single-webpage inputs.

## [0.2.1] - 2026-06-19

### Added
- Agent-friendly `gobbler doctor --json` diagnostics with redacted config, local tool checks, service status, and next actions.
- Consolidated `gobbler` skill for convert/extract/transcribe/archive-to-markdown workflows, with detailed references for YouTube, audio, document, webpage, and batch recipes.
- Unified public skill language around CLI-capable AI agents and documented `npx skills@latest add Enablement-Engineering/gobbler` as the recommended skill-install path.
- Agent usage guide for CLI-capable automation workflows.
- `SECURITY.md` for public project hygiene.
- README project status, badges, and release-prep trust signals.

### Changed
- Cleaned up public documentation examples to remove stale local paths and repository references.

### Fixed
- Prevented `gobbler batch directory` from overwriting outputs when selected inputs share a stem but have different extensions.

## [0.2.0] - 2026-06-16

### Changed
- Reframed Gobbler as a CLI-first, Skills-ready content conversion tool.
- Moved reusable configuration and webpage-selector logic into core modules.
- Updated CI, Dependabot, pre-commit, and PR templates for the CLI-first architecture.
- Improved README and docs around current supported interfaces.

### Removed
- Retired the legacy server package and duplicate console script.
- Removed docs, examples, tests, and hidden command files for the retired duplicate surface.

## [0.1.0] - 2025-12-05

### Added
- **Browser Extension Integration**
  - Bidirectional communication with Chrome/Edge via WebSocket
  - Tab group security model (only access tabs in "Gobbler" group)
  - Multi-tab support with tab-specific script execution
  - Live page extraction and browser automation capabilities

- **Batch Processing System**
  - YouTube playlist batch transcription with rate limiting
  - Batch webpage conversion with concurrency control
  - Directory-based audio/video transcription
  - Directory-based document conversion
  - Real-time progress tracking for batch operations

- **YouTube Features**
  - Transcript extraction using official YouTube API
  - Video downloads with quality selection
  - Playlist support with metadata extraction
  - Auto-queue for long downloads

- **Web Scraping**
  - JavaScript-rendered content support via Crawl4AI
  - CSS and XPath selector-based extraction
  - Rate limiting and robots.txt respect

- **Document Conversion**
  - PDF, DOCX, PPTX, XLSX to markdown conversion via Docling
  - OCR support for scanned documents
  - Batch directory conversion
  - Structure preservation (tables, headings, lists)

- **Audio/Video Transcription**
  - Local Whisper transcription with Metal/CoreML acceleration (M-series Macs)
  - Multiple model sizes (tiny, base, small, medium, large)
  - Auto-language detection

- **Background Queue System**
  - Redis + RQ-based job queue for long-running tasks
  - Auto-queue feature for tasks estimated longer than a short interactive run
  - Separate queues: default, transcription, download
  - Job status tracking and progress monitoring

- **Core Features**
  - CLI-first conversion workflow
  - YAML frontmatter + markdown output for all conversions
  - Comprehensive metadata preservation
  - Health checking for all services
  - Configuration management via `~/.config/gobbler/config.yml`
  - Makefile commands for easy service management

- **Developer Experience**
  - Unit, integration, and benchmark test structure
  - GitHub Actions CI/CD pipeline
  - Code quality tools including Ruff and mypy
  - Documentation and browser extension setup guides

[Unreleased]: https://github.com/Enablement-Engineering/gobbler/compare/v0.2.3...HEAD
[0.2.3]: https://github.com/Enablement-Engineering/gobbler/compare/v0.2.2...v0.2.3
[0.2.2]: https://github.com/Enablement-Engineering/gobbler/compare/v0.2.1...v0.2.2
[0.2.1]: https://github.com/Enablement-Engineering/gobbler/compare/v0.2.0...v0.2.1
[0.2.0]: https://github.com/Enablement-Engineering/gobbler/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/Enablement-Engineering/gobbler/releases/tag/v0.1.0
