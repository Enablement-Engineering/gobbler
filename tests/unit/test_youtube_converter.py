"""Unit tests for YouTube converter module."""

import pytest
from unittest.mock import MagicMock, patch

from gobbler_mcp.converters.youtube import (
    extract_video_id,
    format_timestamp,
    get_video_metadata,
    convert_youtube_to_markdown,
)
from youtube_transcript_api import (
    NoTranscriptFound,
    TranscriptsDisabled,
    VideoUnavailable,
)


class TestVideoIdExtraction:
    """Test video ID extraction from various YouTube URL formats."""

    def test_extract_video_id_standard_url(self):
        """Test extracting video ID from standard youtube.com URL."""
        url = "https://youtube.com/watch?v=dQw4w9WgXcQ"
        assert extract_video_id(url) == "dQw4w9WgXcQ"

    def test_extract_video_id_short_url(self):
        """Test extracting video ID from youtu.be short URL."""
        url = "https://youtu.be/dQw4w9WgXcQ"
        assert extract_video_id(url) == "dQw4w9WgXcQ"

    def test_extract_video_id_with_www(self):
        """Test extracting video ID from URL with www prefix."""
        url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
        assert extract_video_id(url) == "dQw4w9WgXcQ"

    def test_extract_video_id_http_protocol(self):
        """Test extracting video ID from HTTP (not HTTPS) URL."""
        url = "http://youtube.com/watch?v=dQw4w9WgXcQ"
        assert extract_video_id(url) == "dQw4w9WgXcQ"

    def test_extract_video_id_invalid_format_raises_error(self):
        """Test that invalid URL format raises ValueError."""
        invalid_urls = [
            "not a url",
            "https://example.com",
            "youtube.com/watch?v=abc",
            "https://youtube.com/watch?v=toolong123",
            "https://youtube.com/watch?v=short1",
        ]
        for url in invalid_urls:
            with pytest.raises(ValueError, match="Invalid YouTube URL format"):
                extract_video_id(url)


class TestTimestampFormatting:
    """Test timestamp formatting from seconds to HH:MM:SS format."""

    def test_format_timestamp_under_hour(self):
        """Test formatting timestamps under 1 hour."""
        assert format_timestamp(0) == "00:00"
        assert format_timestamp(30) == "00:30"
        assert format_timestamp(90) == "01:30"
        assert format_timestamp(599) == "09:59"

    def test_format_timestamp_over_hour(self):
        """Test formatting timestamps over 1 hour."""
        assert format_timestamp(3600) == "01:00:00"
        assert format_timestamp(3661) == "01:01:01"
        assert format_timestamp(7384) == "02:03:04"

    def test_format_timestamp_with_decimals(self):
        """Test formatting timestamps with decimal seconds."""
        assert format_timestamp(90.5) == "01:30"
        assert format_timestamp(3661.9) == "01:01:01"


class TestVideoMetadata:
    """Test video metadata extraction using yt-dlp."""

    @patch("gobbler_mcp.converters.youtube.yt_dlp.YoutubeDL")
    def test_get_video_metadata_success(self, mock_ytdl):
        """Test successful metadata extraction."""
        mock_instance = MagicMock()
        mock_instance.extract_info.return_value = {
            "title": "Test Video",
            "channel": "Test Channel",
            "uploader": "Test Uploader",
            "thumbnail": "https://example.com/thumb.jpg",
            "description": "Test description",
        }
        mock_ytdl.return_value.__enter__.return_value = mock_instance

        result = get_video_metadata("https://youtube.com/watch?v=test123")

        assert result["title"] == "Test Video"
        assert result["channel"] == "Test Channel"
        assert result["thumbnail"] == "https://example.com/thumb.jpg"
        assert result["description"] == "Test description"

    @patch("gobbler_mcp.converters.youtube.yt_dlp.YoutubeDL")
    def test_get_video_metadata_uses_uploader_fallback(self, mock_ytdl):
        """Test that uploader is used when channel is not available."""
        mock_instance = MagicMock()
        mock_instance.extract_info.return_value = {
            "title": "Test Video",
            "uploader": "Test Uploader",
            "thumbnail": "https://example.com/thumb.jpg",
            "description": "Test description",
        }
        mock_ytdl.return_value.__enter__.return_value = mock_instance

        result = get_video_metadata("https://youtube.com/watch?v=test123")

        assert result["channel"] == "Test Uploader"

    @patch("gobbler_mcp.converters.youtube.yt_dlp.YoutubeDL")
    def test_get_video_metadata_failure_returns_none(self, mock_ytdl):
        """Test that metadata extraction failure returns None values."""
        mock_instance = MagicMock()
        mock_instance.extract_info.side_effect = Exception("Network error")
        mock_ytdl.return_value.__enter__.return_value = mock_instance

        result = get_video_metadata("https://youtube.com/watch?v=test123")

        assert result["title"] is None
        assert result["channel"] is None
        assert result["thumbnail"] is None
        assert result["description"] is None


class TestYouTubeConversion:
    """Test full YouTube to markdown conversion."""

    @pytest.mark.asyncio
    @patch("gobbler_mcp.converters.youtube.get_video_metadata")
    @patch("gobbler_mcp.converters.youtube.YouTubeTranscriptApi")
    async def test_convert_youtube_basic(self, mock_api_class, mock_metadata):
        """Test basic YouTube conversion without timestamps."""
        # Mock metadata
        mock_metadata.return_value = {
            "title": "Test Video",
            "channel": "Test Channel",
            "thumbnail": "https://example.com/thumb.jpg",
            "description": "Test description",
        }

        # Mock transcript API
        mock_api = MagicMock()
        mock_api_class.return_value = mock_api

        # Mock transcript entries
        mock_entry1 = MagicMock()
        mock_entry1.text = "Hello world"
        mock_entry1.start = 0.0
        mock_entry1.duration = 2.5

        mock_entry2 = MagicMock()
        mock_entry2.text = "This is a test"
        mock_entry2.start = 2.5
        mock_entry2.duration = 3.0

        mock_transcript = MagicMock()
        mock_transcript.fetch.return_value = [mock_entry1, mock_entry2]
        mock_transcript.language_code = "en"

        mock_list = MagicMock()
        mock_list.find_generated_transcript.return_value = mock_transcript
        mock_api.list.return_value = mock_list

        # Execute conversion
        markdown, metadata = await convert_youtube_to_markdown(
            "https://youtube.com/watch?v=dQw4w9WgXcQ",
            include_timestamps=False,
            language="auto",
        )

        # Verify markdown structure
        assert "---" in markdown  # Frontmatter present
        assert '"https://youtube.com/watch?v=dQw4w9WgXcQ"' in markdown  # URLs are quoted
        assert "type: youtube_transcript" in markdown
        assert "title: Test Video" in markdown
        assert "# Video Transcript" in markdown
        assert "Hello world" in markdown
        assert "This is a test" in markdown

        # Verify metadata
        assert metadata["video_id"] == "dQw4w9WgXcQ"
        assert metadata["title"] == "Test Video"
        assert metadata["channel"] == "Test Channel"
        assert metadata["language"] == "en"
        assert metadata["duration"] == 5  # 2.5 + 3.0 rounded
        assert metadata["word_count"] > 0

    @pytest.mark.asyncio
    @patch("gobbler_mcp.converters.youtube.get_video_metadata")
    @patch("gobbler_mcp.converters.youtube.YouTubeTranscriptApi")
    async def test_convert_youtube_with_timestamps(self, mock_api_class, mock_metadata):
        """Test YouTube conversion with timestamps enabled."""
        # Mock metadata
        mock_metadata.return_value = {
            "title": "Test Video",
            "channel": "Test Channel",
            "thumbnail": None,
            "description": None,
        }

        # Mock transcript API
        mock_api = MagicMock()
        mock_api_class.return_value = mock_api

        mock_entry = MagicMock()
        mock_entry.text = "Hello"
        mock_entry.start = 90.0  # 1:30
        mock_entry.duration = 2.0

        mock_transcript = MagicMock()
        mock_transcript.fetch.return_value = [mock_entry]
        mock_transcript.language_code = "en"

        mock_list = MagicMock()
        mock_list.find_generated_transcript.return_value = mock_transcript
        mock_api.list.return_value = mock_list

        # Execute conversion with timestamps
        markdown, _ = await convert_youtube_to_markdown(
            "https://youtube.com/watch?v=dQw4w9WgXcQ",
            include_timestamps=True,
        )

        # Verify timestamp format
        assert "[01:30]" in markdown

    @pytest.mark.asyncio
    @patch("gobbler_mcp.converters.youtube.get_video_metadata")
    @patch("gobbler_mcp.converters.youtube.YouTubeTranscriptApi")
    async def test_convert_youtube_specific_language(self, mock_api_class, mock_metadata):
        """Test YouTube conversion with specific language selection."""
        mock_metadata.return_value = {
            "title": "Test Video",
            "channel": "Test Channel",
            "thumbnail": None,
            "description": None,
        }

        mock_api = MagicMock()
        mock_api_class.return_value = mock_api

        mock_entry = MagicMock()
        mock_entry.text = "Hola mundo"
        mock_entry.start = 0.0
        mock_entry.duration = 2.0

        mock_transcript = MagicMock()
        mock_transcript.fetch.return_value = [mock_entry]

        mock_list = MagicMock()
        mock_list.find_transcript.return_value = mock_transcript
        mock_api.list.return_value = mock_list

        # Execute with specific language
        markdown, metadata = await convert_youtube_to_markdown(
            "https://youtube.com/watch?v=dQw4w9WgXcQ",
            language="es",
        )

        # Verify language in metadata
        assert metadata["language"] == "es"
        assert "Hola mundo" in markdown

    @pytest.mark.asyncio
    @patch("gobbler_mcp.converters.youtube.extract_video_id")
    async def test_convert_youtube_invalid_url_raises_error(self, mock_extract):
        """Test that invalid URL raises ValueError."""
        mock_extract.side_effect = ValueError("Invalid YouTube URL format")

        with pytest.raises(ValueError, match="Invalid YouTube URL format"):
            await convert_youtube_to_markdown("not a valid url")

    @pytest.mark.asyncio
    @patch("gobbler_mcp.converters.youtube.get_video_metadata")
    @patch("gobbler_mcp.converters.youtube.YouTubeTranscriptApi")
    async def test_convert_youtube_no_transcript_raises_error(self, mock_api_class, mock_metadata):
        """Test that missing transcript raises appropriate error."""
        mock_metadata.return_value = {
            "title": "Test Video",
            "channel": "Test Channel",
            "thumbnail": None,
            "description": None,
        }

        mock_api = MagicMock()
        mock_api_class.return_value = mock_api
        mock_api.list.side_effect = TranscriptsDisabled("video_id")

        with pytest.raises(TranscriptsDisabled):
            await convert_youtube_to_markdown("https://youtube.com/watch?v=dQw4w9WgXcQ")
