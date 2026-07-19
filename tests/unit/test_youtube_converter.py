"""Unit tests for YouTube converter module."""

import asyncio
import json
import sys
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import httpx
import pytest
from youtube_transcript_api import (
    TranscriptsDisabled,
)

from gobbler_core.config import Config
from gobbler_core.converters.youtube import (
    convert_youtube_to_markdown,
    extract_video_id,
    format_timestamp,
    get_video_metadata,
)
from gobbler_core.converters.youtube_frames import (
    FrameExtractionResult,
    FrameFailure,
    VideoFrameArtifact,
    YouTubeFrameError,
    YouTubeFrameRequest,
    YouTubeStreamInfo,
)
from gobbler_core.providers.youtube import (
    AutoFallbackProvider,
    TranscriptAPIProvider,
    TranscriptProvider,
    TranscriptResult,
    TranscriptSegment,
    YouTubeTranscriptAPIProvider,
    YouTubeTranscriptError,
    create_provider_from_config,
    is_youtube_rate_limit_error,
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
            "https://youtube.com/watch?v=dQw4w9WgXcQextra",
            "https://youtu.be/dQw4w9WgXcQextra",
        ]
        for url in invalid_urls:
            with pytest.raises(ValueError, match="Invalid YouTube URL format"):
                extract_video_id(url)

    def test_extract_video_id_allows_supported_suffix_delimiters(self):
        """Test extracting video ID when supported URL suffixes are present."""
        video_id = "dQw4w9WgXcQ"
        urls = [
            f"https://youtube.com/watch?v={video_id}&t=10",
            f"https://youtube.com/watch?v={video_id}#fragment",
            f"https://youtu.be/{video_id}?si=abc",
        ]
        for url in urls:
            assert extract_video_id(url) == video_id


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

    @patch("gobbler_core.converters.youtube.yt_dlp.YoutubeDL")
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

    @patch("gobbler_core.converters.youtube.yt_dlp.YoutubeDL")
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

    @patch("gobbler_core.converters.youtube.yt_dlp.YoutubeDL")
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


def create_mock_provider(segments, language="en", metadata=None):
    """Create a mock provider that returns given segments."""
    mock_provider = MagicMock(spec=TranscriptProvider)
    mock_provider.fetch.return_value = TranscriptResult(
        segments=[TranscriptSegment(**s) for s in segments],
        language=language,
        metadata=metadata or {},
    )
    return mock_provider


class TestYouTubeProviderRateLimits:
    """Test YouTube provider rate-limit classification."""

    def test_video_id_containing_429_is_not_rate_limit(self):
        """Test a transcript error with 429 only in the video ID is not rate limited."""
        error_text = (
            "Could not retrieve a transcript for the video abc429defgh! "
            "This is most likely caused by: Subtitles are disabled for this video"
        )

        assert is_youtube_rate_limit_error(error_text) is False

    def test_retry_library_429_response_text_is_rate_limit(self):
        """Test retry-library 429 response text is classified as rate limited."""
        error_text = "ResponseError('too many 429 error responses')"

        assert is_youtube_rate_limit_error(error_text) is True

    @patch("gobbler_core.providers.youtube.YouTubeTranscriptApi")
    def test_youtube_transcript_api_429_raises_actionable_error(self, mock_api):
        """Test timedtext HTTP 429 responses become actionable diagnostics."""
        mock_instance = MagicMock()
        mock_instance.list.side_effect = RuntimeError(
            "HTTP 429 Too Many Requests for url: "
            "https://www.youtube.com/api/timedtext?v=dQw4w9WgXcQ"
        )
        mock_api.return_value = mock_instance

        provider = YouTubeTranscriptAPIProvider()

        with pytest.raises(YouTubeTranscriptError) as exc_info:
            provider.fetch("dQw4w9WgXcQ", language="en")

        error = exc_info.value
        dumped = json.dumps(error.diagnostics)
        assert "rate limited" in str(error)
        assert "Wait 10-15 minutes" in str(error)
        assert "TRANSCRIPTAPI_KEY" in str(error)
        assert error.diagnostics["error_type"] == "rate_limited"
        assert error.diagnostics["status_code"] == 429
        assert error.diagnostics["provider"] == "youtube-transcript-api"
        assert error.diagnostics["video_id"] == "dQw4w9WgXcQ"
        assert error.diagnostics["proxy_configured"] is False
        assert "api/timedtext" not in dumped

    @patch("gobbler_core.providers.youtube.httpx.Client")
    def test_transcriptapi_429_raises_actionable_error(self, mock_client):
        """Test TranscriptAPI HTTP 429 responses include retry diagnostics."""

        class FakeClient:
            """Context manager returning a mocked TranscriptAPI 429 response."""

            def __init__(self, *_args, **_kwargs):
                """Accept httpx.Client constructor arguments."""

            def __enter__(self):
                """Return the fake client."""
                return self

            def __exit__(self, *_args):
                """Exit the fake client context."""

            def get(self, *_args, **_kwargs):
                """Return a rate-limited response."""
                request = httpx.Request("GET", "https://transcriptapi.com/test")
                return httpx.Response(
                    429,
                    headers={"Retry-After": "120"},
                    request=request,
                )

        mock_client.side_effect = FakeClient
        provider = TranscriptAPIProvider(api_key="secret-token")

        with pytest.raises(YouTubeTranscriptError) as exc_info:
            provider.fetch("dQw4w9WgXcQ", language="en")

        error = exc_info.value
        dumped = json.dumps({"message": str(error), "diagnostics": error.diagnostics})
        assert "TranscriptAPI rate limited" in str(error)
        assert "Retry after 120s" in str(error)
        assert error.diagnostics["provider"] == "transcriptapi"
        assert error.diagnostics["retry_after_seconds"] == 120
        assert "secret-token" not in dumped

    @patch("gobbler_core.providers.youtube.httpx.Client")
    def test_transcriptapi_402_sanitizes_action_url(self, mock_client):
        """Test TranscriptAPI billing action URLs do not expose query or fragment data."""

        class FakeClient:
            """Context manager returning a mocked TranscriptAPI 402 response."""

            def __init__(self, *_args, **_kwargs):
                """Accept httpx.Client constructor arguments."""

            def __enter__(self):
                """Return the fake client."""
                return self

            def __exit__(self, *_args):
                """Exit the fake client context."""

            def get(self, *_args, **_kwargs):
                """Return a payment-required response with a sensitive action URL."""
                request = httpx.Request("GET", "https://transcriptapi.com/test")
                return httpx.Response(
                    402,
                    json={
                        "detail": {
                            "message": "You don't have an active paid plan yet.",
                            "action_url": (
                                "https://transcriptapi.com/billing?"
                                "session_id=cs_secret_123&token=abc#checkout"
                            ),
                        }
                    },
                    request=request,
                )

        mock_client.side_effect = FakeClient
        provider = TranscriptAPIProvider(api_key="secret-token")

        with pytest.raises(YouTubeTranscriptError) as exc_info:
            provider.fetch("dQw4w9WgXcQ", language="en")

        error = exc_info.value
        dumped = json.dumps({"message": str(error), "diagnostics": error.diagnostics})
        assert "https://transcriptapi.com/billing" in str(error)
        assert error.diagnostics["provider"] == "transcriptapi"
        assert error.diagnostics["error_type"] == "billing_required"
        assert error.diagnostics["status_code"] == 402
        assert "billing" in error.diagnostics["next_actions"][0].lower()
        assert "secret-token" not in dumped
        assert "session_id" not in dumped
        assert "cs_secret_123" not in dumped
        assert "token" not in dumped
        assert "checkout" not in dumped
        assert error.diagnostics["action_url"] == "https://transcriptapi.com/billing"


class TestYouTubeProviderConfigFactory:
    """Test config-driven YouTube provider construction."""

    def test_default_config_with_transcriptapi_key_uses_auto_fallback(
        self,
        tmp_path,
        monkeypatch,
    ):
        """Default provider preserves legacy AutoFallbackProvider behavior with a key."""
        config = Config(config_path=tmp_path / "missing.yml")
        monkeypatch.setenv("TRANSCRIPTAPI_KEY", "test-api-key")

        with patch("gobbler_core.providers.youtube.get_youtube_proxy_config", return_value=None):
            provider = create_provider_from_config(config)

        assert isinstance(provider, AutoFallbackProvider)

    def test_default_config_without_transcriptapi_key_uses_free_provider(
        self,
        tmp_path,
        monkeypatch,
    ):
        """Default provider without a key remains the free YouTube provider."""
        config = Config(config_path=tmp_path / "missing.yml")
        monkeypatch.delenv("TRANSCRIPTAPI_KEY", raising=False)

        with patch("gobbler_core.providers.youtube.get_youtube_proxy_config", return_value=None):
            provider = create_provider_from_config(config)

        assert isinstance(provider, YouTubeTranscriptAPIProvider)

    def test_explicit_transcriptapi_provider_remains_paid_provider(
        self,
        tmp_path,
        monkeypatch,
    ):
        """Explicit transcriptapi selection creates TranscriptAPIProvider, not fallback."""
        config_path = tmp_path / "config.yml"
        config_path.write_text(
            "providers:\n  youtube:\n    default: transcriptapi\n    transcriptapi: {}\n"
        )
        config = Config(config_path=config_path)
        monkeypatch.setenv("TRANSCRIPTAPI_KEY", "test-api-key")

        with patch("gobbler_core.providers.youtube.get_youtube_proxy_config", return_value=None):
            provider = create_provider_from_config(config)

        assert isinstance(provider, TranscriptAPIProvider)

    def test_auto_provider_with_transcriptapi_key_uses_auto_fallback(
        self,
        tmp_path,
        monkeypatch,
    ):
        """Config provider=auto uses the implicit TranscriptAPI fallback path."""
        config_path = tmp_path / "config.yml"
        config_path.write_text("providers:\n  youtube:\n    default: auto\n    auto: {}\n")
        config = Config(config_path=config_path)
        monkeypatch.setenv("TRANSCRIPTAPI_KEY", "test-api-key")

        with patch("gobbler_core.providers.youtube.get_youtube_proxy_config", return_value=None):
            provider = create_provider_from_config(config)

        assert isinstance(provider, AutoFallbackProvider)

    def test_explicit_scalar_fallback_condition_uses_auto_fallback(
        self,
        tmp_path,
        monkeypatch,
    ):
        """Explicit scalar fallback conditions are treated as one condition."""
        config_path = tmp_path / "config.yml"
        config_path.write_text(
            "providers:\n"
            "  youtube:\n"
            "    default: youtube-transcript-api\n"
            "    youtube-transcript-api:\n"
            "      fallback:\n"
            "        provider: transcriptapi\n"
            '        "on": rate_limited\n'
        )
        config = Config(config_path=config_path)
        monkeypatch.setenv("TRANSCRIPTAPI_KEY", "test-api-key")

        with patch("gobbler_core.providers.youtube.get_youtube_proxy_config", return_value=None):
            provider = create_provider_from_config(config)

        assert isinstance(provider, AutoFallbackProvider)

    def test_explicit_numeric_fallback_condition_uses_auto_fallback(
        self,
        tmp_path,
        monkeypatch,
    ):
        """Explicit numeric 429 fallback conditions are normalized to strings."""
        config_path = tmp_path / "config.yml"
        config_path.write_text(
            "providers:\n"
            "  youtube:\n"
            "    default: youtube-transcript-api\n"
            "    youtube-transcript-api:\n"
            "      fallback:\n"
            "        provider: transcriptapi\n"
            '        "on": [429]\n'
        )
        config = Config(config_path=config_path)
        monkeypatch.setenv("TRANSCRIPTAPI_KEY", "test-api-key")

        with patch("gobbler_core.providers.youtube.get_youtube_proxy_config", return_value=None):
            provider = create_provider_from_config(config)

        assert isinstance(provider, AutoFallbackProvider)

    def test_unquoted_yaml_on_fallback_key_uses_auto_fallback(
        self,
        tmp_path,
        monkeypatch,
    ):
        """YAML 1.1 boolean parsing of unquoted on is tolerated for docs examples."""
        config_path = tmp_path / "config.yml"
        config_path.write_text(
            "providers:\n"
            "  youtube:\n"
            "    default: youtube-transcript-api\n"
            "    youtube-transcript-api:\n"
            "      fallback:\n"
            "        provider: transcriptapi\n"
            "        on: rate_limited\n"
        )
        config = Config(config_path=config_path)
        monkeypatch.setenv("TRANSCRIPTAPI_KEY", "test-api-key")

        with patch("gobbler_core.providers.youtube.get_youtube_proxy_config", return_value=None):
            provider = create_provider_from_config(config)

        assert isinstance(provider, AutoFallbackProvider)


class TestYouTubeConversion:
    """Test full YouTube to markdown conversion."""

    @pytest.mark.asyncio
    @patch("gobbler_core.converters.youtube.get_video_metadata")
    @patch("gobbler_core.converters.youtube.create_provider_from_config")
    @patch("gobbler_core.converters.youtube.get_config")
    async def test_convert_youtube_default_provider_uses_config_factory(
        self,
        mock_get_config,
        mock_create_provider_from_config,
        mock_metadata,
    ):
        """Test default conversion builds the provider from loaded config."""
        mock_metadata.return_value = {
            "title": "Test Video",
            "channel": "Test Channel",
            "thumbnail": None,
            "description": None,
        }
        mock_config = MagicMock()
        mock_get_config.return_value = mock_config
        mock_provider = create_mock_provider(
            [{"text": "Configured provider transcript", "start": 0.0, "duration": 1.0}]
        )
        mock_create_provider_from_config.return_value = mock_provider

        markdown, metadata = await convert_youtube_to_markdown(
            "https://youtube.com/watch?v=dQw4w9WgXcQ"
        )

        mock_get_config.assert_called_once_with()
        mock_create_provider_from_config.assert_called_once_with(mock_config)
        mock_provider.fetch.assert_called_once_with("dQw4w9WgXcQ", "auto")
        assert "Configured provider transcript" in markdown
        assert metadata["video_id"] == "dQw4w9WgXcQ"

    @pytest.mark.asyncio
    @patch("gobbler_core.converters.youtube.get_video_metadata")
    @patch("gobbler_core.converters.youtube.create_provider_from_config")
    @patch("gobbler_core.converters.youtube.get_config")
    async def test_convert_youtube_injected_provider_bypasses_config_factory(
        self,
        mock_get_config,
        mock_create_provider_from_config,
        mock_metadata,
    ):
        """Test explicitly injected providers bypass config-based construction."""
        mock_metadata.return_value = {
            "title": "Test Video",
            "channel": "Test Channel",
            "thumbnail": None,
            "description": None,
        }
        mock_provider = create_mock_provider(
            [{"text": "Injected provider transcript", "start": 0.0, "duration": 1.0}]
        )

        markdown, _ = await convert_youtube_to_markdown(
            "https://youtube.com/watch?v=dQw4w9WgXcQ",
            provider=mock_provider,
        )

        mock_get_config.assert_not_called()
        mock_create_provider_from_config.assert_not_called()
        mock_provider.fetch.assert_called_once_with("dQw4w9WgXcQ", "auto")
        assert "Injected provider transcript" in markdown

    @pytest.mark.asyncio
    @patch("gobbler_core.converters.youtube.get_video_metadata")
    @patch("gobbler_core.providers.youtube.TranscriptAPIProvider.fetch")
    async def test_convert_youtube_configured_transcriptapi_provider_is_used(
        self,
        mock_transcriptapi_fetch,
        mock_metadata,
        tmp_path,
        monkeypatch,
    ):
        """Test config selecting transcriptapi uses TranscriptAPIProvider."""
        config_path = tmp_path / "config.yml"
        config_path.write_text(
            "providers:\n  youtube:\n    default: transcriptapi\n    transcriptapi: {}\n"
        )
        config = Config(config_path=config_path)
        monkeypatch.setenv("TRANSCRIPTAPI_KEY", "test-api-key")
        mock_metadata.return_value = {
            "title": "Test Video",
            "channel": "Test Channel",
            "thumbnail": None,
            "description": None,
        }
        mock_transcriptapi_fetch.return_value = TranscriptResult(
            segments=[TranscriptSegment(text="Paid provider transcript", start=0.0, duration=1.0)],
            language="en",
            metadata={},
        )

        with patch("gobbler_core.converters.youtube.get_config", return_value=config):
            markdown, _ = await convert_youtube_to_markdown(
                "https://youtube.com/watch?v=dQw4w9WgXcQ"
            )

        mock_transcriptapi_fetch.assert_called_once_with("dQw4w9WgXcQ", "auto")
        assert "Paid provider transcript" in markdown

    @pytest.mark.asyncio
    @patch("gobbler_core.converters.youtube.get_video_metadata")
    async def test_convert_youtube_basic(self, mock_metadata):
        """Test basic YouTube conversion without timestamps."""
        mock_metadata.return_value = {
            "title": "Test Video",
            "channel": "Test Channel",
            "thumbnail": "https://example.com/thumb.jpg",
            "description": "Test description",
        }

        mock_provider = create_mock_provider(
            [
                {"text": "Hello world", "start": 0.0, "duration": 2.5},
                {"text": "This is a test", "start": 2.5, "duration": 3.0},
            ]
        )

        markdown, metadata = await convert_youtube_to_markdown(
            "https://youtube.com/watch?v=dQw4w9WgXcQ",
            include_timestamps=False,
            language="auto",
            provider=mock_provider,
        )

        assert "---" in markdown
        assert '"https://youtube.com/watch?v=dQw4w9WgXcQ"' in markdown
        assert "type: youtube_transcript" in markdown
        assert "title: Test Video" in markdown
        assert "# Video Transcript" in markdown
        assert "Hello world" in markdown
        assert "This is a test" in markdown

        assert metadata["video_id"] == "dQw4w9WgXcQ"
        assert metadata["title"] == "Test Video"
        assert metadata["channel"] == "Test Channel"
        assert metadata["language"] == "en"
        assert metadata["duration"] == 5
        assert metadata["word_count"] > 0

    @pytest.mark.asyncio
    @patch("gobbler_core.converters.youtube.get_video_metadata")
    async def test_convert_youtube_neutralizes_public_github_mentions(self, mock_metadata):
        """Test YouTube output cannot trigger GitHub mentions when pasted publicly."""
        mock_metadata.return_value = {
            "title": "Test Video",
            "channel": "Test Channel",
            "thumbnail": None,
            "description": "S/O @Ph4seOn3 for the edit. Contact user@example.com",
        }
        mock_provider = create_mock_provider(
            [
                {
                    "text": "Transcript thanks @octocat for reviewing.",
                    "start": 0.0,
                    "duration": 1.0,
                }
            ]
        )

        markdown, _ = await convert_youtube_to_markdown(
            "https://youtube.com/watch?v=dQw4w9WgXcQ",
            provider=mock_provider,
        )

        assert "@Ph4seOn3" not in markdown
        assert "@octocat" not in markdown
        assert "@\u200bPh4seOn3" in markdown
        assert "@\u200boctocat" in markdown
        assert "user@example.com" in markdown

    @pytest.mark.asyncio
    @patch("gobbler_core.converters.youtube.get_video_metadata")
    async def test_convert_youtube_with_timestamps(self, mock_metadata):
        """Test YouTube conversion with timestamps enabled."""
        mock_metadata.return_value = {
            "title": "Test Video",
            "channel": "Test Channel",
            "thumbnail": None,
            "description": None,
        }

        mock_provider = create_mock_provider(
            [
                {"text": "Hello", "start": 90.0, "duration": 2.0},
            ]
        )

        markdown, _ = await convert_youtube_to_markdown(
            "https://youtube.com/watch?v=dQw4w9WgXcQ",
            include_timestamps=True,
            provider=mock_provider,
        )

        assert "[01:30]" in markdown

    @pytest.mark.asyncio
    @patch("gobbler_core.converters.youtube.get_video_metadata")
    async def test_convert_youtube_specific_language(self, mock_metadata):
        """Test YouTube conversion with specific language selection."""
        mock_metadata.return_value = {
            "title": "Test Video",
            "channel": "Test Channel",
            "thumbnail": None,
            "description": None,
        }

        mock_provider = create_mock_provider(
            [{"text": "Hola mundo", "start": 0.0, "duration": 2.0}],
            language="es",
        )

        markdown, metadata = await convert_youtube_to_markdown(
            "https://youtube.com/watch?v=dQw4w9WgXcQ",
            language="es",
            provider=mock_provider,
        )

        assert metadata["language"] == "es"
        assert "Hola mundo" in markdown

    @pytest.mark.asyncio
    @patch("gobbler_core.converters.youtube.extract_video_id")
    async def test_convert_youtube_invalid_url_raises_error(self, mock_extract):
        """Test that invalid URL raises ValueError."""
        mock_extract.side_effect = ValueError("Invalid YouTube URL format")

        with pytest.raises(ValueError, match="Invalid YouTube URL format"):
            await convert_youtube_to_markdown("not a valid url")

    @pytest.mark.asyncio
    @patch("gobbler_core.converters.youtube.get_video_metadata")
    async def test_convert_youtube_no_transcript_raises_error(self, mock_metadata):
        """Test that missing transcript raises appropriate error with clean message."""
        mock_metadata.return_value = {
            "title": "Test Video",
            "channel": "Test Channel",
            "thumbnail": None,
            "description": None,
        }

        mock_provider = MagicMock(spec=TranscriptProvider)
        mock_provider.fetch.side_effect = TranscriptsDisabled("video_id")

        # Now we wrap noisy errors into clean RuntimeError messages
        with pytest.raises(RuntimeError, match="Transcript unavailable"):
            await convert_youtube_to_markdown(
                "https://youtube.com/watch?v=dQw4w9WgXcQ",
                provider=mock_provider,
            )

    @pytest.mark.asyncio
    @patch("gobbler_core.converters.youtube.get_video_metadata")
    async def test_convert_youtube_429_raises_actionable_error(self, mock_metadata):
        """Test plain provider 429 errors become actionable YouTube diagnostics."""
        mock_metadata.return_value = {
            "title": "Test Video",
            "channel": "Test Channel",
            "thumbnail": None,
            "description": None,
        }

        mock_provider = MagicMock(spec=TranscriptProvider)
        mock_provider.fetch.side_effect = RuntimeError(
            "HTTP 429 Too Many Requests for url: "
            "https://www.youtube.com/api/timedtext?v=dQw4w9WgXcQ"
        )

        with pytest.raises(YouTubeTranscriptError) as exc_info:
            await convert_youtube_to_markdown(
                "https://youtube.com/watch?v=dQw4w9WgXcQ",
                language="auto",
                provider=mock_provider,
            )

        error = exc_info.value
        assert "YouTube transcript fetch was rate limited" in str(error)
        assert "different video or caption language" in str(error)
        assert "another transcript source" in str(error)
        assert error.diagnostics["error_type"] == "rate_limited"
        assert error.diagnostics["status_code"] == 429
        assert error.diagnostics["video_id"] == "dQw4w9WgXcQ"
        assert error.diagnostics["language"] == "auto"

    @pytest.mark.asyncio
    @patch("gobbler_core.converters.youtube.get_video_metadata")
    async def test_convert_youtube_metrics_callback(self, mock_metadata):
        """Test that metrics callback is invoked."""
        mock_metadata.return_value = {
            "title": "Test Video",
            "channel": "Test Channel",
            "thumbnail": None,
            "description": None,
        }

        mock_provider = create_mock_provider(
            [
                {"text": "Test content", "start": 0.0, "duration": 1.0},
            ]
        )

        metrics_called = []

        def metrics_callback(converter_type, size_bytes):
            metrics_called.append((converter_type, size_bytes))

        await convert_youtube_to_markdown(
            "https://youtube.com/watch?v=dQw4w9WgXcQ",
            provider=mock_provider,
            metrics_callback=metrics_callback,
        )

        assert len(metrics_called) == 1
        assert metrics_called[0][0] == "youtube"
        assert metrics_called[0][1] > 0

    @pytest.mark.asyncio
    async def test_convert_youtube_timeout_raises_clean_error(self):
        """Test that conversion timeout becomes a clean RuntimeError."""

        mock_provider = MagicMock(spec=TranscriptProvider)
        mock_provider.fetch.side_effect = lambda *_args, **_kwargs: asyncio.run(asyncio.sleep(0.2))

        with (
            patch(
                "gobbler_core.converters.youtube.get_video_metadata",
                return_value={
                    "title": "Test Video",
                    "channel": "Test Channel",
                    "thumbnail": None,
                    "description": None,
                },
            ),
            pytest.raises(RuntimeError, match=r"timed out after 0\.01s"),
        ):
            await convert_youtube_to_markdown(
                "https://youtube.com/watch?v=dQw4w9WgXcQ",
                provider=mock_provider,
                timeout=0.01,
            )

    @pytest.mark.asyncio
    async def test_convert_youtube_augments_transcript_with_frames(self, tmp_path: Path) -> None:
        """A frame request appends a manifest without changing transcript providers."""
        provider = create_mock_provider([{"text": "Transcript", "start": 0, "duration": 3}])
        output = tmp_path / "video.md"
        artifact = VideoFrameArtifact(
            5.0,
            "00:05.000",
            tmp_path / "video.assets/frames/frame-001-00-00-05-000.jpg",
            "image/jpeg",
            "overview",
        )
        with (
            patch(
                "gobbler_core.converters.youtube.get_video_metadata",
                return_value={
                    "title": "Video",
                    "channel": "Channel",
                    "thumbnail": None,
                    "description": None,
                },
            ),
            patch("gobbler_core.converters.youtube.ensure_ffmpeg_available"),
            patch(
                "gobbler_core.converters.youtube.resolve_youtube_stream",
                return_value=YouTubeStreamInfo("signed-stream", 10.0),
            ),
            patch(
                "gobbler_core.converters.youtube.extract_youtube_frames",
                return_value=FrameExtractionResult(frames=[artifact], duration_seconds=10.0),
            ) as extract_frames,
        ):
            markdown, metadata = await convert_youtube_to_markdown(
                "https://youtube.com/watch?v=dQw4w9WgXcQ",
                provider=provider,
                frame_request=YouTubeFrameRequest(overview_count=1),
                output_path=output,
            )

        assert "# Video Transcript" in markdown
        assert "## Video Frames" in markdown
        assert metadata["frames"][0]["timestamp"] == "00:05.000"
        extract_frames.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_combined_markdown_reports_partial_frame_failures_safely(
        self, tmp_path: Path
    ) -> None:
        """Transcript Markdown includes the same sanitized partial-frame warning section."""
        provider = create_mock_provider([{"text": "Transcript", "start": 0, "duration": 3}])
        output = tmp_path / "video.md"
        frame_result = FrameExtractionResult(
            frames=[
                VideoFrameArtifact(
                    5.0,
                    "00:05.000",
                    tmp_path / "video.assets/frames/frame-001-00-00-05-000.jpg",
                    "image/jpeg",
                    "exact",
                )
            ],
            failures=[
                FrameFailure(
                    8.0,
                    "00:08.000",
                    "overview",
                    "ffmpeg_timeout",
                    (
                        "raw stderr https://media.invalid/video?signature=signed-secret "
                        "/Users/example/local-secret"
                    ),
                )
            ],
            duration_seconds=10.0,
        )
        with (
            patch(
                "gobbler_core.converters.youtube.get_video_metadata",
                return_value={
                    "title": "Video",
                    "channel": "Channel",
                    "thumbnail": None,
                    "description": None,
                },
            ),
            patch("gobbler_core.converters.youtube.ensure_ffmpeg_available"),
            patch(
                "gobbler_core.converters.youtube.resolve_youtube_stream",
                return_value=YouTubeStreamInfo("signed-stream", 10.0),
            ),
            patch(
                "gobbler_core.converters.youtube.extract_youtube_frames",
                return_value=frame_result,
            ),
        ):
            markdown, metadata = await convert_youtube_to_markdown(
                "https://youtube.com/watch?v=dQw4w9WgXcQ",
                provider=provider,
                frame_request=YouTubeFrameRequest(exact_timestamps=(5.0, 8.0)),
                output_path=output,
            )

        assert "# Video Transcript" in markdown
        assert "## Video Frames" in markdown
        assert "## Frame Warnings" in markdown
        assert "00:08.000" in markdown
        assert "overview" in markdown
        assert "ffmpeg_timeout" in markdown
        assert "FFmpeg timed out while extracting this frame" in markdown
        assert metadata["warnings"][0]["message"] == (
            "FFmpeg timed out while extracting this frame"
        )
        for secret in ("raw stderr", "signed-secret", "local-secret", "media.invalid"):
            assert secret not in markdown
            assert secret not in json.dumps(metadata)

    @pytest.mark.asyncio
    async def test_combined_frames_share_one_overall_timeout_budget(self, tmp_path: Path) -> None:
        """Transcript work and delayed frame extraction share one timeout budget."""
        provider = create_mock_provider([{"text": "Transcript", "start": 0, "duration": 3}])
        transcript_result = provider.fetch.return_value

        def delayed_fetch(*_args, **_kwargs):
            time.sleep(0.3)
            return transcript_result

        provider.fetch.side_effect = delayed_fetch
        extraction_started = False
        extraction_completed = False

        async def delayed_extraction(*_args, **_kwargs):
            nonlocal extraction_started, extraction_completed
            extraction_started = True
            await asyncio.sleep(0.3)
            extraction_completed = True
            return FrameExtractionResult(frames=[], duration_seconds=10.0)

        with (
            patch(
                "gobbler_core.converters.youtube.get_video_metadata",
                return_value={
                    "title": "Video",
                    "channel": "Channel",
                    "thumbnail": None,
                    "description": None,
                },
            ),
            patch("gobbler_core.converters.youtube.ensure_ffmpeg_available"),
            patch(
                "gobbler_core.converters.youtube.resolve_youtube_stream",
                return_value=YouTubeStreamInfo("signed-stream", 10.0),
            ),
            patch(
                "gobbler_core.converters.youtube.extract_youtube_frames",
                side_effect=delayed_extraction,
            ),
            pytest.raises(RuntimeError) as exc_info,
        ):
            await convert_youtube_to_markdown(
                "https://youtube.com/watch?v=dQw4w9WgXcQ",
                provider=provider,
                timeout=0.5,
                frame_request=YouTubeFrameRequest(overview_count=1),
                output_path=tmp_path / "video.md",
            )

        assert str(exc_info.value) == "YouTube conversion timed out after 0.5s"
        assert extraction_started is True
        assert extraction_completed is False

    @pytest.mark.asyncio
    async def test_convert_youtube_frames_only_never_constructs_provider(
        self, tmp_path: Path
    ) -> None:
        """Frames-only conversion does not construct or call transcript providers."""
        output = tmp_path / "frames.md"
        artifact = VideoFrameArtifact(
            5.0,
            "00:05.000",
            tmp_path / "frames.assets/frames/frame-001-00-00-05-000.jpg",
            "image/jpeg",
            "exact",
        )
        with (
            patch(
                "gobbler_core.converters.youtube.get_video_metadata",
                return_value={
                    "title": "Video",
                    "channel": "Channel",
                    "thumbnail": None,
                    "description": None,
                },
            ),
            patch("gobbler_core.converters.youtube.ensure_ffmpeg_available"),
            patch(
                "gobbler_core.converters.youtube.resolve_youtube_stream",
                return_value=YouTubeStreamInfo("signed-stream", 10.0),
            ),
            patch(
                "gobbler_core.converters.youtube.extract_youtube_frames",
                return_value=FrameExtractionResult(frames=[artifact], duration_seconds=10.0),
            ),
            patch("gobbler_core.converters.youtube.create_provider_from_config") as factory,
        ):
            markdown, metadata = await convert_youtube_to_markdown(
                "https://youtube.com/watch?v=dQw4w9WgXcQ",
                frame_request=YouTubeFrameRequest(exact_timestamps=(5.0,)),
                frames_only=True,
                output_path=output,
            )

        factory.assert_not_called()
        assert "type: youtube_frames" in markdown
        assert "# Video Frames" in markdown
        assert "# Video Transcript" not in markdown
        assert metadata["duration"] == 10.0

    @pytest.mark.asyncio
    async def test_frames_only_markdown_reports_partial_failures_and_omits_thumbnail_query(
        self, tmp_path: Path
    ) -> None:
        """Default Markdown exposes partial failures without retaining signed metadata URLs."""
        output = tmp_path / "frames.md"
        artifact = VideoFrameArtifact(
            5.0,
            "00:05.000",
            tmp_path / "frames.assets/frames/frame-001.jpg",
            "image/jpeg",
            "exact",
        )
        frame_result = FrameExtractionResult(
            frames=[artifact],
            failures=[
                FrameFailure(
                    8.0,
                    "00:08.000",
                    "range",
                    "ffmpeg_failed",
                    "FFmpeg could not decode this frame",
                )
            ],
            duration_seconds=10.0,
        )
        with (
            patch(
                "gobbler_core.converters.youtube.get_video_metadata",
                return_value={
                    "title": "Video",
                    "channel": "Channel",
                    "thumbnail": "https://i.ytimg.com/image.jpg?token=thumbnail-secret",
                    "description": None,
                },
            ),
            patch("gobbler_core.converters.youtube.ensure_ffmpeg_available"),
            patch(
                "gobbler_core.converters.youtube.resolve_youtube_stream",
                return_value=YouTubeStreamInfo("signed-stream", 10.0),
            ),
            patch(
                "gobbler_core.converters.youtube.extract_youtube_frames",
                return_value=frame_result,
            ),
        ):
            markdown, _metadata = await convert_youtube_to_markdown(
                "https://youtube.com/watch?v=dQw4w9WgXcQ",
                frame_request=YouTubeFrameRequest(exact_timestamps=(5.0, 8.0)),
                frames_only=True,
                output_path=output,
            )

        assert "## Frame Warnings" in markdown
        assert "00:08.000" in markdown
        assert "FFmpeg could not decode this frame" in markdown
        assert "thumbnail-secret" not in markdown

    def test_frames_only_timeout_does_not_wait_for_stalled_resolver(self, tmp_path: Path) -> None:
        """The CLI-facing event loop returns promptly after the overall deadline."""

        def stalled_resolver(_url: str) -> YouTubeStreamInfo:
            time.sleep(1.0)
            return YouTubeStreamInfo("signed-stream", 10.0)

        started = time.monotonic()
        with (
            patch("gobbler_core.converters.youtube.ensure_ffmpeg_available"),
            patch(
                "gobbler_core.converters.youtube.get_video_metadata",
                return_value={
                    "title": None,
                    "channel": None,
                    "thumbnail": None,
                    "description": None,
                },
            ),
            patch(
                "gobbler_core.converters.youtube.resolve_youtube_stream",
                side_effect=stalled_resolver,
            ),
            pytest.raises(RuntimeError, match="timed out"),
        ):
            asyncio.run(
                convert_youtube_to_markdown(
                    "https://youtube.com/watch?v=dQw4w9WgXcQ",
                    timeout=0.05,
                    frame_request=YouTubeFrameRequest(exact_timestamps=(1.0,)),
                    frames_only=True,
                    output_path=tmp_path / "frames.md",
                )
            )

        assert time.monotonic() - started < 0.5

    def test_frames_only_metadata_timeout_does_not_replace_process_stderr(
        self, tmp_path: Path
    ) -> None:
        """Detached optional metadata work never captures later CLI diagnostics."""

        class SlowYoutubeDL:
            """Minimal delayed yt-dlp context manager."""

            def __init__(self, *_args, **_kwargs) -> None:
                """Accept yt-dlp options."""

            def __enter__(self) -> "SlowYoutubeDL":
                """Enter the fake downloader."""
                return self

            def __exit__(self, *_args) -> None:
                """Exit the fake downloader."""

            def extract_info(self, *_args, **_kwargs) -> dict[str, str]:
                """Delay optional metadata beyond the overall deadline."""
                time.sleep(1.0)
                return {"title": "late"}

        original_stderr = sys.stderr
        with (
            patch("gobbler_core.converters.youtube.ensure_ffmpeg_available"),
            patch("gobbler_core.converters.youtube.yt_dlp.YoutubeDL", SlowYoutubeDL),
            pytest.raises(RuntimeError, match="timed out"),
        ):
            asyncio.run(
                convert_youtube_to_markdown(
                    "https://youtube.com/watch?v=dQw4w9WgXcQ",
                    timeout=0.05,
                    frame_request=YouTubeFrameRequest(exact_timestamps=(1.0,)),
                    frames_only=True,
                    output_path=tmp_path / "frames.md",
                )
            )

        assert sys.stderr is original_stderr

    @pytest.mark.asyncio
    async def test_frames_only_shares_one_overall_timeout_budget(self, tmp_path: Path) -> None:
        """Stream resolution and delayed frame extraction share one timeout budget."""
        extraction_started = False
        extraction_completed = False

        def delayed_stream_resolution(_url: str) -> YouTubeStreamInfo:
            time.sleep(0.3)
            return YouTubeStreamInfo("signed-stream", 10.0)

        async def delayed_extraction(*_args, **_kwargs):
            nonlocal extraction_started, extraction_completed
            extraction_started = True
            await asyncio.sleep(0.3)
            extraction_completed = True
            return FrameExtractionResult(frames=[], duration_seconds=10.0)

        with (
            patch(
                "gobbler_core.converters.youtube.get_video_metadata",
                return_value={
                    "title": "Video",
                    "channel": "Channel",
                    "thumbnail": None,
                    "description": None,
                },
            ),
            patch("gobbler_core.converters.youtube.ensure_ffmpeg_available"),
            patch(
                "gobbler_core.converters.youtube.resolve_youtube_stream",
                side_effect=delayed_stream_resolution,
            ),
            patch(
                "gobbler_core.converters.youtube.extract_youtube_frames",
                side_effect=delayed_extraction,
            ),
            patch("gobbler_core.converters.youtube.create_provider_from_config") as factory,
            pytest.raises(RuntimeError) as exc_info,
        ):
            await convert_youtube_to_markdown(
                "https://youtube.com/watch?v=dQw4w9WgXcQ",
                timeout=0.5,
                frame_request=YouTubeFrameRequest(exact_timestamps=(5.0,)),
                frames_only=True,
                output_path=tmp_path / "frames.md",
            )

        assert str(exc_info.value) == "YouTube conversion timed out after 0.5s"
        assert extraction_started is True
        assert extraction_completed is False
        factory.assert_not_called()

    @pytest.mark.asyncio
    async def test_convert_youtube_frames_only_requires_selector(self) -> None:
        """Frames-only mode requires a non-empty typed request."""
        with pytest.raises(ValueError, match="requires at least one frame selector"):
            await convert_youtube_to_markdown(
                "https://youtube.com/watch?v=dQw4w9WgXcQ",
                frames_only=True,
            )

    @pytest.mark.asyncio
    async def test_missing_ffmpeg_fails_before_transcript_work(self, tmp_path: Path) -> None:
        """Explicit frame work preflights FFmpeg before touching a provider."""
        provider = create_mock_provider([{"text": "Transcript", "start": 0, "duration": 3}])
        error = YouTubeFrameError("FFmpeg is required", {"error_type": "ffmpeg_missing"})

        with (
            patch("gobbler_core.converters.youtube.ensure_ffmpeg_available", side_effect=error),
            patch("gobbler_core.converters.youtube.get_video_metadata") as metadata,
            pytest.raises(YouTubeFrameError, match="FFmpeg is required"),
        ):
            await convert_youtube_to_markdown(
                "https://youtube.com/watch?v=dQw4w9WgXcQ",
                provider=provider,
                frame_request=YouTubeFrameRequest(overview_count=1),
                output_path=tmp_path / "video.md",
            )

        provider.fetch.assert_not_called()
        metadata.assert_not_called()
