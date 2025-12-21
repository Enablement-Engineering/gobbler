# Gobbler MCP - Documentation

This directory contains documentation for Gobbler MCP.

## Quick Links

- **[SKILLS.md](SKILLS.md)** - Claude Code Skills that bypass MCP (YouTube, Webpage, Document, Audio, Browser)
- **[QUICK_START.md](QUICK_START.md)** - Getting started guide
- **[ARCHITECTURE-VISUAL.md](ARCHITECTURE-VISUAL.md)** - System architecture diagrams

## Product Requirements Documents (PRDs)

This directory also contains all Product Requirements Documents for Gobbler MCP.

## PRD Status Tracking

### PRD-001: Testing Infrastructure ✅
**Status**: Complete
**Completed**: 2025-10-03
**Effort**: 3-4 days
**Dependencies**: None

**Summary**: Comprehensive testing infrastructure with unit tests, integration tests, benchmarks, and CI/CD pipeline.

**Deliverables Completed**:
- ✅ Test directory structure (`tests/unit/`, `tests/integration/`, `tests/benchmarks/`, `tests/e2e/`)
- ✅ `conftest.py` with shared fixtures and mocks
- ✅ Unit tests for converters (YouTube, audio, webpage, document)
- ✅ Unit tests for utilities (frontmatter, config, file_handler)
- ✅ Integration test structure (Redis queue, Crawl4AI service)
- ✅ Performance benchmarks (Whisper transcription baselines)
- ✅ GitHub Actions CI/CD workflow (`.github/workflows/test.yml`)
- ✅ Coverage configuration in `pyproject.toml`
- ✅ Test dependencies added (`pytest`, `pytest-asyncio`, `pytest-cov`, `pytest-mock`, `pytest-benchmark`, `pytest-httpx`, `fakeredis`)

**Test Results**:
- ✅ 72 tests passing
- ✅ 38%+ overall coverage (90%+ on tested modules)
- ✅ YouTube converter: 96.72% coverage
- ✅ Audio converter: 90.57% coverage
- ✅ Config: 92.31% coverage
- ✅ File handler: 92.31% coverage
- ✅ Frontmatter: 97.62% coverage

**CI/CD**:
- ✅ Multi-Python version testing (3.11, 3.12, 3.13)
- ✅ Unit tests run on every PR
- ✅ Integration tests run on main branch
- ✅ Code quality checks (ruff, mypy)
- ✅ Coverage reporting configured

**Documentation**:
- ✅ README updated with testing commands
- ✅ Test structure documented
- ✅ Coverage targets defined

---

### PRD-002: Batch Processing ✅
**Status**: Complete
**Completed**: 2025-10-03
**Effort**: 4-5 days
**Dependencies**: PRD-001 (Testing Infrastructure)

**Summary**: Batch processing system for handling multiple items with progress tracking.

**Deliverables Completed**:
- ✅ Batch core module (`src/gobbler_mcp/batch/`)
- ✅ Data models (BatchItem, BatchResult, BatchSummary)
- ✅ Progress tracker with Redis integration
- ✅ Batch manager with concurrency control (asyncio.Semaphore)
- ✅ YouTube playlist batch processor
- ✅ Webpage batch processor
- ✅ File directory batch processors (audio, documents)
- ✅ 5 new MCP tools (batch_transcribe_youtube_playlist, batch_fetch_webpages, batch_transcribe_directory, batch_convert_documents, get_batch_progress)
- ✅ Auto-queue support (>10 items)
- ✅ Numeric suffix for duplicate filenames
- ✅ 16 unit tests (88 total tests passing)
- ✅ README documentation updated

**Features**:
- Process YouTube playlists (up to 500 videos)
- Batch web scraping (up to 100 URLs)
- Directory transcription (audio/video files)
- Directory document conversion (PDF, DOCX, etc.)
- Real-time progress tracking via Redis
- Configurable concurrency limits
- Skip existing files option
- Partial failure handling (continue on error)
- Auto-queue for large batches (>10 items)

**Test Results**:
- ✅ 88 tests passing (72 original + 16 new)
- ✅ Zero regressions
- ✅ Batch models: 100% coverage
- ✅ Batch manager: 77% coverage

**Blocks**: None

---

### PRD-003: Advanced Crawl4AI Integration ✅
**Status**: Complete
**Completed**: 2025-10-03
**Effort**: 3-4 days
**Dependencies**: PRD-001 (Testing Infrastructure)

**Summary**: Enhanced web scraping with CSS/XPath selectors, session management, and recursive site crawling.

**Deliverables Completed**:
- ✅ Selector-based extraction (`src/gobbler_mcp/converters/webpage_selector.py` - 153 lines, 90% coverage)
- ✅ Session management (`src/gobbler_mcp/crawlers/session_manager.py` - 72 lines)
- ✅ Site crawler with BFS (`src/gobbler_mcp/crawlers/site_crawler.py` - 90 lines)
- ✅ Link extraction & categorization (internal/external)
- ✅ Robots.txt respect & polite crawling
- ✅ 3 new MCP tools (fetch_webpage_with_selector, create_crawl_session, crawl_site)
- ✅ BeautifulSoup4 dependency added
- ✅ 11 unit tests passing
- ✅ README documentation updated

**Features Implemented**:
- CSS selector extraction (e.g., `css_selector="article.main"`)
- XPath selector extraction (e.g., `xpath="//article[@class='main']"`)
- Session persistence to `~/.config/gobbler/sessions/`
- Cookie and localStorage support
- Recursive site crawling with depth control (max: 5)
- URL pattern filtering (include/exclude regex)
- Link graph generation
- Concurrent crawling with semaphore control (max: 10)
- Polite crawling delays (default: 1.0s)

**Blocks**: None

---

### PRD-004: Monitoring & Observability ✅
**Status**: Complete (Core Implementation)
**Completed**: 2025-10-03
**Dependencies**: PRD-001 (Testing Infrastructure), PRD-002 (Batch Processing)
**Effort**: 3-4 days

**Summary**: Production-ready monitoring infrastructure with Prometheus metrics, structured logging, and HTTP metrics endpoint.

**Deliverables Completed**:
- ✅ `src/gobbler_mcp/logging_config.py` - Structured logging (JSON/text modes)
- ✅ `src/gobbler_mcp/metrics.py` - 11 Prometheus metrics defined
- ✅ `src/gobbler_mcp/metrics_server.py` - HTTP server (/metrics on port 9090)
- ✅ `src/gobbler_mcp/config.py` - Monitoring configuration section
- ✅ All 4 converters instrumented (youtube, audio, webpage, document)
- ✅ Integrated with server.py lifespan
- ✅ 24 tests passing (17 unit + 7 integration)

**Features Implemented**:
- Prometheus metrics collection (conversions, queues, resources, errors)
- Structured JSON logging with extra fields
- Metrics HTTP endpoint (/metrics, /health)
- Config-driven monitoring (disabled by default)
- MCP stdio protocol compatibility
- Background thread metrics server (no event loop conflicts)

**Optional (Phase 4-5 - Future Work)**:
- Health monitor for continuous service checking
- Queue/worker metrics integration
- Grafana dashboards
- Docker Compose monitoring stack
- Monitoring documentation

**Test Results**:
- ✅ 24/24 tests passing
- ✅ Zero overhead when disabled
- ✅ MCP stdio compatibility verified

**Blocks**: None

---

### PRD-005: Hot-Reload Configuration
**Status**: Pending
**Dependencies**: PRD-001 (Testing Infrastructure)
**Effort**: 2-3 days

**Blocks**: None

---

### PRD-006: Advanced Docling Integration 🆕
**Status**: Pending
**Dependencies**: PRD-001 (Testing Infrastructure), Docling service
**Effort**: 5-7 days

**Summary**: Deep integration with Docling's capabilities beyond basic markdown conversion. Includes structured document output, RAG-optimized chunking, schema-based extraction, table intelligence, and advanced pipeline options.

**Planned Deliverables**:
- [ ] Structured document output (DoclingDocument with tables, images, sections)
- [ ] RAG-optimized chunking (hierarchical + hybrid strategies, tokenizer integration)
- [ ] Schema-based extraction (JSON Schema, TypeScript, or example-based)
- [ ] Table-specific extraction (DataFrame, CSV, JSON output)
- [ ] Advanced pipeline selection (standard, VLM, fast)
- [ ] Image classification and VLM captioning
- [ ] PII detection and redaction mode
- [ ] Visual grounding with bounding boxes for citations

**New MCP Tools**:
- `convert_document` (enhanced with `output_format` param)
- `chunk_document` - RAG-optimized chunking
- `extract_structured_data` - Schema-based extraction
- `extract_tables` - Table-specific extraction
- `convert_document_advanced` - Full pipeline control

**Inspiration**: [Cloudflare Code Mode](https://blog.cloudflare.com/code-mode/) - LLMs are better at writing code than making tool calls.

**Blocks**: None

---

### PRD-011: Eliminate Package Duplication 🆕
**Status**: Pending
**Dependencies**: None
**Effort**: 2-3 days
**Priority**: High

**Summary**: Remove ~900 lines of identical code duplicated between gobbler_core and gobbler_mcp packages. Files like frontmatter.py, file_handler.py, audio.py are 100% identical in both packages. Also addresses unused exceptions.py (113 lines).

**Key Deliverables**:
- [ ] Delete duplicate files from gobbler_mcp (use re-exports instead)
- [ ] Update gobbler_relay to import from gobbler_core
- [ ] Address unused exceptions.py (remove or integrate)
- [ ] Fix pyproject.toml isort configuration

**Impact**: ~1,000 lines of code removed, cleaner architecture

---

### PRD-012: Test Coverage Expansion 🆕
**Status**: Pending
**Dependencies**: PRD-001 (Testing Infrastructure)
**Effort**: 5-7 days
**Priority**: High

**Summary**: Expand test coverage from ~40% to 70%+. Critical modules like relay.py (850 lines), browser.py (282 lines), and crawl.py (389 lines) have zero tests.

**Key Deliverables**:
- [ ] Add tests for relay server (~25 tests)
- [ ] Add tests for browser tools (~15 tests)
- [ ] Add tests for crawl tools (~20 tests)
- [ ] Fix test isolation (global state leaking)
- [ ] Establish E2E test framework
- [ ] Fix benchmark tests to actually benchmark

**Impact**: 100+ new tests, 70%+ coverage

---

### PRD-013: Documentation Improvements 🆕
**Status**: Pending
**Dependencies**: None
**Effort**: 2-3 days
**Priority**: Medium

**Summary**: Complete API.md (missing 15+ tools), comprehensive config.example.yml, gobbler_core README, and fix type hint documentation.

**Key Deliverables**:
- [ ] Document all 25+ MCP tools in API.md
- [ ] Complete config.example.yml (redis, queue, monitoring, relay)
- [ ] Create gobbler_core package README
- [ ] Standardize SKILL.md format with versions
- [ ] Fix type hints (str = None -> Optional[str])

**Impact**: Complete documentation for all features

---

### PRD-014: Skills Architecture Consolidation 🆕
**Status**: Pending
**Dependencies**: PRD-011 (Eliminate Package Duplication)
**Effort**: 3-4 days
**Priority**: Medium

**Summary**: Consolidate duplicate NotebookLM scripts, remove hardcoded paths, fix skill dependencies on gobbler_mcp, standardize shebangs.

**Key Deliverables**:
- [ ] Consolidate duplicate notebooklm.py scripts
- [ ] Remove hardcoded path from sandbox_bridge.py
- [ ] Fix gobbler-youtube to use gobbler_core
- [ ] Standardize shebang across all skills
- [ ] Relocate skill tests to central location

**Impact**: Cleaner skill architecture, no duplicate code

---

### PRD-015: Project Configuration Improvements 🆕
**Status**: Pending
**Dependencies**: None
**Effort**: 1-2 days
**Priority**: Medium

**Summary**: Fix Python version mismatch (3.10 vs 3.11), enable CI type checking, add security scanning, complete .env.example.

**Key Deliverables**:
- [ ] Fix Python version to 3.11 in mypy/ruff
- [ ] Remove continue-on-error from CI type checking
- [ ] Add security scanning workflow (CodeQL, Dependabot)
- [ ] Complete .env.example with all variables
- [ ] Secure default API tokens

**Impact**: Reliable CI, security scanning, better DX

---

## Execution Notes

### Phase 1: Foundation ✅
**Status**: Complete

PRD-001 established the testing foundation that all other PRDs depend on. With comprehensive test coverage, mocking infrastructure, and CI/CD in place, future development can proceed with confidence.

**Key Achievements**:
- Zero external dependencies for unit tests (all mocked)
- Fast test execution (< 1 second for all unit tests)
- Comprehensive mock fixtures for YouTube API, Whisper, Crawl4AI, Redis
- Integration test structure ready for Docker service testing
- Performance baseline documentation

---

### Phase 2: Feature Enhancement ✅
**Status**: In Progress (PRD-002 Complete)

PRD-002 introduced batch processing capabilities, enabling users to process multiple items efficiently with progress tracking and concurrency control.

**Key Achievements**:
- Generic batch processing framework (BatchProcessor, ProgressTracker)
- 5 new MCP tools for batch operations
- Redis-based progress tracking with 24-hour retention
- Auto-queue support for large batches (>10 items)
- Concurrency control with asyncio.Semaphore
- Partial failure handling (continue on error)
- Duplicate filename handling with numeric suffixes
- 16 new unit tests, 88 total tests passing
- Zero regressions from original 72 tests

**Architecture Decisions**:
- Reused existing single-item converters (no code duplication)
- Used native Python asyncio for concurrency (no additional dependencies)
- Redis for progress tracking (leveraged existing queue infrastructure)
- Generic BatchProcessor supports multiple use cases

**Next Steps**:
- PRD-003: Advanced Crawl4AI Integration
- PRD-004: Monitoring & Observability (depends on PRD-002)
- PRD-005: Hot-Reload Configuration

---

## How to Use This Document

1. **Before starting a PRD**: Review dependencies and verify all are marked complete (✅)
2. **During development**: Update status to "In Progress 🚧" and track deliverables
3. **After completion**: Mark complete (✅), document completion date, and note any deviations
4. **Track blockers**: If blocked, add "Blocked ⚠️" and document blocker details

---

## PRD Template

When adding new PRDs, follow this structure:

```markdown
### PRD-XXX: Title [✅/🚧/⚠️/Pending]
**Status**: [Pending/In Progress/Complete/Blocked]
**Completed**: YYYY-MM-DD (if complete)
**Started**: YYYY-MM-DD (if in progress)
**Effort**: X-Y days
**Dependencies**: PRD-XXX, PRD-YYY
**Blocks**: PRD-ZZZ (if applicable)

**Summary**: Brief description

**Deliverables**: List of files/features to create
```

---

Last Updated: 2025-12-19
