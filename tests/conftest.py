"""Shared pytest fixtures and configuration for Gobbler MCP tests."""

import asyncio
import tempfile
from collections.abc import Generator
from pathlib import Path
from unittest.mock import MagicMock

import pytest


@pytest.fixture(autouse=True)
def reset_config_singleton():
    """Reset config singleton between tests to ensure isolation.

    This fixture runs automatically before each test to reset the global
    config instance, preventing state leakage between tests.
    """
    import gobbler_mcp.config as config_module

    # Reset before test
    config_module._config = None
    yield
    # Reset after test
    config_module._config = None


@pytest.fixture(scope="session")
def fixtures_dir() -> Path:
    """Return path to test fixtures directory."""
    return Path(__file__).parent / "fixtures"


@pytest.fixture
def temp_output_dir() -> Generator[Path, None, None]:
    """Provide a temporary directory for test outputs."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


# Mock fixtures for external services
@pytest.fixture
def mock_youtube_api(mocker):
    """Mock YouTube Transcript API."""
    mock_api = mocker.patch("gobbler_core.converters.youtube.YouTubeTranscriptApi")
    mock_api.get_transcript.return_value = [
        {"text": "Hello world", "start": 0.0, "duration": 2.5},
        {"text": "This is a test", "start": 2.5, "duration": 3.0},
    ]
    mock_api.list_transcripts.return_value = MagicMock()
    return mock_api


@pytest.fixture
def mock_yt_dlp(mocker):
    """Mock yt-dlp for video metadata and downloads."""
    mock_ytdl = mocker.patch("gobbler_core.converters.youtube.yt_dlp.YoutubeDL")
    mock_instance = MagicMock()
    mock_instance.extract_info.return_value = {
        "title": "Test Video",
        "channel": "Test Channel",
        "duration": 180,
        "upload_date": "20250101",
        "view_count": 1000,
        "description": "Test description",
    }
    mock_ytdl.return_value.__enter__.return_value = mock_instance
    return mock_ytdl


@pytest.fixture
def mock_whisper_model(mocker):
    """Mock faster-whisper WhisperModel."""
    mock_model = mocker.patch("gobbler_core.converters.audio.WhisperModel")
    mock_instance = MagicMock()

    # Mock transcribe method to return segments
    mock_segments = [
        MagicMock(text="Hello world", start=0.0, end=2.5),
        MagicMock(text="This is a test", start=2.5, end=5.5),
    ]
    mock_info = MagicMock(language="en", duration=5.5)
    mock_instance.transcribe.return_value = (mock_segments, mock_info)

    mock_model.return_value = mock_instance
    return mock_model


@pytest.fixture
def mock_ffmpeg(mocker):
    """Mock ffmpeg subprocess for audio extraction."""
    mock_run = mocker.patch("gobbler_core.converters.audio.subprocess.run")
    mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
    return mock_run


@pytest.fixture
def mock_crawl4ai_response():
    """Mock Crawl4AI task result response."""
    return {
        "markdown": "# Test Article\n\nThis is test content.",
        "title": "Test Article",
        "metadata": {
            "title": "Test Article",
            "description": "Test description",
            "language": "en",
        },
        "html": "<html><body><h1>Test Article</h1><p>This is test content.</p></body></html>",
    }


@pytest.fixture
def mock_docling_response():
    """Mock Docling HTTP response."""
    return {
        "success": True,
        "markdown": "# Document Title\n\nDocument content here.",
        "metadata": {
            "pages": 2,
            "title": "Document Title",
        },
    }


# Sample test data
@pytest.fixture
def sample_youtube_url() -> str:
    """Return a sample YouTube URL for testing."""
    return "https://youtube.com/watch?v=dQw4w9WgXcQ"


@pytest.fixture
def sample_audio_file(fixtures_dir: Path) -> Path:
    """Return path to sample audio fixture (short wav)."""
    return fixtures_dir / "audio" / "test_short.wav"


@pytest.fixture
def sample_video_file(fixtures_dir: Path) -> Path:
    """Return path to sample video fixture."""
    return fixtures_dir / "video" / "ted_chatgpt_language.mp4"


@pytest.fixture
def sample_document_file(fixtures_dir: Path) -> Path:
    """Return path to sample PDF fixture."""
    return fixtures_dir / "documents" / "pdf" / "resume_sample.pdf"


# Additional fixture path helpers
@pytest.fixture(scope="session")
def audio_dir(fixtures_dir: Path) -> Path:
    """Return path to audio fixtures directory."""
    return fixtures_dir / "audio"


@pytest.fixture(scope="session")
def video_dir(fixtures_dir: Path) -> Path:
    """Return path to video fixtures directory."""
    return fixtures_dir / "video"


@pytest.fixture(scope="session")
def documents_dir(fixtures_dir: Path) -> Path:
    """Return path to documents fixtures directory."""
    return fixtures_dir / "documents"


@pytest.fixture(scope="session")
def urls_dir(fixtures_dir: Path) -> Path:
    """Return path to URL lists directory."""
    return fixtures_dir / "urls"


def load_url_list(urls_dir: Path, category: str, filename: str) -> list[str]:
    """Load URLs from a fixture file, filtering comments and empty lines."""
    path = urls_dir / category / filename
    return [
        line.strip()
        for line in path.read_text().splitlines()
        if line.strip() and not line.startswith("#")
    ]


# Expected outputs for comparison
@pytest.fixture
def expected_youtube_transcript(fixtures_dir: Path) -> str:
    """Return expected YouTube transcript output."""
    expected_file = fixtures_dir / "expected_outputs" / "youtube_transcript.md"
    if expected_file.exists():
        return expected_file.read_text()
    return "# Test Video\n\nHello world This is a test"


@pytest.fixture
def expected_audio_transcript(fixtures_dir: Path) -> str:
    """Return expected audio transcript output."""
    expected_file = fixtures_dir / "expected_outputs" / "audio_transcript.md"
    if expected_file.exists():
        return expected_file.read_text()
    return "# Audio Transcription\n\nHello world This is a test"


# Service health check helpers
@pytest.fixture
def check_crawl4ai_available() -> bool:
    """Check if Crawl4AI service is available for integration tests."""
    try:
        import httpx

        response = httpx.get("http://localhost:11235/health", timeout=2)
    except Exception:
        return False
    else:
        return response.status_code == 200


@pytest.fixture
def check_docling_available() -> bool:
    """Check if Docling service is available for integration tests."""
    try:
        import httpx

        response = httpx.get("http://localhost:5001/health", timeout=2)
    except Exception:
        return False
    else:
        return response.status_code == 200
