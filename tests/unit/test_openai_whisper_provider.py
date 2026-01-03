"""Unit tests for OpenAI Whisper transcription provider."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from gobbler_core.providers.transcription.openai_whisper import (
    MAX_FILE_SIZE_BYTES,
    OpenAIWhisperProvider,
)


class TestProviderName:
    """Test provider name property."""

    def test_name_returns_openai_whisper(self) -> None:
        """Test that provider name is 'openai-whisper'."""
        with patch.dict(os.environ, {"OPENAI_API_KEY": "sk-test-key"}):
            provider = OpenAIWhisperProvider()
            assert provider.name == "openai-whisper"


class TestSupportsFormat:
    """Test format support checking."""

    @pytest.fixture
    def provider(self) -> OpenAIWhisperProvider:
        """Create provider instance for testing."""
        with patch.dict(os.environ, {"OPENAI_API_KEY": "sk-test-key"}):
            return OpenAIWhisperProvider()

    @pytest.mark.parametrize(
        "extension",
        [".mp3", ".mp4", ".m4a", ".wav", ".webm", ".mpeg", ".mpga"],
    )
    def test_supports_valid_formats(self, provider: OpenAIWhisperProvider, extension: str) -> None:
        """Test that all supported formats return True."""
        assert provider.supports_format(extension) is True

    @pytest.mark.parametrize(
        "extension",
        [".flac", ".ogg", ".aac", ".wma", ".txt", ".pdf"],
    )
    def test_rejects_unsupported_formats(
        self, provider: OpenAIWhisperProvider, extension: str
    ) -> None:
        """Test that unsupported formats return False."""
        assert provider.supports_format(extension) is False

    def test_case_insensitive(self, provider: OpenAIWhisperProvider) -> None:
        """Test that format check is case-insensitive."""
        assert provider.supports_format(".MP3") is True
        assert provider.supports_format(".Mp4") is True
        assert provider.supports_format(".WAV") is True


class TestConstructor:
    """Test provider initialization."""

    def test_constructor_with_explicit_api_key(self) -> None:
        """Test constructor accepts explicit API key."""
        provider = OpenAIWhisperProvider(api_key="sk-explicit-key")
        assert provider._api_key == "sk-explicit-key"
        assert provider.model == "whisper-1"
        assert provider.timeout == 120.0

    def test_constructor_with_env_var(self) -> None:
        """Test constructor reads from OPENAI_API_KEY env var."""
        with patch.dict(os.environ, {"OPENAI_API_KEY": "sk-env-key"}):
            provider = OpenAIWhisperProvider()
            assert provider._api_key == "sk-env-key"

    def test_constructor_without_api_key_raises(self) -> None:
        """Test constructor raises ValueError if no API key available."""
        with patch.dict(os.environ, {}, clear=True):
            # Remove OPENAI_API_KEY if it exists
            os.environ.pop("OPENAI_API_KEY", None)
            with pytest.raises(ValueError, match="OpenAI API key not provided"):
                OpenAIWhisperProvider()

    def test_constructor_custom_params(self) -> None:
        """Test constructor accepts custom model and timeout."""
        provider = OpenAIWhisperProvider(
            api_key="sk-test",
            model="whisper-1",
            timeout=60.0,
        )
        assert provider.model == "whisper-1"
        assert provider.timeout == 60.0


class TestTranscribe:
    """Test transcription functionality."""

    @pytest.fixture
    def provider(self) -> OpenAIWhisperProvider:
        """Create provider instance for testing."""
        return OpenAIWhisperProvider(api_key="sk-test-key")

    @pytest.fixture
    def mock_audio_file(self, tmp_path: Path) -> Path:
        """Create a mock audio file for testing."""
        audio_file = tmp_path / "test.mp3"
        audio_file.write_bytes(b"fake audio data")
        return audio_file

    @pytest.fixture
    def mock_response_data(self) -> dict[str, Any]:
        """Sample OpenAI API response."""
        return {
            "text": "Hello, this is a test transcription.",
            "language": "en",
            "duration": 5.5,
            "segments": [
                {
                    "id": 0,
                    "start": 0.0,
                    "end": 2.5,
                    "text": " Hello, this is",
                    "avg_logprob": -0.25,
                },
                {
                    "id": 1,
                    "start": 2.5,
                    "end": 5.5,
                    "text": " a test transcription.",
                    "avg_logprob": -0.30,
                },
            ],
        }

    @pytest.mark.asyncio
    async def test_transcribe_success(
        self,
        provider: OpenAIWhisperProvider,
        mock_audio_file: Path,
        mock_response_data: dict[str, Any],
    ) -> None:
        """Test successful transcription with mocked API response."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = mock_response_data

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.post.return_value = mock_response
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_client_class.return_value = mock_client

            result = await provider.transcribe(mock_audio_file, language="en")

            assert result.text == "Hello, this is a test transcription."
            assert result.language == "en"
            assert result.duration == 5.5
            assert len(result.segments) == 2
            assert result.segments[0].text == "Hello, this is"
            assert result.segments[0].start == 0.0
            assert result.segments[0].end == 2.5
            assert result.metadata["model"] == "whisper-1"
            assert result.metadata["provider"] == "openai-whisper"

    @pytest.mark.asyncio
    async def test_transcribe_auto_language(
        self,
        provider: OpenAIWhisperProvider,
        mock_audio_file: Path,
        mock_response_data: dict[str, Any],
    ) -> None:
        """Test transcription with auto language detection."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = mock_response_data

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.post.return_value = mock_response
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_client_class.return_value = mock_client

            await provider.transcribe(mock_audio_file, language="auto")

            # Verify language was not included in form data
            call_kwargs = mock_client.post.call_args.kwargs
            assert "language" not in call_kwargs.get("data", {})

    @pytest.mark.asyncio
    async def test_transcribe_file_not_found(self, provider: OpenAIWhisperProvider) -> None:
        """Test transcription raises FileNotFoundError for missing file."""
        with pytest.raises(FileNotFoundError, match="Audio file not found"):
            await provider.transcribe(Path("/nonexistent/audio.mp3"))

    @pytest.mark.asyncio
    async def test_transcribe_unsupported_format(
        self, provider: OpenAIWhisperProvider, tmp_path: Path
    ) -> None:
        """Test transcription raises ValueError for unsupported format."""
        unsupported_file = tmp_path / "test.flac"
        unsupported_file.write_bytes(b"fake audio")

        with pytest.raises(ValueError, match="Unsupported format"):
            await provider.transcribe(unsupported_file)

    @pytest.mark.asyncio
    async def test_transcribe_api_error(
        self, provider: OpenAIWhisperProvider, mock_audio_file: Path
    ) -> None:
        """Test transcription raises RuntimeError on API error."""
        mock_response = MagicMock()
        mock_response.status_code = 401
        mock_response.text = "Invalid API key"

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.post.return_value = mock_response
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_client_class.return_value = mock_client

            with pytest.raises(RuntimeError, match="OpenAI API error"):
                await provider.transcribe(mock_audio_file)

    @pytest.mark.asyncio
    async def test_transcribe_timeout(
        self, provider: OpenAIWhisperProvider, mock_audio_file: Path
    ) -> None:
        """Test transcription raises RuntimeError on timeout."""
        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.post.side_effect = httpx.TimeoutException("Timeout")
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_client_class.return_value = mock_client

            with pytest.raises(RuntimeError, match="timed out"):
                await provider.transcribe(mock_audio_file)


class TestFileSizeHandling:
    """Test large file size handling."""

    @pytest.fixture
    def provider(self) -> OpenAIWhisperProvider:
        """Create provider instance for testing."""
        return OpenAIWhisperProvider(api_key="sk-test-key")

    @pytest.mark.asyncio
    async def test_large_file_triggers_extraction(
        self, provider: OpenAIWhisperProvider, tmp_path: Path
    ) -> None:
        """Test that files over 25MB trigger audio extraction."""
        # Create a file larger than the limit (26MB)
        large_file = tmp_path / "large_audio.mp4"
        # Write actual large content to exceed MAX_FILE_SIZE_BYTES (25MB)
        large_file.write_bytes(b"x" * (MAX_FILE_SIZE_BYTES + 1024))

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "text": "Test",
            "language": "en",
            "duration": 1.0,
            "segments": [],
        }

        with (
            patch.object(provider, "_extract_audio", new_callable=AsyncMock) as mock_extract,
            patch("httpx.AsyncClient") as mock_client_class,
        ):
            # Set up the mock to return a valid temp file path
            temp_audio = tmp_path / "extracted.mp3"
            temp_audio.write_bytes(b"extracted audio")
            mock_extract.return_value = temp_audio

            mock_client = AsyncMock()
            mock_client.post.return_value = mock_response
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_client_class.return_value = mock_client

            await provider.transcribe(large_file)

            # Verify _extract_audio was called
            mock_extract.assert_called_once_with(large_file)


class TestProviderRegistration:
    """Test provider registration with registry."""

    def test_provider_is_registered(self) -> None:
        """Test that OpenAIWhisperProvider is registered in the registry."""
        from gobbler_core.providers.registry import ProviderRegistry

        # The provider should be registered when the module is imported
        providers = ProviderRegistry.list_providers("transcription")
        assert "openai-whisper" in providers

    def test_can_create_from_registry(self) -> None:
        """Test that provider can be created from registry."""
        from gobbler_core.providers.registry import ProviderRegistry

        with patch.dict(os.environ, {"OPENAI_API_KEY": "sk-test-key"}):
            provider = ProviderRegistry.create("transcription", "openai-whisper")
            assert provider.name == "openai-whisper"
            assert isinstance(provider, OpenAIWhisperProvider)
