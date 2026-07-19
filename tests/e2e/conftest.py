"""E2E test configuration and fixtures.

E2E tests run against real services and make actual network calls.
Use markers to skip tests when required services are unavailable.
"""

import shutil
import subprocess
import tempfile
from collections.abc import Generator
from pathlib import Path

import httpx
import pytest

# ============================================================================
# Service availability checks
# ============================================================================


def is_network_available() -> bool:
    """Check basic network connectivity."""
    try:
        httpx.get("https://www.google.com", timeout=5)
    except Exception:
        return False
    else:
        return True


def is_crawl4ai_available() -> bool:
    """Check if Crawl4AI Docker container is running."""
    try:
        response = httpx.get("http://localhost:11235/health", timeout=2)
    except Exception:
        return False
    else:
        return response.status_code == 200


def is_docling_available() -> bool:
    """Check if Docling Docker container is running."""
    try:
        response = httpx.get("http://localhost:5001/health", timeout=2)
    except Exception:
        return False
    else:
        return response.status_code == 200


def is_gobbler_cli_available() -> bool:
    """Check if gobbler CLI is installed and working."""
    try:
        result = subprocess.run(
            ["gobbler", "--help"],
            capture_output=True,
            timeout=5,
            check=False,
        )
    except Exception:
        return False
    else:
        return result.returncode == 0


def is_ffmpeg_available() -> bool:
    """Check whether system FFmpeg is available for media artifact tests."""
    return shutil.which("ffmpeg") is not None


# ============================================================================
# Pytest configuration
# ============================================================================


def pytest_configure(config):
    """Register custom markers for E2E tests."""
    config.addinivalue_line("markers", "requires_network: test requires internet access")
    config.addinivalue_line("markers", "requires_crawl4ai: test requires Crawl4AI Docker container")
    config.addinivalue_line("markers", "requires_docling: test requires Docling Docker container")
    config.addinivalue_line("markers", "requires_ffmpeg: test requires system ffmpeg")
    config.addinivalue_line("markers", "slow: test takes more than 30 seconds")


# ============================================================================
# Skip conditions (applied via autouse fixture)
# ============================================================================


@pytest.fixture(autouse=True)
def skip_by_marker(request):
    """Automatically skip tests based on markers and service availability."""
    markers = {
        "requires_network": (
            is_network_available,
            "Network unavailable",
        ),
        "requires_crawl4ai": (
            is_crawl4ai_available,
            "Crawl4AI not running (docker compose up crawl4ai)",
        ),
        "requires_docling": (
            is_docling_available,
            "Docling not running (docker compose up docling)",
        ),
        "requires_ffmpeg": (
            is_ffmpeg_available,
            "FFmpeg not installed",
        ),
    }

    for marker_name, (check_fn, skip_reason) in markers.items():
        marker = request.node.get_closest_marker(marker_name)
        if marker is not None and not check_fn():
            pytest.skip(skip_reason)


# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture(scope="session")
def fixtures_dir() -> Path:
    """Path to test fixtures directory."""
    return Path(__file__).parent.parent / "fixtures"


@pytest.fixture(scope="session")
def audio_dir(fixtures_dir: Path) -> Path:
    """Path to audio fixtures directory."""
    return fixtures_dir / "audio"


@pytest.fixture(scope="session")
def video_dir(fixtures_dir: Path) -> Path:
    """Path to video fixtures directory."""
    return fixtures_dir / "video"


@pytest.fixture(scope="session")
def documents_dir(fixtures_dir: Path) -> Path:
    """Path to documents fixtures directory."""
    return fixtures_dir / "documents"


@pytest.fixture(scope="session")
def urls_dir(fixtures_dir: Path) -> Path:
    """Path to URL lists directory."""
    return fixtures_dir / "urls"


@pytest.fixture
def temp_output_dir() -> Generator[Path, None, None]:
    """Provide a temporary directory for test outputs."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


# ============================================================================
# CLI runner helper
# ============================================================================


@pytest.fixture
def run_gobbler():
    """Fixture that returns a function to run gobbler CLI commands."""

    def _run(args: list[str], timeout: int = 120) -> subprocess.CompletedProcess:
        """Run a gobbler CLI command.

        Args:
            args: Command arguments (without 'gobbler' prefix)
            timeout: Timeout in seconds

        Returns:
            CompletedProcess with stdout, stderr, returncode
        """
        cmd = ["gobbler", *args]
        return subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )

    return _run
