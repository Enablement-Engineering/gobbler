"""Unit tests for frontmatter generation utilities."""

import pytest
from unittest.mock import patch
from datetime import datetime, timezone

from gobbler_mcp.utils.frontmatter import (
    create_frontmatter,
    get_iso8601_timestamp,
    count_words,
    create_youtube_frontmatter,
    create_webpage_frontmatter,
    create_document_frontmatter,
    create_audio_frontmatter,
)


class TestBasicFrontmatter:
    """Test basic frontmatter creation functionality."""

    def test_create_frontmatter_simple_metadata(self):
        """Test creating frontmatter with simple key-value pairs."""
        metadata = {
            "title": "Test Document",
            "author": "Test Author",
            "count": 42,
        }

        result = create_frontmatter(metadata)

        assert result.startswith("---\n")
        assert result.endswith("---\n")  # Fixed: no double newline
        assert "title: Test Document" in result
        assert "author: Test Author" in result
        assert "count: 42" in result

    def test_create_frontmatter_with_special_characters(self):
        """Test that special characters in strings are properly quoted."""
        metadata = {
            "title": "Title: With Colon",
            "description": "Description # with hash",
        }

        result = create_frontmatter(metadata)

        # Values with colons or hashes should be quoted
        assert '"Title: With Colon"' in result
        assert '"Description # with hash"' in result

    def test_create_frontmatter_with_different_types(self):
        """Test frontmatter with different value types."""
        metadata = {
            "string_val": "test",
            "int_val": 123,
            "float_val": 45.67,
            "bool_val": True,
            "null_val": None,
        }

        result = create_frontmatter(metadata)

        assert "string_val: test" in result
        assert "int_val: 123" in result
        assert "float_val: 45.67" in result
        assert "bool_val: True" in result
        assert "null_val: null" in result


class TestTimestampGeneration:
    """Test ISO 8601 timestamp generation."""

    def test_get_iso8601_timestamp_format(self):
        """Test that timestamp is in correct ISO 8601 format."""
        timestamp = get_iso8601_timestamp()

        # Should match format: YYYY-MM-DDTHH:MM:SSZ
        assert len(timestamp) == 20
        assert timestamp[4] == "-"
        assert timestamp[7] == "-"
        assert timestamp[10] == "T"
        assert timestamp[13] == ":"
        assert timestamp[16] == ":"
        assert timestamp[-1] == "Z"

    @patch("gobbler_mcp.utils.frontmatter.datetime")
    def test_get_iso8601_timestamp_uses_utc(self, mock_datetime):
        """Test that timestamp uses UTC timezone."""
        # Mock datetime to return a fixed time
        mock_now = datetime(2025, 10, 3, 14, 30, 45, tzinfo=timezone.utc)
        mock_datetime.now.return_value = mock_now

        timestamp = get_iso8601_timestamp()

        mock_datetime.now.assert_called_once_with(timezone.utc)
        assert timestamp == "2025-10-03T14:30:45Z"


class TestWordCounting:
    """Test word counting functionality."""

    def test_count_words_simple_text(self):
        """Test word counting with simple text."""
        text = "Hello world this is a test"
        assert count_words(text) == 6

    def test_count_words_empty_string(self):
        """Test word counting with empty string."""
        assert count_words("") == 0

    def test_count_words_with_multiple_spaces(self):
        """Test word counting handles multiple spaces correctly."""
        text = "Hello    world   test"
        # split() handles multiple spaces automatically
        assert count_words(text) == 3

    def test_count_words_with_newlines(self):
        """Test word counting with newlines."""
        text = "Hello\nworld\ntest"
        assert count_words(text) == 3


class TestYouTubeFrontmatter:
    """Test YouTube-specific frontmatter generation."""

    @patch("gobbler_mcp.utils.frontmatter.get_iso8601_timestamp")
    def test_create_youtube_frontmatter_minimal(self, mock_timestamp):
        """Test YouTube frontmatter with minimal required fields."""
        mock_timestamp.return_value = "2025-10-03T00:00:00Z"

        result = create_youtube_frontmatter(
            video_url="https://youtube.com/watch?v=test123",
            video_id="test123",
            duration=180,
            language="en",
            word_count=500,
        )

        assert '"https://youtube.com/watch?v=test123"' in result  # URLs are quoted
        assert "type: youtube_transcript" in result
        assert "video_id: test123" in result
        assert "duration: 180" in result
        assert "language: en" in result
        assert "word_count: 500" in result
        assert '"2025-10-03T00:00:00Z"' in result  # Timestamps are quoted (contain :)

    @patch("gobbler_mcp.utils.frontmatter.get_iso8601_timestamp")
    def test_create_youtube_frontmatter_with_optionals(self, mock_timestamp):
        """Test YouTube frontmatter with all optional fields."""
        mock_timestamp.return_value = "2025-10-03T00:00:00Z"

        result = create_youtube_frontmatter(
            video_url="https://youtube.com/watch?v=test123",
            video_id="test123",
            duration=180,
            language="en",
            word_count=500,
            title="Test Video",
            channel="Test Channel",
            thumbnail="https://example.com/thumb.jpg",
            description="Test description",
        )

        assert "title: Test Video" in result
        assert "channel: Test Channel" in result
        assert '"https://example.com/thumb.jpg"' in result  # URLs are quoted
        assert "description: Test description" in result


class TestWebpageFrontmatter:
    """Test webpage-specific frontmatter generation."""

    @patch("gobbler_mcp.utils.frontmatter.get_iso8601_timestamp")
    def test_create_webpage_frontmatter(self, mock_timestamp):
        """Test webpage frontmatter generation."""
        mock_timestamp.return_value = "2025-10-03T00:00:00Z"

        result = create_webpage_frontmatter(
            url="https://example.com/article",
            title="Test Article",
            word_count=1200,
            conversion_time_ms=5000,
        )

        assert '"https://example.com/article"' in result  # URLs are quoted
        assert "type: webpage" in result
        assert "title: Test Article" in result
        assert "word_count: 1200" in result
        assert "conversion_time_ms: 5000" in result
        assert '"2025-10-03T00:00:00Z"' in result  # Timestamps are quoted


class TestDocumentFrontmatter:
    """Test document-specific frontmatter generation."""

    @patch("gobbler_mcp.utils.frontmatter.get_iso8601_timestamp")
    def test_create_document_frontmatter(self, mock_timestamp):
        """Test document frontmatter generation."""
        mock_timestamp.return_value = "2025-10-03T00:00:00Z"

        result = create_document_frontmatter(
            file_path="/path/to/document.pdf",
            format="pdf",
            pages=10,
            word_count=3000,
            conversion_time_ms=15000,
        )

        assert "source: /path/to/document.pdf" in result
        assert "type: document" in result
        assert "format: pdf" in result
        assert "pages: 10" in result
        assert "word_count: 3000" in result
        assert "conversion_time_ms: 15000" in result
        assert '"2025-10-03T00:00:00Z"' in result  # Timestamps are quoted


class TestAudioFrontmatter:
    """Test audio-specific frontmatter generation."""

    @patch("gobbler_mcp.utils.frontmatter.get_iso8601_timestamp")
    def test_create_audio_frontmatter(self, mock_timestamp):
        """Test audio frontmatter generation."""
        mock_timestamp.return_value = "2025-10-03T00:00:00Z"

        result = create_audio_frontmatter(
            file_path="/path/to/audio.mp3",
            duration=240,
            language="en",
            model="small",
            word_count=800,
            conversion_time_ms=12000,
        )

        assert "source: /path/to/audio.mp3" in result
        assert "type: audio_transcript" in result
        assert "duration: 240" in result
        assert "language: en" in result
        assert "model: small" in result
        assert "word_count: 800" in result
        assert "conversion_time_ms: 12000" in result
        assert '"2025-10-03T00:00:00Z"' in result  # Timestamps are quoted
