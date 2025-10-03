# PRD-001: Testing Infrastructure

## Overview
**Epic**: Quality Assurance & Testing Framework
**Phase**: Foundation
**Estimated Effort**: 3-4 days
**Dependencies**: None - foundational work
**Parallel**: ✅ Can be implemented alongside other PRDs

## Problem Statement
Gobbler MCP currently lacks a comprehensive test suite, making it difficult to:
- Verify correctness of converters and tools
- Prevent regressions when adding features
- Ensure reliability of external service integrations (Crawl4AI, Docling, YouTube API)
- Validate queue system behavior and edge cases
- Test error handling paths

A robust testing infrastructure is essential for maintaining code quality, enabling confident refactoring, and supporting future development.

## Success Criteria
- [ ] Unit tests cover all converter modules (youtube, audio, webpage, document)
- [ ] Integration tests validate Docker service interactions
- [ ] Mock tests eliminate external API dependencies
- [ ] Performance benchmarks track transcription speed
- [ ] CI/CD pipeline runs tests automatically
- [ ] Code coverage >= 80% for core modules
- [ ] Test fixtures available for common scenarios

## Technical Requirements

### Test Structure
```
tests/
├── __init__.py
├── conftest.py                    # Shared pytest fixtures
├── fixtures/                      # Test data files
│   ├── sample_video.mp4           # 30-second test video
│   ├── sample_audio.mp3           # 15-second test audio
│   ├── sample_document.pdf        # 2-page test PDF
│   ├── sample_webpage.html        # Static HTML for testing
│   └── expected_outputs/          # Expected markdown results
│       ├── youtube_transcript.md
│       ├── audio_transcript.md
│       ├── webpage_output.md
│       └── document_output.md
├── unit/                          # Unit tests
│   ├── test_youtube_converter.py
│   ├── test_audio_converter.py
│   ├── test_webpage_converter.py
│   ├── test_document_converter.py
│   ├── test_config.py
│   ├── test_queue.py
│   └── test_frontmatter.py
├── integration/                   # Integration tests
│   ├── test_crawl4ai_service.py
│   ├── test_docling_service.py
│   ├── test_redis_queue.py
│   └── test_mcp_tools.py
├── benchmarks/                    # Performance tests
│   ├── test_whisper_performance.py
│   └── test_queue_throughput.py
└── e2e/                          # End-to-end tests
    ├── test_youtube_workflow.py
    └── test_transcription_workflow.py
```

### Testing Dependencies
```toml
# Add to pyproject.toml [project.optional-dependencies]
dev = [
    "pytest>=8.0.0",
    "pytest-asyncio>=0.23.0",
    "pytest-cov>=5.0.0",
    "pytest-benchmark>=4.0.0",
    "pytest-mock>=3.12.0",
    "httpx-mock>=0.7.0",
    "fakeredis>=2.21.0",
    "mypy>=1.10.0",
    "ruff>=0.4.0",
]
```

## Implementation Details

### 1. Unit Tests - YouTube Converter

```python
# tests/unit/test_youtube_converter.py
import pytest
from unittest.mock import Mock, patch, AsyncMock
from gobbler_mcp.converters.youtube import (
    extract_video_id,
    format_timestamp,
    get_video_metadata,
    convert_youtube_to_markdown,
)

class TestVideoIdExtraction:
    """Test YouTube video ID extraction"""

    def test_extract_video_id_standard_format(self):
        """Test standard youtube.com URL"""
        url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
        assert extract_video_id(url) == "dQw4w9WgXcQ"

    def test_extract_video_id_short_format(self):
        """Test youtu.be short URL"""
        url = "https://youtu.be/dQw4w9WgXcQ"
        assert extract_video_id(url) == "dQw4w9WgXcQ"

    def test_extract_video_id_invalid_format(self):
        """Test invalid URL raises ValueError"""
        with pytest.raises(ValueError, match="Invalid YouTube URL"):
            extract_video_id("https://vimeo.com/12345")

    def test_extract_video_id_invalid_length(self):
        """Test video ID with wrong length"""
        with pytest.raises(ValueError):
            extract_video_id("https://youtube.com/watch?v=short")


class TestTimestampFormatting:
    """Test timestamp formatting"""

    def test_format_timestamp_minutes_only(self):
        """Test timestamps under 1 hour"""
        assert format_timestamp(125.5) == "02:05"

    def test_format_timestamp_with_hours(self):
        """Test timestamps over 1 hour"""
        assert format_timestamp(3665) == "01:01:05"

    def test_format_timestamp_zero(self):
        """Test zero timestamp"""
        assert format_timestamp(0) == "00:00"


class TestVideoMetadata:
    """Test video metadata extraction"""

    @patch('gobbler_mcp.converters.youtube.yt_dlp.YoutubeDL')
    def test_get_video_metadata_success(self, mock_ydl_class):
        """Test successful metadata extraction"""
        mock_ydl = Mock()
        mock_ydl.extract_info.return_value = {
            'title': 'Test Video',
            'channel': 'Test Channel',
            'thumbnail': 'https://example.com/thumb.jpg',
            'description': 'Test description'
        }
        mock_ydl_class.return_value.__enter__.return_value = mock_ydl

        metadata = get_video_metadata("https://youtube.com/watch?v=test123")

        assert metadata['title'] == 'Test Video'
        assert metadata['channel'] == 'Test Channel'
        assert metadata['thumbnail'] == 'https://example.com/thumb.jpg'

    @patch('gobbler_mcp.converters.youtube.yt_dlp.YoutubeDL')
    def test_get_video_metadata_failure(self, mock_ydl_class):
        """Test metadata extraction failure returns defaults"""
        mock_ydl = Mock()
        mock_ydl.extract_info.side_effect = Exception("Network error")
        mock_ydl_class.return_value.__enter__.return_value = mock_ydl

        metadata = get_video_metadata("https://youtube.com/watch?v=test123")

        assert metadata['title'] is None
        assert metadata['channel'] is None


@pytest.mark.asyncio
class TestYouTubeConversion:
    """Test full YouTube to markdown conversion"""

    @patch('gobbler_mcp.converters.youtube.YouTubeTranscriptApi')
    @patch('gobbler_mcp.converters.youtube.get_video_metadata')
    async def test_convert_youtube_to_markdown_success(
        self, mock_metadata, mock_transcript_api
    ):
        """Test successful conversion"""
        # Mock metadata
        mock_metadata.return_value = {
            'title': 'Test Video',
            'channel': 'Test Channel',
            'thumbnail': None,
            'description': None
        }

        # Mock transcript
        mock_api = Mock()
        mock_transcript_list = Mock()
        mock_transcript = Mock()
        mock_transcript.language_code = 'en'

        # Create mock transcript entries
        mock_entry = Mock()
        mock_entry.text = "Test transcript text"
        mock_entry.start = 0.0
        mock_entry.duration = 5.0

        mock_transcript.fetch.return_value = [mock_entry]
        mock_transcript_list.find_generated_transcript.return_value = mock_transcript
        mock_api.list.return_value = mock_transcript_list
        mock_transcript_api.return_value = mock_api

        # Test conversion
        markdown, metadata = await convert_youtube_to_markdown(
            video_url="https://youtube.com/watch?v=dQw4w9WgXcQ",
            include_timestamps=False,
            language="auto"
        )

        # Verify output
        assert "---" in markdown  # Frontmatter present
        assert "Test transcript text" in markdown
        assert metadata['video_id'] == "dQw4w9WgXcQ"
        assert metadata['language'] == 'en'

    @patch('gobbler_mcp.converters.youtube.YouTubeTranscriptApi')
    async def test_convert_youtube_with_timestamps(self, mock_transcript_api):
        """Test conversion with timestamps enabled"""
        # Setup mocks...
        mock_api = Mock()
        mock_transcript_list = Mock()
        mock_transcript = Mock()
        mock_transcript.language_code = 'en'

        mock_entry = Mock()
        mock_entry.text = "Hello world"
        mock_entry.start = 125.0
        mock_entry.duration = 3.0

        mock_transcript.fetch.return_value = [mock_entry]
        mock_transcript_list.find_generated_transcript.return_value = mock_transcript
        mock_api.list.return_value = mock_transcript_list
        mock_transcript_api.return_value = mock_api

        markdown, _ = await convert_youtube_to_markdown(
            video_url="https://youtube.com/watch?v=test",
            include_timestamps=True,
            language="auto"
        )

        assert "[02:05]" in markdown  # Timestamp should be present
```

### 2. Unit Tests - Audio Converter

```python
# tests/unit/test_audio_converter.py
import pytest
import os
from pathlib import Path
from unittest.mock import Mock, patch, AsyncMock
from gobbler_mcp.converters.audio import (
    convert_audio_to_markdown,
    _extract_audio,
    _get_whisper_model,
)

@pytest.fixture
def sample_audio_file(tmp_path):
    """Create a temporary test audio file"""
    audio_file = tmp_path / "test_audio.mp3"
    # Create a minimal MP3 file (you'd use a real fixture in practice)
    audio_file.write_bytes(b"fake mp3 data")
    return str(audio_file)


class TestAudioExtraction:
    """Test audio extraction from video files"""

    @pytest.mark.asyncio
    @patch('gobbler_mcp.converters.audio.subprocess.run')
    async def test_extract_audio_success(self, mock_subprocess, tmp_path):
        """Test successful audio extraction"""
        video_file = str(tmp_path / "test.mp4")

        # Mock successful ffmpeg execution
        mock_subprocess.return_value = Mock(returncode=0, stderr="")

        result = await _extract_audio(video_file)

        assert result.endswith(".mp3")
        assert os.path.exists(result)
        mock_subprocess.assert_called_once()

    @pytest.mark.asyncio
    @patch('gobbler_mcp.converters.audio.subprocess.run')
    async def test_extract_audio_ffmpeg_failure(self, mock_subprocess):
        """Test ffmpeg extraction failure"""
        mock_subprocess.return_value = Mock(
            returncode=1,
            stderr="ffmpeg error: invalid file"
        )

        with pytest.raises(RuntimeError, match="ffmpeg audio extraction failed"):
            await _extract_audio("/path/to/video.mp4")

    @pytest.mark.asyncio
    @patch('gobbler_mcp.converters.audio.subprocess.run')
    async def test_extract_audio_timeout(self, mock_subprocess):
        """Test extraction timeout"""
        from subprocess import TimeoutExpired
        mock_subprocess.side_effect = TimeoutExpired("ffmpeg", 300)

        with pytest.raises(RuntimeError, match="timed out"):
            await _extract_audio("/path/to/video.mp4")


class TestWhisperModel:
    """Test Whisper model loading"""

    @patch('gobbler_mcp.converters.audio.WhisperModel')
    def test_get_whisper_model_loads_correctly(self, mock_whisper_class):
        """Test model is loaded with correct parameters"""
        mock_model = Mock()
        mock_whisper_class.return_value = mock_model

        result = _get_whisper_model("small")

        mock_whisper_class.assert_called_once_with(
            "small",
            device="cpu",
            compute_type="auto"
        )
        assert result == mock_model

    @patch('gobbler_mcp.converters.audio.WhisperModel')
    def test_get_whisper_model_caching(self, mock_whisper_class):
        """Test model is cached and not reloaded"""
        mock_model = Mock()
        mock_whisper_class.return_value = mock_model

        # Load model twice
        result1 = _get_whisper_model("small")
        result2 = _get_whisper_model("small")

        # Should only be called once due to caching
        assert mock_whisper_class.call_count == 1
        assert result1 == result2


@pytest.mark.asyncio
class TestAudioConversion:
    """Test audio to markdown conversion"""

    @patch('gobbler_mcp.converters.audio._get_whisper_model')
    @patch('gobbler_mcp.converters.audio.validate_input_path')
    async def test_convert_audio_to_markdown_success(
        self, mock_validate, mock_get_model, sample_audio_file
    ):
        """Test successful audio transcription"""
        # Mock validation
        mock_validate.return_value = None

        # Mock Whisper model
        mock_model = Mock()
        mock_segment = Mock()
        mock_segment.text = "Hello world"
        mock_segment.end = 5.0

        mock_info = Mock()
        mock_info.language = "en"

        mock_model.transcribe.return_value = ([mock_segment], mock_info)
        mock_get_model.return_value = mock_model

        # Test conversion
        markdown, metadata = await convert_audio_to_markdown(
            file_path=sample_audio_file,
            model="small",
            language="auto"
        )

        # Verify output
        assert "---" in markdown  # Frontmatter
        assert "Hello world" in markdown
        assert metadata['language'] == 'en'
        assert metadata['model'] == 'small'
        assert 'conversion_time_ms' in metadata

    async def test_convert_audio_invalid_file(self):
        """Test conversion with non-existent file"""
        with pytest.raises(ValueError, match="File not found"):
            await convert_audio_to_markdown(
                file_path="/nonexistent/file.mp3",
                model="small"
            )

    async def test_convert_audio_invalid_model(self, sample_audio_file):
        """Test conversion with invalid model"""
        with pytest.raises(ValueError, match="Invalid model"):
            await convert_audio_to_markdown(
                file_path=sample_audio_file,
                model="invalid_model"
            )
```

### 3. Integration Tests - Crawl4AI Service

```python
# tests/integration/test_crawl4ai_service.py
import pytest
import httpx
from gobbler_mcp.converters.webpage import convert_webpage_to_markdown
from gobbler_mcp.config import get_config

@pytest.mark.integration
class TestCrawl4AIIntegration:
    """Integration tests for Crawl4AI service"""

    @pytest.fixture(autouse=True)
    async def check_service_available(self):
        """Skip tests if Crawl4AI service is not running"""
        config = get_config()
        service_url = config.get_service_url("crawl4ai")

        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(f"{service_url}/health", timeout=5.0)
                if response.status_code != 200:
                    pytest.skip("Crawl4AI service not available")
        except (httpx.ConnectError, httpx.TimeoutException):
            pytest.skip("Crawl4AI service not available")

    @pytest.mark.asyncio
    async def test_convert_simple_webpage(self):
        """Test converting a simple static webpage"""
        markdown, metadata = await convert_webpage_to_markdown(
            url="https://example.com",
            include_images=True,
            timeout=30
        )

        assert "---" in markdown
        assert "Example Domain" in markdown
        assert metadata['url'] == "https://example.com"
        assert metadata['word_count'] > 0

    @pytest.mark.asyncio
    async def test_convert_webpage_with_javascript(self):
        """Test converting a JavaScript-heavy page"""
        markdown, metadata = await convert_webpage_to_markdown(
            url="https://httpbin.org/",
            include_images=False,
            timeout=45
        )

        assert markdown is not None
        assert len(markdown) > 100

    @pytest.mark.asyncio
    async def test_convert_webpage_timeout(self):
        """Test that timeout is respected"""
        with pytest.raises(httpx.TimeoutException):
            await convert_webpage_to_markdown(
                url="https://httpbin.org/delay/60",
                timeout=5
            )
```

### 4. Mock Tests - YouTube API

```python
# tests/unit/test_youtube_mocks.py
import pytest
from httpx_mock import HTTPXMock
from gobbler_mcp.converters.youtube import get_video_metadata

@pytest.mark.asyncio
class TestYouTubeMocks:
    """Mock tests for YouTube API interactions"""

    def test_mock_youtube_api_response(self, httpx_mock: HTTPXMock):
        """Test mocked YouTube API response"""
        # Mock the yt-dlp request (this is simplified)
        httpx_mock.add_response(
            url="https://www.youtube.com/watch?v=test",
            json={
                "title": "Mocked Video",
                "channel": "Mocked Channel",
                "thumbnail": "https://example.com/thumb.jpg"
            }
        )

        # This would need actual implementation to work with yt-dlp
        # which doesn't use httpx directly
        # Shown for demonstration purposes
```

### 5. Performance Benchmarks

```python
# tests/benchmarks/test_whisper_performance.py
import pytest
from pathlib import Path
from gobbler_mcp.converters.audio import convert_audio_to_markdown

@pytest.mark.benchmark
class TestWhisperPerformance:
    """Benchmark Whisper transcription performance"""

    @pytest.fixture
    def benchmark_audio(self):
        """60-second audio file for benchmarking"""
        return str(Path(__file__).parent.parent / "fixtures" / "benchmark_60s.mp3")

    @pytest.mark.asyncio
    @pytest.mark.benchmark(min_rounds=3)
    async def test_transcription_speed_small_model(self, benchmark, benchmark_audio):
        """Benchmark transcription with small model"""
        async def transcribe():
            return await convert_audio_to_markdown(
                file_path=benchmark_audio,
                model="small",
                language="en"
            )

        result = benchmark(transcribe)
        # Should process ~6 seconds per MB on M-series
```

### 6. E2E Tests - Full Workflow

```python
# tests/e2e/test_youtube_workflow.py
import pytest
import tempfile
from pathlib import Path
from gobbler_mcp.server import (
    transcribe_youtube,
    download_youtube_video,
    transcribe_audio
)

@pytest.mark.e2e
@pytest.mark.asyncio
class TestYouTubeWorkflow:
    """End-to-end tests for YouTube workflows"""

    async def test_complete_youtube_transcription_workflow(self):
        """Test downloading and transcribing a YouTube video"""
        # This test uses a real (short) YouTube video
        test_video_url = "https://www.youtube.com/watch?v=jNQXAC9IVRw"  # "Me at the zoo"

        with tempfile.TemporaryDirectory() as tmpdir:
            # Step 1: Download video
            result = await download_youtube_video(
                video_url=test_video_url,
                output_dir=tmpdir,
                quality="360p"
            )

            assert "downloaded successfully" in result.lower()

            # Step 2: Find downloaded file
            video_files = list(Path(tmpdir).glob("*.mp4"))
            assert len(video_files) == 1

            # Step 3: Transcribe
            markdown = await transcribe_audio(
                file_path=str(video_files[0]),
                model="tiny",  # Fast model for testing
                language="en"
            )

            assert "---" in markdown
            assert len(markdown) > 100
```

### 7. Configuration for pytest

```python
# tests/conftest.py
import pytest
import asyncio
from pathlib import Path

# Configure pytest-asyncio
pytest_plugins = ('pytest_asyncio',)

@pytest.fixture(scope="session")
def event_loop():
    """Create event loop for async tests"""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()

@pytest.fixture
def fixtures_dir():
    """Path to test fixtures directory"""
    return Path(__file__).parent / "fixtures"

@pytest.fixture
def temp_output_dir(tmp_path):
    """Temporary directory for test outputs"""
    output_dir = tmp_path / "outputs"
    output_dir.mkdir()
    return output_dir

# Mark definitions
def pytest_configure(config):
    config.addinivalue_line("markers", "integration: mark test as integration test")
    config.addinivalue_line("markers", "e2e: mark test as end-to-end test")
    config.addinivalue_line("markers", "benchmark: mark test as performance benchmark")
```

### 8. CI/CD Configuration

```yaml
# .github/workflows/test.yml
name: Tests

on:
  push:
    branches: [ main, develop ]
  pull_request:
    branches: [ main ]

jobs:
  test:
    runs-on: ubuntu-latest

    strategy:
      matrix:
        python-version: ["3.11", "3.12"]

    services:
      redis:
        image: redis:7-alpine
        ports:
          - 6380:6379
        options: >-
          --health-cmd "redis-cli ping"
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5

      crawl4ai:
        image: unclecode/crawl4ai:basic
        ports:
          - 11235:11235
        env:
          CRAWL4AI_API_TOKEN: test-token

    steps:
    - uses: actions/checkout@v4

    - name: Install uv
      uses: astral-sh/setup-uv@v2

    - name: Set up Python
      run: uv python install ${{ matrix.python-version }}

    - name: Install dependencies
      run: |
        uv sync --dev
        uv pip install -e .

    - name: Run unit tests
      run: |
        uv run pytest tests/unit/ -v --cov=src/gobbler_mcp --cov-report=xml

    - name: Run integration tests
      run: |
        uv run pytest tests/integration/ -v -m integration

    - name: Upload coverage
      uses: codecov/codecov-action@v3
      with:
        file: ./coverage.xml
        fail_ci_if_error: true
```

## Acceptance Criteria

### 1. Unit Test Coverage
- [ ] YouTube converter: 100% function coverage
- [ ] Audio converter: 100% function coverage
- [ ] Webpage converter: 90% coverage (excluding external service calls)
- [ ] Queue utilities: 100% coverage
- [ ] Config management: 100% coverage
- [ ] Frontmatter generation: 100% coverage

### 2. Integration Tests
- [ ] Crawl4AI service integration working
- [ ] Docling service integration working (when available)
- [ ] Redis queue integration working
- [ ] Health check tests passing

### 3. Mock Tests
- [ ] External APIs mocked appropriately
- [ ] Tests run without network access
- [ ] Consistent mock data fixtures

### 4. Performance Tests
- [ ] Whisper transcription benchmarks established
- [ ] Baseline performance metrics documented
- [ ] Regression detection for performance

### 5. CI/CD
- [ ] GitHub Actions workflow configured
- [ ] Tests run on push and PR
- [ ] Coverage reports generated
- [ ] Multiple Python versions tested

## Deliverables

### Files to Create
```
tests/
├── conftest.py
├── fixtures/
│   ├── sample_audio.mp3
│   ├── sample_video.mp4
│   └── expected_outputs/
├── unit/
│   ├── test_youtube_converter.py
│   ├── test_audio_converter.py
│   ├── test_webpage_converter.py
│   ├── test_config.py
│   ├── test_queue.py
│   └── test_frontmatter.py
├── integration/
│   ├── test_crawl4ai_service.py
│   ├── test_redis_queue.py
│   └── test_mcp_tools.py
├── benchmarks/
│   └── test_whisper_performance.py
└── e2e/
    └── test_youtube_workflow.py

.github/
└── workflows/
    └── test.yml

pytest.ini                         # Pytest configuration
.coveragerc                       # Coverage configuration
```

## Testing Commands

```bash
# Run all tests
uv run pytest

# Run unit tests only
uv run pytest tests/unit/

# Run with coverage
uv run pytest --cov=src/gobbler_mcp --cov-report=html

# Run integration tests (requires services)
uv run pytest tests/integration/ -m integration

# Run benchmarks
uv run pytest tests/benchmarks/ -m benchmark

# Run specific test file
uv run pytest tests/unit/test_youtube_converter.py -v

# Run with parallel execution
uv run pytest -n auto
```

## Definition of Done
- [ ] All test files created and implemented
- [ ] Test fixtures available in repository
- [ ] Unit tests achieve >= 80% coverage
- [ ] Integration tests pass with running services
- [ ] CI/CD pipeline configured and passing
- [ ] Documentation updated with testing instructions
- [ ] Performance baselines established
- [ ] Tests run successfully on multiple Python versions (3.11, 3.12, 3.13)

## References
- pytest documentation: https://docs.pytest.org/
- pytest-asyncio: https://pytest-asyncio.readthedocs.io/
- pytest-cov: https://pytest-cov.readthedocs.io/
- GitHub Actions: https://docs.github.com/en/actions
