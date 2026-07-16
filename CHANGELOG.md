# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.2.22] - 2026-07-16

### Fixed
- Sanitized invalid single-video `gobbler youtube --format json` diagnostic sources so URLs do not expose userinfo, query values, or fragments.

## [0.2.21] - 2026-07-09

### Fixed
- Sanitized top-level `gobbler webpage --format json` failure `source` values so credential-bearing URLs do not expose userinfo, query values, or fragments in automation logs.

## [0.2.20] - 2026-07-08

### Fixed
- Made queued `gobbler batch webpages` human output point to the existing `gobbler daemon status` progress command instead of the removed `gobbler queue status` command.

## [0.2.19] - 2026-07-06

### Fixed
- Made `gobbler webpage --format json` promote provider-specific diagnostic advice, such as safe `--no-proxy` Crawl4AI retry guidance, into the top-level `suggestion` field instead of falling back to generic service-start advice.

## [0.2.18] - 2026-07-05

### Fixed
- Made TranscriptAPI fallback billing/active-plan failures return stable `YOUTUBE_TRANSCRIPTAPI_BILLING_REQUIRED` JSON diagnostics with account-actionable guidance instead of generic YouTube retry/proxy advice.

## [0.2.17] - 2026-07-04

### Fixed
- Made queued `gobbler batch webpages --json` submissions emit parseable job and queue-error JSON instead of human progress text, including stdin, missing-file, empty-input, and queue-failure boundary cases.

## [0.2.16] - 2026-07-03

### Fixed
- Made `gobbler batch youtube-playlist` reject malformed or schemeless playlist URLs locally before invoking `yt-dlp`, returning stable `YOUTUBE_PLAYLIST_INVALID_URL` JSON diagnostics with URL-format guidance.

## [0.2.15] - 2026-07-02

### Fixed
- Made `gobbler youtube` reject invalid single-video URLs locally before conversion, returning stable `YOUTUBE_INVALID_URL` JSON diagnostics with URL-format guidance.

## [0.2.14] - 2026-07-01

### Fixed
- Made `gobbler batch webpages` plan collision-safe output filenames for duplicate or same-stem URLs across dry-run, inline execution, and queued jobs.

## [0.2.13] - 2026-06-30

### Fixed
- Made `gobbler status --json` exit nonzero when the reported overall status is degraded while preserving the JSON response body for automation consumers.

## [0.2.12] - 2026-06-29

### Fixed
- Made `gobbler status --json` surface proxy-bypass Crawl4AI probe guidance in the top-level webpage `fix` field when the detailed probe diagnostic includes a safe `--no-proxy` retry command.

## [0.2.11] - 2026-06-28

### Fixed
- Made `gobbler batch webpages` reject malformed, schemeless, unsupported-scheme, whitespace/control-character, and invalid-port URLs locally before dry-run planning or provider dispatch.

## [0.2.10] - 2026-06-27

### Fixed
- Added sanitized `--no-proxy` retry guidance to proxy-configured Crawl4AI status/readiness probe failures for public URLs.

## [0.2.9] - 2026-06-26

### Fixed
- Neutralized GitHub-style `@login` mentions in generated markdown/frontmatter output so pasted third-party transcripts, descriptions, pages, documents, or audio transcripts do not notify unrelated GitHub users.

## [0.2.8] - 2026-06-26

### Fixed
- Made `gobbler youtube` construct its default transcript provider from the loaded Gobbler config so configured YouTube provider and fallback readiness match runtime conversion behavior.

## [0.2.7] - 2026-06-25

### Added
- Added YouTube fallback readiness diagnostics to `gobbler status`, including fallback provider, trigger conditions, and whether `TRANSCRIPTAPI_KEY` is visible to the running process.

## [0.2.6] - 2026-06-24

### Fixed
- Refined Crawl4AI proxy diagnostics so localhost and loopback navigation failures do not suggest `--no-proxy`, while public proxy-path failures keep sanitized retry guidance.

## [0.2.5] - 2026-06-23

### Fixed
- Suppressed internal retry-client traceback logging for final handled HTTP status failures while preserving retry warnings and unexpected-error tracebacks.

## [0.2.4] - 2026-06-22

### Fixed
- Added actionable `--no-proxy` retry guidance to proxy-configured Crawl4AI conversion diagnostics without exposing credentials.

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

[Unreleased]: https://github.com/Enablement-Engineering/gobbler/compare/v0.2.22...HEAD
[0.2.22]: https://github.com/Enablement-Engineering/gobbler/compare/v0.2.21...v0.2.22
[0.2.21]: https://github.com/Enablement-Engineering/gobbler/compare/v0.2.20...v0.2.21
[0.2.20]: https://github.com/Enablement-Engineering/gobbler/compare/v0.2.19...v0.2.20
[0.2.19]: https://github.com/Enablement-Engineering/gobbler/compare/v0.2.18...v0.2.19
[0.2.18]: https://github.com/Enablement-Engineering/gobbler/compare/v0.2.17...v0.2.18
[0.2.17]: https://github.com/Enablement-Engineering/gobbler/compare/v0.2.16...v0.2.17
[0.2.16]: https://github.com/Enablement-Engineering/gobbler/compare/v0.2.15...v0.2.16
[0.2.15]: https://github.com/Enablement-Engineering/gobbler/compare/v0.2.14...v0.2.15
[0.2.14]: https://github.com/Enablement-Engineering/gobbler/compare/v0.2.13...v0.2.14
[0.2.13]: https://github.com/Enablement-Engineering/gobbler/compare/v0.2.12...v0.2.13
[0.2.12]: https://github.com/Enablement-Engineering/gobbler/compare/v0.2.11...v0.2.12
[0.2.11]: https://github.com/Enablement-Engineering/gobbler/compare/v0.2.10...v0.2.11
[0.2.10]: https://github.com/Enablement-Engineering/gobbler/compare/v0.2.9...v0.2.10
[0.2.9]: https://github.com/Enablement-Engineering/gobbler/compare/v0.2.8...v0.2.9
[0.2.8]: https://github.com/Enablement-Engineering/gobbler/compare/v0.2.7...v0.2.8
[0.2.7]: https://github.com/Enablement-Engineering/gobbler/compare/v0.2.6...v0.2.7
[0.2.6]: https://github.com/Enablement-Engineering/gobbler/compare/v0.2.5...v0.2.6
[0.2.5]: https://github.com/Enablement-Engineering/gobbler/compare/v0.2.4...v0.2.5
[0.2.4]: https://github.com/Enablement-Engineering/gobbler/compare/v0.2.3...v0.2.4
[0.2.3]: https://github.com/Enablement-Engineering/gobbler/compare/v0.2.2...v0.2.3
[0.2.2]: https://github.com/Enablement-Engineering/gobbler/compare/v0.2.1...v0.2.2
[0.2.1]: https://github.com/Enablement-Engineering/gobbler/compare/v0.2.0...v0.2.1
[0.2.0]: https://github.com/Enablement-Engineering/gobbler/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/Enablement-Engineering/gobbler/releases/tag/v0.1.0
