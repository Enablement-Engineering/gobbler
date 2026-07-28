"""Unit tests for the fallback provider module."""

from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from gobbler_core.providers.base import ContentProvider, ProviderResult
from gobbler_core.providers.document.base import DocumentProvider, DocumentResult
from gobbler_core.providers.fallback import (
    FallbackCondition,
    FallbackDocumentProvider,
    FallbackProvider,
    FallbackTranscriptionProvider,
    FallbackWebPageProvider,
    create_fallback_provider,
    matches_condition,
)
from gobbler_core.providers.transcription.base import (
    TranscriptionProvider,
    TranscriptionResult,
)
from gobbler_core.providers.webpage.base import WebPageProvider, WebPageResult


class MockProvider(ContentProvider):
    """Mock provider for testing."""

    def __init__(
        self,
        name: str = "mock",
        result: ProviderResult | None = None,
        exception: Exception | None = None,
    ) -> None:
        """Initialize mock provider."""
        self._name = name
        self._result = result or ProviderResult(
            success=True,
            content="mock content",
            metadata={"provider": name},
        )
        self._exception = exception
        self.fetch_count = 0

    @property
    def name(self) -> str:
        """Return provider name."""
        return self._name

    def supports(self, source: str) -> bool:
        """Return True for all sources."""
        return True

    async def fetch(self, source: str, **options: Any) -> ProviderResult:
        """Return configured result or raise exception."""
        self.fetch_count += 1
        if self._exception:
            raise self._exception
        return self._result


class MockWebPageProvider(WebPageProvider):
    """Mock webpage provider for typed fallback tests."""

    def __init__(self, name: str, exception: Exception | None = None) -> None:
        """Initialize the mock."""
        self._name = name
        self._exception = exception
        self.fetch_count = 0

    @property
    def name(self) -> str:
        """Return provider name."""
        return self._name

    async def fetch(
        self,
        url: str,
        timeout: int = 30,
        **options: Any,
    ) -> WebPageResult:
        """Return a webpage result or raise the configured exception."""
        self.fetch_count += 1
        if self._exception is not None:
            raise self._exception
        return WebPageResult(
            markdown=f"# {self.name}",
            title=self.name,
            url=url,
            metadata={"timeout": timeout, **options},
        )


class MockDocumentProvider(DocumentProvider):
    """Mock document provider for typed fallback tests."""

    def __init__(self, name: str, exception: Exception | None = None) -> None:
        """Initialize the mock."""
        self._name = name
        self._exception = exception
        self.convert_count = 0

    @property
    def name(self) -> str:
        """Return provider name."""
        return self._name

    def supports_format(self, file_extension: str) -> bool:
        """Support PDF files."""
        return file_extension == ".pdf"

    async def convert(
        self,
        file_path: Path,
        ocr: bool = True,
        **options: Any,
    ) -> DocumentResult:
        """Return a document result or raise the configured exception."""
        self.convert_count += 1
        if self._exception is not None:
            raise self._exception
        return DocumentResult(
            markdown=f"# {self.name}",
            pages=1,
            metadata={"path": str(file_path), "ocr": ocr, **options},
        )


class MockTranscriptionProvider(TranscriptionProvider):
    """Mock transcription provider for typed fallback tests."""

    def __init__(self, name: str, exception: Exception | None = None) -> None:
        """Initialize the mock."""
        self._name = name
        self._exception = exception
        self.transcribe_count = 0

    @property
    def name(self) -> str:
        """Return provider name."""
        return self._name

    def supports_format(self, file_extension: str) -> bool:
        """Support MP3 files."""
        return file_extension == ".mp3"

    async def transcribe(
        self,
        audio_path: Path,
        language: str = "auto",
        **options: Any,
    ) -> TranscriptionResult:
        """Return a transcription result or raise the configured exception."""
        self.transcribe_count += 1
        if self._exception is not None:
            raise self._exception
        return TranscriptionResult(
            text=self.name,
            segments=[],
            language=language,
            duration=1.0,
            metadata={"path": str(audio_path), **options},
        )


class TestFallbackCondition:
    """Tests for FallbackCondition class."""

    def test_all_conditions_returns_all_values(self) -> None:
        """Test that all_conditions returns all condition values."""
        conditions = FallbackCondition.all_conditions()
        assert FallbackCondition.ERROR in conditions
        assert FallbackCondition.TIMEOUT in conditions
        assert FallbackCondition.RATE_LIMITED in conditions
        assert FallbackCondition.IP_BLOCKED in conditions
        assert FallbackCondition.UNAVAILABLE in conditions
        assert len(conditions) == 5


class TestMatchesCondition:
    """Tests for matches_condition function."""

    def test_error_matches_any_exception(self) -> None:
        """Test that ERROR condition matches any exception."""
        assert matches_condition(ValueError("test"), FallbackCondition.ERROR)
        assert matches_condition(TimeoutError(), FallbackCondition.ERROR)
        assert matches_condition(RuntimeError("something"), FallbackCondition.ERROR)

    def test_timeout_matches_timeout_error(self) -> None:
        """Test that TIMEOUT condition matches TimeoutError."""
        assert matches_condition(TimeoutError(), FallbackCondition.TIMEOUT)

    def test_timeout_matches_asyncio_timeout_error(self) -> None:
        """Test that TIMEOUT condition matches asyncio.TimeoutError."""
        assert matches_condition(TimeoutError(), FallbackCondition.TIMEOUT)

    def test_timeout_matches_message_with_timeout(self) -> None:
        """Test that TIMEOUT condition matches exceptions with 'timeout' in message."""
        assert matches_condition(RuntimeError("Request timeout"), FallbackCondition.TIMEOUT)
        assert matches_condition(
            RuntimeError("Connection timeout occurred"), FallbackCondition.TIMEOUT
        )

    def test_timeout_does_not_match_unrelated_error(self) -> None:
        """Test that TIMEOUT condition does not match unrelated errors."""
        assert not matches_condition(ValueError("invalid value"), FallbackCondition.TIMEOUT)

    def test_rate_limited_matches_429(self) -> None:
        """Test that RATE_LIMITED condition matches 429 status."""
        assert matches_condition(
            RuntimeError("HTTP 429 Too Many Requests"), FallbackCondition.RATE_LIMITED
        )

    def test_rate_limited_matches_rate_limit_message(self) -> None:
        """Test that RATE_LIMITED condition matches rate limit messages."""
        assert matches_condition(
            RuntimeError("rate limit exceeded"), FallbackCondition.RATE_LIMITED
        )
        assert matches_condition(RuntimeError("ratelimit hit"), FallbackCondition.RATE_LIMITED)
        assert matches_condition(RuntimeError("too many requests"), FallbackCondition.RATE_LIMITED)

    def test_rate_limited_does_not_match_unrelated_error(self) -> None:
        """Test that RATE_LIMITED condition does not match unrelated errors."""
        assert not matches_condition(ValueError("invalid value"), FallbackCondition.RATE_LIMITED)

    def test_ip_blocked_matches_blocked_messages(self) -> None:
        """Test that IP_BLOCKED condition matches blocking messages."""
        assert matches_condition(RuntimeError("IP blocked"), FallbackCondition.IP_BLOCKED)
        assert matches_condition(RuntimeError("IpBlocked by server"), FallbackCondition.IP_BLOCKED)
        assert matches_condition(RuntimeError("User banned"), FallbackCondition.IP_BLOCKED)
        assert matches_condition(RuntimeError("Access denied"), FallbackCondition.IP_BLOCKED)
        assert matches_condition(RuntimeError("Captcha required"), FallbackCondition.IP_BLOCKED)
        assert matches_condition(RuntimeError("403 Forbidden"), FallbackCondition.IP_BLOCKED)

    def test_ip_blocked_does_not_match_unrelated_error(self) -> None:
        """Test that IP_BLOCKED condition does not match unrelated errors."""
        assert not matches_condition(ValueError("invalid value"), FallbackCondition.IP_BLOCKED)

    def test_unavailable_matches_connection_error(self) -> None:
        """Test that UNAVAILABLE condition matches ConnectionError."""
        assert matches_condition(
            ConnectionError("Connection refused"), FallbackCondition.UNAVAILABLE
        )

    def test_unavailable_matches_oserror(self) -> None:
        """Test that UNAVAILABLE condition matches OSError."""
        assert matches_condition(OSError("Network unreachable"), FallbackCondition.UNAVAILABLE)

    def test_unavailable_matches_unavailable_messages(self) -> None:
        """Test that UNAVAILABLE condition matches unavailability messages."""
        assert matches_condition(RuntimeError("Service unavailable"), FallbackCondition.UNAVAILABLE)
        assert matches_condition(RuntimeError("Host unreachable"), FallbackCondition.UNAVAILABLE)
        assert matches_condition(RuntimeError("HTTP 503"), FallbackCondition.UNAVAILABLE)
        assert matches_condition(
            RuntimeError("HTTP 502 Bad Gateway"), FallbackCondition.UNAVAILABLE
        )
        assert matches_condition(
            RuntimeError("HTTP 504 Gateway Timeout"), FallbackCondition.UNAVAILABLE
        )

    def test_unavailable_does_not_match_unrelated_error(self) -> None:
        """Test that UNAVAILABLE condition does not match unrelated errors."""
        assert not matches_condition(ValueError("invalid value"), FallbackCondition.UNAVAILABLE)

    def test_unknown_condition_returns_false(self) -> None:
        """Test that unknown condition returns False."""
        assert not matches_condition(ValueError("test"), "unknown_condition")


class TestFallbackProvider:
    """Tests for FallbackProvider class."""

    def test_name_combines_provider_names(self) -> None:
        """Test that name combines primary and fallback provider names."""
        primary = MockProvider(name="primary")
        fallback = MockProvider(name="fallback")
        provider = FallbackProvider(primary, fallback, [FallbackCondition.ERROR])

        assert provider.name == "primary+fallback"

    def test_supports_returns_true_if_either_supports(self) -> None:
        """Test that supports returns True if either provider supports the source."""
        primary = MockProvider(name="primary")
        fallback = MockProvider(name="fallback")
        provider = FallbackProvider(primary, fallback, [FallbackCondition.ERROR])

        assert provider.supports("https://example.com")

    def test_properties_return_correct_values(self) -> None:
        """Test that properties return the correct values."""
        primary = MockProvider(name="primary")
        fallback = MockProvider(name="fallback")
        conditions = [FallbackCondition.TIMEOUT, FallbackCondition.ERROR]
        provider = FallbackProvider(primary, fallback, conditions)

        assert provider.primary is primary
        assert provider.fallback is fallback
        assert provider.conditions == conditions

    def test_conditions_returns_copy(self) -> None:
        """Test that conditions returns a copy to prevent mutation."""
        primary = MockProvider(name="primary")
        fallback = MockProvider(name="fallback")
        conditions = [FallbackCondition.TIMEOUT]
        provider = FallbackProvider(primary, fallback, conditions)

        returned_conditions = provider.conditions
        returned_conditions.append(FallbackCondition.ERROR)

        assert provider.conditions == [FallbackCondition.TIMEOUT]

    @pytest.mark.asyncio
    async def test_fetch_uses_primary_on_success(self) -> None:
        """Test that fetch uses primary provider when it succeeds."""
        primary_result = ProviderResult(success=True, content="primary", metadata={})
        primary = MockProvider(name="primary", result=primary_result)
        fallback = MockProvider(name="fallback")
        provider = FallbackProvider(primary, fallback, [FallbackCondition.ERROR])

        result = await provider.fetch("https://example.com")

        assert result.content == "primary"
        assert primary.fetch_count == 1
        assert fallback.fetch_count == 0

    @pytest.mark.asyncio
    async def test_fetch_falls_back_on_matching_condition(self) -> None:
        """Test that fetch falls back when primary fails with matching condition."""
        primary = MockProvider(name="primary", exception=TimeoutError("timed out"))
        fallback_result = ProviderResult(success=True, content="fallback", metadata={})
        fallback = MockProvider(name="fallback", result=fallback_result)
        provider = FallbackProvider(primary, fallback, [FallbackCondition.TIMEOUT])

        result = await provider.fetch("https://example.com")

        assert result.content == "fallback"
        assert result.metadata["fallback_used"] is True
        assert result.metadata["fallback_reason"] == FallbackCondition.TIMEOUT
        assert result.metadata["primary_provider"] == "primary"
        assert result.metadata["fallback_provider"] == "fallback"
        assert primary.fetch_count == 1
        assert fallback.fetch_count == 1

    @pytest.mark.asyncio
    async def test_fetch_raises_on_non_matching_condition(self) -> None:
        """Test that fetch re-raises when primary fails with non-matching condition."""
        primary = MockProvider(name="primary", exception=ValueError("invalid"))
        fallback = MockProvider(name="fallback")
        provider = FallbackProvider(primary, fallback, [FallbackCondition.TIMEOUT])

        with pytest.raises(ValueError, match="invalid"):
            await provider.fetch("https://example.com")

        assert primary.fetch_count == 1
        assert fallback.fetch_count == 0

    @pytest.mark.asyncio
    async def test_fetch_raises_fallback_error_when_both_fail(self) -> None:
        """Test that fetch raises fallback error when both providers fail."""
        primary = MockProvider(name="primary", exception=TimeoutError("primary timeout"))
        fallback = MockProvider(name="fallback", exception=RuntimeError("fallback error"))
        provider = FallbackProvider(primary, fallback, [FallbackCondition.ERROR])

        with pytest.raises(RuntimeError, match="fallback error"):
            await provider.fetch("https://example.com")

        assert primary.fetch_count == 1
        assert fallback.fetch_count == 1

    @pytest.mark.asyncio
    async def test_fetch_passes_options_to_both_providers(self) -> None:
        """Test that fetch passes options to both providers."""
        primary = MockProvider(name="primary", exception=TimeoutError())
        fallback = MockProvider(name="fallback")
        provider = FallbackProvider(primary, fallback, [FallbackCondition.TIMEOUT])

        # The options will be passed through, but our mock doesn't use them
        await provider.fetch("https://example.com", timeout=60, format="json")

        assert primary.fetch_count == 1
        assert fallback.fetch_count == 1


class TestCreateFallbackProvider:
    """Tests for create_fallback_provider factory function."""

    def test_rejects_incompatible_primary_registry_result(self) -> None:
        """Test that registry results must match the requested category."""
        mock_config = MagicMock()
        mock_config.get_provider_config.return_value = {}

        with patch("gobbler_core.providers.registry.ProviderRegistry") as mock_registry:
            mock_registry.create.return_value = object()

            with pytest.raises(
                TypeError,
                match=(
                    "Provider 'crawl4ai' in category 'webpage' is incompatible with "
                    "fallback handling: expected WebPageProvider, got object"
                ),
            ):
                create_fallback_provider(mock_config, "webpage", "crawl4ai")

        mock_config.get_provider_fallback.assert_not_called()

    def test_returns_primary_when_no_fallback_configured(self) -> None:
        """Test that primary provider is returned when no fallback is configured."""
        mock_config = MagicMock()
        mock_config.get_provider_config.return_value = {}
        mock_config.get_provider_fallback.return_value = None

        with patch("gobbler_core.providers.registry.ProviderRegistry") as mock_registry:
            mock_primary = MockWebPageProvider(name="crawl4ai")
            mock_registry.create.return_value = mock_primary

            result = create_fallback_provider(mock_config, "webpage", "crawl4ai")

            assert result is mock_primary
            mock_registry.create.assert_called_once_with("webpage", "crawl4ai")

    def test_webpage_category_wins_for_provider_with_overlapping_interfaces(self) -> None:
        """Test wrapper dispatch follows category rather than runtime match ordering."""
        mock_config = MagicMock()
        mock_config.get_provider_config.side_effect = lambda _cat, _name: {}
        mock_config.get_provider_fallback.return_value = {
            "provider": "backup",
            "on": ["error"],
        }

        with patch("gobbler_core.providers.registry.ProviderRegistry") as mock_registry:
            mock_registry.create.side_effect = [
                MockProvider(name="primary"),
                MockProvider(name="backup"),
            ]

            result = create_fallback_provider(mock_config, "webpage", "primary")

        assert isinstance(result, FallbackWebPageProvider)

    @pytest.mark.asyncio
    async def test_preserves_webpage_fetch_fallback_behavior(self) -> None:
        """Test the documented webpage factory path delegates ``fetch`` correctly."""
        mock_config = MagicMock()
        mock_config.get_provider_config.side_effect = lambda _cat, _name: {}
        mock_config.get_provider_fallback.return_value = {
            "provider": "httpx-simple",
            "on": ["timeout", "rate_limited"],
        }

        with patch("gobbler_core.providers.registry.ProviderRegistry") as mock_registry:
            mock_primary = MockWebPageProvider(
                name="crawl4ai",
                exception=TimeoutError("timed out"),
            )
            mock_fallback = MockWebPageProvider(name="httpx-simple")
            mock_registry.create.side_effect = [mock_primary, mock_fallback]

            result = create_fallback_provider(mock_config, "webpage", "crawl4ai")

            assert isinstance(result, FallbackWebPageProvider)
            assert result.primary is mock_primary
            assert result.fallback is mock_fallback
            assert result.conditions == ["timeout", "rate_limited"]
            webpage_result = await result.fetch(
                "https://example.com",
                timeout=17,
                include_images=True,
            )

        assert webpage_result.title == "httpx-simple"
        assert webpage_result.metadata["timeout"] == 17
        assert webpage_result.metadata["include_images"] is True
        assert webpage_result.metadata["fallback_used"] is True
        assert webpage_result.metadata["fallback_reason"] == "timeout"

    def test_rejects_incompatible_fallback_registry_result(self) -> None:
        """Test that mixed category interfaces are rejected before wrapping."""
        mock_config = MagicMock()
        mock_config.get_provider_config.side_effect = lambda _cat, _name: {}
        mock_config.get_provider_fallback.return_value = {
            "provider": "whisper",
            "on": ["error"],
        }

        with patch("gobbler_core.providers.registry.ProviderRegistry") as mock_registry:
            mock_registry.create.side_effect = [
                MockDocumentProvider(name="docling"),
                MockTranscriptionProvider(name="whisper"),
            ]

            with pytest.raises(
                TypeError,
                match=(
                    "Provider 'whisper' in category 'document' is incompatible with "
                    "fallback handling: expected DocumentProvider, "
                    "got MockTranscriptionProvider"
                ),
            ):
                create_fallback_provider(mock_config, "document", "docling")

    @pytest.mark.asyncio
    async def test_document_wrapper_delegates_convert_and_enriches_metadata(self) -> None:
        """Test document fallback uses ``convert`` and preserves its arguments."""
        mock_config = MagicMock()
        mock_config.get_provider_config.side_effect = lambda _cat, _name: {}
        mock_config.get_provider_fallback.return_value = {
            "provider": "backup-docling",
            "on": "timeout",
        }

        with patch("gobbler_core.providers.registry.ProviderRegistry") as mock_registry:
            mock_primary = MockDocumentProvider(
                name="docling",
                exception=TimeoutError("timed out"),
            )
            mock_fallback = MockDocumentProvider(name="backup-docling")
            mock_registry.create.side_effect = [mock_primary, mock_fallback]

            provider = create_fallback_provider(mock_config, "document", "docling")
            assert isinstance(provider, FallbackDocumentProvider)
            result = await provider.convert(Path("report.pdf"), ocr=False, tables=True)

        assert result.metadata["ocr"] is False
        assert result.metadata["tables"] is True
        assert result.metadata["fallback_provider"] == "backup-docling"

    @pytest.mark.asyncio
    async def test_transcription_wrapper_delegates_transcribe(self) -> None:
        """Test transcription fallback uses ``transcribe``."""
        mock_config = MagicMock()
        mock_config.get_provider_config.side_effect = lambda _cat, _name: {}
        mock_config.get_provider_fallback.return_value = {
            "provider": "backup-whisper",
            "on": ["error"],
        }

        with patch("gobbler_core.providers.registry.ProviderRegistry") as mock_registry:
            mock_registry.create.side_effect = [
                MockTranscriptionProvider("whisper", RuntimeError("failed")),
                MockTranscriptionProvider("backup-whisper"),
            ]
            provider = create_fallback_provider(
                mock_config,
                "transcription",
                "whisper",
            )
            assert isinstance(provider, FallbackTranscriptionProvider)
            result = await provider.transcribe(Path("audio.mp3"), language="en")

        assert result.text == "backup-whisper"
        assert result.language == "en"
        assert result.metadata["fallback_used"] is True

    @pytest.mark.parametrize(
        ("fallback_config", "message"),
        [
            (42, "must be a string-keyed dictionary"),
            ({"provider": "", "on": ["error"]}, "nonempty string 'provider'"),
            ({"provider": "backup", "on": 42}, "'on' to be a nonempty string"),
            ({"provider": "backup", "on": [""]}, "'on' to be a nonempty string"),
        ],
    )
    def test_rejects_invalid_fallback_config_before_creating_wrapper(
        self,
        fallback_config: object,
        message: str,
    ) -> None:
        """Test malformed fallback settings never reach a wrapper."""
        mock_config = MagicMock()
        mock_config.get_provider_config.return_value = {}
        mock_config.get_provider_fallback.return_value = fallback_config

        with patch("gobbler_core.providers.registry.ProviderRegistry") as mock_registry:
            mock_registry.create.return_value = MockWebPageProvider("crawl4ai")

            with pytest.raises(TypeError, match=message):
                create_fallback_provider(mock_config, "webpage", "crawl4ai")

        mock_registry.create.assert_called_once()
