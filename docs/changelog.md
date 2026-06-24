---
icon: material/history
---

# Changelog

All notable changes to this project are tracked in the root [CHANGELOG.md](https://github.com/Enablement-Engineering/gobbler/blob/main/CHANGELOG.md).

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

### Removed

- Retired the legacy server package and duplicate console script.
- Removed docs, examples, tests, and hidden command files for the retired duplicate surface.

## [0.1.0] - 2025-12-05

### Added

- Browser extension integration with tab-group scoping.
- Batch processing for YouTube playlists, webpages, documents, and audio/video directories.
- YouTube transcript extraction and video downloads.
- Web scraping through Crawl4AI.
- Document conversion through Docling.
- Audio/video transcription through Whisper.
- Redis/RQ background queue support.
- CLI-first markdown output with YAML frontmatter.
