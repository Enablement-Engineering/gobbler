# PRD-012: Test Coverage Expansion

## Overview
**Epic**: Code Quality & Maintainability  
**Phase**: Testing Infrastructure  
**Status**: Pending  
**Effort**: 5-7 days  
**Dependencies**: PRD-001 (Testing Infrastructure)  
**Priority**: High  

## Problem Statement

The codebase has **~40-50% test coverage** with major gaps in critical components:

| Module | Lines | Tests | Priority |
|--------|-------|-------|----------|
| `gobbler_relay/relay.py` | 850 | 0 | **CRITICAL** |
| `gobbler_mcp/tools/browser.py` | 282 | 0 | **CRITICAL** |
| `gobbler_mcp/tools/crawl.py` | 389 | 0 | **CRITICAL** |
| `gobbler_mcp/crawlers/site_crawler.py` | 208 | 0 | **HIGH** |
| `gobbler_mcp/crawlers/session_manager.py` | ~150 | 0 | **HIGH** |
| `gobbler_mcp/utils/queue.py` | ~200 | 0 | **MEDIUM** |
| `gobbler_mcp/batch/youtube_batch.py` | ~150 | 0 | **MEDIUM** |
| `gobbler_mcp/batch/webpage_batch.py` | ~190 | 0 | **MEDIUM** |
| `gobbler_mcp/server.py` | 141 | 0 | **MEDIUM** |

**Total untested code: ~2,500+ lines in critical paths**

### Additional Issues

1. **E2E tests are empty**: `tests/e2e/__init__.py` contains only a docstring
2. **Benchmark tests are stubs**: Most benchmarks just `assert True`
3. **Integration tests skip functionality**: `test_redis_queue.py` has `pytest.skip()` markers
4. **Global state not properly reset**: Whisper model cache, metrics, config singleton leak between tests

## Success Criteria

- [ ] Test coverage increased from ~40% to 70%+
- [ ] All critical modules (relay, browser, crawl) have unit tests
- [ ] E2E test framework established with at least 5 automated tests
- [ ] Benchmark tests actually measure performance
- [ ] Global state properly isolated between tests
- [ ] CI passes with no skipped tests in unit suite

## Technical Requirements

### 1. Relay Server Tests (`tests/unit/test_relay_server.py`)

Test the WebSocket relay server that bridges browser extension to MCP:

```python
"""Unit tests for gobbler_relay server."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

@pytest.fixture
def mock_websocket():
    """Mock WebSocket connection."""
    ws = AsyncMock()
    ws.send = AsyncMock()
    ws.recv = AsyncMock()
    ws.close = AsyncMock()
    return ws

class TestWebSocketHandler:
    """Test WebSocket message handling."""
    
    async def test_extract_command_returns_markdown(self, mock_websocket):
        """Test extract command returns markdown content."""
        pass  # Implementation
    
    async def test_navigate_command_sends_to_extension(self, mock_websocket):
        """Test navigate command is forwarded to extension."""
        pass
    
    async def test_execute_script_with_timeout(self, mock_websocket):
        """Test script execution respects timeout."""
        pass
    
    async def test_invalid_command_returns_error(self, mock_websocket):
        """Test unknown command returns proper error."""
        pass

class TestPidfileManagement:
    """Test PID file creation and cleanup."""
    
    def test_pidfile_created_on_start(self, tmp_path):
        """Test PID file is created when server starts."""
        pass
    
    def test_pidfile_removed_on_shutdown(self, tmp_path):
        """Test PID file is removed on clean shutdown."""
        pass
    
    def test_stale_pidfile_detected(self, tmp_path):
        """Test stale PID file from dead process is handled."""
        pass

class TestAutoShutdown:
    """Test auto-shutdown after inactivity."""
    
    async def test_shutdown_after_timeout(self):
        """Test server shuts down after configured timeout."""
        pass
    
    async def test_activity_resets_timeout(self):
        """Test client activity resets shutdown timer."""
        pass

class TestMarkdownConversion:
    """Test HTML to markdown conversion."""
    
    def test_html_to_markdown_preserves_structure(self):
        """Test HTML conversion preserves headings, lists, links."""
        pass
    
    def test_scripts_and_styles_removed(self):
        """Test script and style tags are stripped."""
        pass
```

**Target: 25-30 tests for relay server**

### 2. Browser Tools Tests (`tests/unit/test_browser_tools.py`)

Test MCP browser automation tools:

```python
"""Unit tests for browser MCP tools."""
import pytest
from unittest.mock import AsyncMock, patch

@pytest.fixture
def mock_relay_client():
    """Mock the relay client for browser communication."""
    with patch("gobbler_mcp.tools.browser.RelayClient") as mock:
        client = AsyncMock()
        mock.return_value = client
        yield client

class TestBrowserCheckConnection:
    """Test browser_check_connection tool."""
    
    async def test_returns_connected_when_relay_responds(self, mock_relay_client):
        """Test successful connection check."""
        mock_relay_client.ping.return_value = True
        # Call tool and verify response
        pass
    
    async def test_returns_disconnected_when_relay_fails(self, mock_relay_client):
        """Test failed connection check."""
        mock_relay_client.ping.side_effect = ConnectionError()
        pass

class TestBrowserNavigate:
    """Test browser_navigate_to_url tool."""
    
    async def test_navigate_sends_correct_command(self, mock_relay_client):
        """Test navigation command is properly formatted."""
        pass
    
    async def test_navigate_validates_url(self, mock_relay_client):
        """Test invalid URLs are rejected."""
        pass
    
    async def test_navigate_with_wait_for_load(self, mock_relay_client):
        """Test wait_for_load parameter is respected."""
        pass

class TestBrowserExecuteScript:
    """Test browser_execute_script tool."""
    
    async def test_script_execution_returns_result(self, mock_relay_client):
        """Test script result is returned correctly."""
        mock_relay_client.execute.return_value = {"result": "value"}
        pass
    
    async def test_script_timeout_handling(self, mock_relay_client):
        """Test timeout is enforced on script execution."""
        pass
    
    async def test_script_error_propagation(self, mock_relay_client):
        """Test JavaScript errors are properly reported."""
        pass

class TestBrowserListTabs:
    """Test browser_list_tabs tool."""
    
    async def test_list_tabs_returns_all_tabs(self, mock_relay_client):
        """Test all tabs in Gobbler group are returned."""
        pass
    
    async def test_list_tabs_with_filter(self, mock_relay_client):
        """Test tab filtering by URL pattern."""
        pass
```

**Target: 15-20 tests for browser tools**

### 3. Crawl Tools Tests (`tests/unit/test_crawl_tools.py`)

Test site crawler and crawl MCP tools:

```python
"""Unit tests for crawl MCP tools and site crawler."""
import pytest
from unittest.mock import AsyncMock, patch

class TestSiteCrawler:
    """Test site_crawler.py BFS crawler."""
    
    async def test_crawl_respects_max_depth(self):
        """Test crawler stops at max_depth."""
        pass
    
    async def test_crawl_respects_max_pages(self):
        """Test crawler stops at max_pages."""
        pass
    
    async def test_url_include_pattern_filters(self):
        """Test include pattern filters URLs correctly."""
        pass
    
    async def test_url_exclude_pattern_filters(self):
        """Test exclude pattern filters URLs correctly."""
        pass
    
    async def test_robots_txt_respected(self):
        """Test robots.txt rules are followed."""
        pass
    
    async def test_circular_links_handled(self):
        """Test crawler doesn't loop on circular links."""
        pass
    
    async def test_concurrent_request_limiting(self):
        """Test concurrency semaphore limits requests."""
        pass
    
    async def test_crawl_delay_between_requests(self):
        """Test polite delay between requests."""
        pass

class TestSessionManager:
    """Test session_manager.py."""
    
    def test_create_session_saves_to_disk(self, tmp_path):
        """Test session creation persists to disk."""
        pass
    
    def test_load_session_restores_cookies(self, tmp_path):
        """Test session loading restores cookies."""
        pass
    
    def test_invalid_session_id_rejected(self):
        """Test invalid session IDs are rejected."""
        pass
    
    def test_corrupted_session_file_handled(self, tmp_path):
        """Test corrupted session files don't crash."""
        pass

class TestCrawlSiteTool:
    """Test crawl_site MCP tool."""
    
    async def test_crawl_site_basic(self):
        """Test basic site crawl with defaults."""
        pass
    
    async def test_crawl_site_with_selector(self):
        """Test crawl with CSS selector extraction."""
        pass
    
    async def test_crawl_site_output_dir(self, tmp_path):
        """Test crawl saves files to output_dir."""
        pass
```

**Target: 20-25 tests for crawl functionality**

### 4. Queue Utilities Tests (`tests/unit/test_queue_utils.py`)

```python
"""Unit tests for queue utilities."""
import pytest
from unittest.mock import patch

class TestDurationEstimation:
    """Test job duration estimation."""
    
    def test_estimate_audio_duration_by_model(self):
        """Test duration varies by Whisper model size."""
        pass
    
    def test_estimate_handles_unknown_model(self):
        """Test unknown model gets default estimate."""
        pass

class TestJobFormatting:
    """Test job result formatting."""
    
    def test_format_job_status(self):
        """Test job status formatting."""
        pass
    
    def test_format_job_list(self):
        """Test job list formatting."""
        pass

class TestRedisConnection:
    """Test Redis connection handling."""
    
    async def test_connection_failure_graceful(self):
        """Test connection failure doesn't crash."""
        pass
    
    async def test_retry_on_connection_lost(self):
        """Test automatic retry on connection loss."""
        pass
```

**Target: 10-15 tests for queue utilities**

### 5. Fix Test Isolation Issues

Create proper cleanup fixtures:

```python
# tests/conftest.py additions

@pytest.fixture(autouse=True)
def reset_whisper_model():
    """Reset Whisper model cache between tests."""
    yield
    # Clean up after test
    import gobbler_mcp.converters.audio as audio_module
    audio_module._whisper_model = None
    audio_module._current_model_size = None

@pytest.fixture(autouse=True)
def reset_config_singleton():
    """Reset config singleton between tests."""
    yield
    import gobbler_mcp.config as config_module
    config_module._config = None

@pytest.fixture(autouse=True)
def reset_prometheus_metrics():
    """Reset Prometheus metrics between tests."""
    yield
    from prometheus_client import REGISTRY
    # Clear custom metrics
    collectors_to_remove = []
    for collector in REGISTRY._names_to_collectors.values():
        if hasattr(collector, '_metrics'):
            collectors_to_remove.append(collector)
    for collector in collectors_to_remove:
        try:
            REGISTRY.unregister(collector)
        except Exception:
            pass
```

### 6. E2E Test Framework

Create automated E2E tests with Docker service detection:

```python
# tests/e2e/test_youtube_e2e.py
"""End-to-end tests for YouTube functionality."""
import pytest

pytestmark = pytest.mark.e2e

@pytest.fixture
def youtube_test_url():
    """Short, stable YouTube video for testing."""
    return "https://www.youtube.com/watch?v=dQw4w9WgXcQ"  # Rick Astley - stable

class TestYouTubeE2E:
    """E2E tests for YouTube transcript extraction."""
    
    async def test_full_transcript_extraction(self, youtube_test_url):
        """Test full workflow: URL -> transcript -> markdown."""
        pass
    
    async def test_transcript_with_timestamps(self, youtube_test_url):
        """Test transcript with timestamp markers."""
        pass

# tests/e2e/test_webpage_e2e.py
"""End-to-end tests for webpage functionality."""
import pytest

pytestmark = [pytest.mark.e2e, pytest.mark.requires_docker]

class TestWebpageE2E:
    """E2E tests requiring Crawl4AI Docker service."""
    
    @pytest.fixture
    def crawl4ai_available(self):
        """Skip if Crawl4AI not running."""
        import httpx
        try:
            resp = httpx.get("http://localhost:11235/health", timeout=2)
            if resp.status_code != 200:
                pytest.skip("Crawl4AI not available")
        except Exception:
            pytest.skip("Crawl4AI not available")
    
    async def test_webpage_fetch(self, crawl4ai_available):
        """Test basic webpage fetch."""
        pass
    
    async def test_webpage_with_selector(self, crawl4ai_available):
        """Test fetch with CSS selector."""
        pass
```

**Target: 10+ automated E2E tests**

### 7. Benchmark Tests That Actually Benchmark

```python
# tests/benchmarks/test_whisper_performance.py (rewrite)
"""Actual performance benchmarks for Whisper transcription."""
import pytest
from pathlib import Path

pytestmark = pytest.mark.benchmark

@pytest.fixture
def sample_audio(fixtures_dir):
    """Get sample audio file for benchmarking."""
    audio_file = fixtures_dir / "batch_audio" / "sample_01.wav"
    if not audio_file.exists():
        pytest.skip("Sample audio not available")
    return audio_file

class TestWhisperBenchmarks:
    """Performance benchmarks for Whisper transcription."""
    
    def test_tiny_model_speed(self, benchmark, sample_audio):
        """Benchmark tiny model transcription."""
        from gobbler_core.converters.audio import convert_audio_to_markdown
        
        result = benchmark(
            lambda: asyncio.run(
                convert_audio_to_markdown(str(sample_audio), model="tiny")
            )
        )
        # Assert reasonable performance
        assert benchmark.stats['mean'] < 5.0  # Under 5 seconds
    
    def test_small_model_speed(self, benchmark, sample_audio):
        """Benchmark small model transcription."""
        pass
```

## Implementation Plan

### Phase 1: Test Infrastructure (Day 1)
- Add cleanup fixtures to conftest.py
- Fix test isolation issues
- Remove pytest.skip() from working tests

### Phase 2: Critical Module Tests (Days 2-3)
- Write relay server tests (25 tests)
- Write browser tools tests (15 tests)

### Phase 3: Crawl Tests (Day 4)
- Write site crawler tests (15 tests)
- Write session manager tests (10 tests)
- Write crawl tool tests (10 tests)

### Phase 4: Supporting Tests (Day 5)
- Write queue utility tests (10 tests)
- Write batch processor tests (15 tests)

### Phase 5: E2E Framework (Days 6-7)
- Set up E2E test framework with Docker detection
- Write 10+ automated E2E tests
- Fix benchmark tests to actually benchmark

## Files to Create

```
tests/
├── unit/
│   ├── test_relay_server.py         # NEW: 25 tests
│   ├── test_browser_tools.py        # NEW: 15 tests
│   ├── test_crawl_tools.py          # NEW: 20 tests
│   ├── test_session_manager.py      # NEW: 10 tests
│   ├── test_queue_utils.py          # NEW: 10 tests
│   ├── test_youtube_batch.py        # NEW: 10 tests
│   └── test_webpage_batch.py        # NEW: 10 tests
├── e2e/
│   ├── test_youtube_e2e.py          # NEW: 5 tests
│   ├── test_webpage_e2e.py          # NEW: 5 tests
│   └── conftest.py                  # NEW: E2E fixtures
└── conftest.py                      # MODIFY: Add cleanup fixtures
```

## Files to Modify

```
tests/conftest.py                    # Add isolation fixtures
tests/benchmarks/test_whisper_performance.py  # Make tests real
tests/integration/test_redis_queue.py  # Remove skips or implement
```

## Acceptance Criteria

### Coverage
- [ ] Overall test coverage >= 70%
- [ ] relay.py coverage >= 60%
- [ ] browser.py coverage >= 80%
- [ ] crawl.py coverage >= 70%
- [ ] site_crawler.py coverage >= 80%

### Test Quality
- [ ] All new tests have descriptive names
- [ ] All new tests have docstrings
- [ ] Mocking strategy documented
- [ ] Edge cases covered for each module

### CI/CD
- [ ] All tests pass in CI
- [ ] No skipped tests in unit suite
- [ ] E2E tests run on main branch
- [ ] Coverage report generated

## Metrics

### Before
- Total tests: 139
- Coverage: ~40-50%
- Untested critical modules: 5

### After (Target)
- Total tests: 250+
- Coverage: 70%+
- All modules have at least basic coverage

## Definition of Done

- [ ] 100+ new tests written
- [ ] Coverage increased to 70%+
- [ ] All critical modules covered
- [ ] Test isolation fixed
- [ ] E2E framework established
- [ ] Benchmark tests functional
- [ ] CI passes with all tests
- [ ] Documentation updated
