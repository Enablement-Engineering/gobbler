"""Unit tests for the fallback provider module."""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from gobbler_core.providers.base import ContentProvider, ProviderResult
from gobbler_core.providers.fallback import (
    FallbackCondition,
    FallbackProvider,
    create_fallback_provider,
    matches_condition,
)


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

    def supports(self, source: str) -> bool:  # noqa: ARG002
        """Return True for all sources."""
        return True

    async def fetch(self, source: str, **options: Any) -> ProviderResult:  # noqa: ARG002
        """Return configured result or raise exception."""
        self.fetch_count += 1
        if self._exception:
            raise self._exception
        return self._result


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

    def test_returns_primary_when_no_fallback_configured(self) -> None:
        """Test that primary provider is returned when no fallback is configured."""
        mock_config = MagicMock()
        mock_config.get_provider_config.return_value = {}
        mock_config.get_provider_fallback.return_value = None

        with patch("gobbler_core.providers.registry.ProviderRegistry") as mock_registry:
            mock_primary = MockProvider(name="crawl4ai")
            mock_registry.create.return_value = mock_primary

            result = create_fallback_provider(mock_config, "webpage", "crawl4ai")

            assert result is mock_primary
            mock_registry.create.assert_called_once_with("webpage", "crawl4ai")

    def test_returns_fallback_provider_when_configured(self) -> None:
        """Test that FallbackProvider is returned when fallback is configured."""
        mock_config = MagicMock()
        mock_config.get_provider_config.side_effect = lambda _cat, _name: {}
        mock_config.get_provider_fallback.return_value = {
            "provider": "httpx-simple",
            "on": ["timeout", "rate_limited"],
        }

        with patch("gobbler_core.providers.registry.ProviderRegistry") as mock_registry:
            mock_primary = MockProvider(name="crawl4ai")
            mock_fallback = MockProvider(name="httpx-simple")
            mock_registry.create.side_effect = [mock_primary, mock_fallback]

            result = create_fallback_provider(mock_config, "webpage", "crawl4ai")

            assert isinstance(result, FallbackProvider)
            assert result.primary is mock_primary
            assert result.fallback is mock_fallback
            assert result.conditions == ["timeout", "rate_limited"]

    def test_handles_single_condition_as_string(self) -> None:
        """Test that a single condition as string is converted to list."""
        mock_config = MagicMock()
        mock_config.get_provider_config.side_effect = lambda _cat, _name: {}
        mock_config.get_provider_fallback.return_value = {
            "provider": "httpx-simple",
            "on": "timeout",  # Single string, not a list
        }

        with patch("gobbler_core.providers.registry.ProviderRegistry") as mock_registry:
            mock_primary = MockProvider(name="crawl4ai")
            mock_fallback = MockProvider(name="httpx-simple")
            mock_registry.create.side_effect = [mock_primary, mock_fallback]

            result = create_fallback_provider(mock_config, "webpage", "crawl4ai")

            assert isinstance(result, FallbackProvider)
            assert result.conditions == ["timeout"]
