---
icon: material/history
---

# Changelog

All notable changes to this project are tracked in the root [CHANGELOG.md](https://github.com/Enablement-Engineering/gobbler/blob/main/CHANGELOG.md).

## [0.2.30] - 2026-07-23

### Fixed

- Canonicalized documented unquoted `fallback.on` configuration keys during loading so `gobbler doctor --json` reports the same effective fallback schema that provider selection consumes.
- Preserved normal YAML boolean values and the existing runtime compatibility path for previously constructed coerced fallback mappings.

## [0.2.29] - 2026-07-22

### Changed

- Updated the supported minimum versions of `aiohttp`, `pytest`, and Ruff.
- Excluded Typer 0.27.0 because that release's wheel omits its public CLI API.

### Fixed

- Replaced stale browser-extension scripts with real relay protocol integration tests covering WebSocket registration, heartbeat, and HTTP-to-WebSocket command round trips.
- Made integration tests run on pull requests and fail CI normally instead of collecting zero tests behind `continue-on-error`.
- Isolated positive webpage E2E cases from ambient proxy configuration by exercising the explicit direct-provider path.

## [0.2.28] - 2026-07-21

### Changed

- Refreshed the supported minimum versions for ten Python dependencies and `actions/setup-python` from the current Dependabot proposals.
- Grouped major, minor, and patch Python dependency updates into one bounded weekly Dependabot PR.

## [0.2.27] - 2026-07-20

### Changed

- Updated the Codecov v7 upload configuration to use its supported plural `files` input.

## [0.2.26] - 2026-07-19

### Added

- Added deterministic YouTube overview, repeatable exact-timestamp, and repeatable inclusive-range JPEG extraction with durable Markdown and JSON manifests.
- Added `--frames-only` refinement that bypasses transcript providers, plus explicit and output-derived frame directories.

### Security

- Sanitized yt-dlp/FFmpeg frame failures so signed stream URLs, URL credentials and private components, query values, fragments, and cookie values cannot enter diagnostics or warnings.

## [0.2.25] - 2026-07-18

### Changed

- Updated every test and security workflow checkout step to `actions/checkout` v7.
- Added a static workflow dependency regression test so checkout major versions cannot drift between jobs.

## [0.2.24] - 2026-07-17

### Changed

- Reconciled installation, CLI, configuration, provider, queue, browser-extension, troubleshooting, contributor, and agent-skill documentation with the current runtime.
- Documented extension-managed tab scope, automatic page-API injection, relay lifecycle, and browser debugger security boundaries.
- Synchronized package and extension release versions and added regression coverage for version drift.

### Fixed

- Made `gobbler config init` use the repository's canonical example in source checkouts.
- Made queued webpage-batch output point to `gobbler jobs get JOB_ID` and the SQLite worker rather than the unrelated legacy daemon wrapper.

## [0.2.23] - 2026-07-17

### Fixed

- Sanitized invalid `gobbler batch youtube-playlist --json` diagnostic URL fields to retain only a validated authority, preventing exposure of userinfo, arbitrary path tokens, query values, fragments, and malformed backslash authorities.

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
