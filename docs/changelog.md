---
icon: material/history
---

# Changelog

All notable changes to this project are tracked in the root [CHANGELOG.md](https://github.com/Enablement-Engineering/gobbler/blob/main/CHANGELOG.md).

## [0.2.0] - 2026-06-16

### Changed

- Reframed Gobbler as a CLI-first, Skills-ready content conversion tool.
- Moved reusable configuration and webpage-selector logic into core modules.
- Updated CI, Dependabot, pre-commit, and PR templates for the CLI-first architecture.
- Added public project hygiene docs: security policy, roadmap, and agent usage guide.

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
