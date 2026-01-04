"""Fixture loading utilities for E2E tests."""

from pathlib import Path

FIXTURES_DIR = Path(__file__).parent.parent.parent / "fixtures"


def load_url_list(category: str, filename: str) -> list[str]:
    """Load URLs from a fixture file.

    Args:
        category: URL category ('youtube' or 'webpages')
        filename: Name of the URL list file

    Returns:
        List of URLs (comments and empty lines filtered out)
    """
    path = FIXTURES_DIR / "urls" / category / filename
    if not path.exists():
        raise FileNotFoundError(f"URL list not found: {path}")

    return [
        line.strip()
        for line in path.read_text().splitlines()
        if line.strip() and not line.startswith("#")
    ]


def get_first_url(category: str, filename: str) -> str:
    """Get the first URL from a list file.

    Useful for quick single-item tests.

    Args:
        category: URL category ('youtube' or 'webpages')
        filename: Name of the URL list file

    Returns:
        First URL in the list

    Raises:
        ValueError: If the list is empty
    """
    urls = load_url_list(category, filename)
    if not urls:
        raise ValueError(f"No URLs found in {category}/{filename}")
    return urls[0]


def get_document(doc_type: str, filename: str) -> Path:
    """Get path to a document fixture.

    Args:
        doc_type: Document type ('pdf', 'docx', 'xlsx', 'pptx')
        filename: Name of the document file

    Returns:
        Path to the document

    Raises:
        FileNotFoundError: If document doesn't exist
    """
    path = FIXTURES_DIR / "documents" / doc_type / filename
    if not path.exists():
        raise FileNotFoundError(f"Document not found: {path}")
    return path


def get_audio(filename: str) -> Path:
    """Get path to an audio fixture.

    Args:
        filename: Name of the audio file

    Returns:
        Path to the audio file

    Raises:
        FileNotFoundError: If file doesn't exist
    """
    path = FIXTURES_DIR / "audio" / filename
    if not path.exists():
        raise FileNotFoundError(f"Audio file not found: {path}")
    return path


def get_video(filename: str) -> Path:
    """Get path to a video fixture.

    Args:
        filename: Name of the video file

    Returns:
        Path to the video file

    Raises:
        FileNotFoundError: If file doesn't exist
    """
    path = FIXTURES_DIR / "video" / filename
    if not path.exists():
        raise FileNotFoundError(f"Video file not found: {path}")
    return path
