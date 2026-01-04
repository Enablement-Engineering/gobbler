"""Fallback wrapper for content providers.

This module provides a generic fallback mechanism that wraps any ContentProvider
and automatically falls back to an alternative provider when specified conditions
are met (e.g., errors, timeouts, rate limiting).

Example:
    from gobbler_core.providers.fallback import FallbackProvider, FallbackCondition
    from gobbler_core.providers import ProviderRegistry

    primary = ProviderRegistry.create("webpage", "crawl4ai")
    fallback = ProviderRegistry.create("webpage", "httpx-simple")

    provider = FallbackProvider(
        primary=primary,
        fallback=fallback,
        conditions=[FallbackCondition.TIMEOUT, FallbackCondition.RATE_LIMITED],
    )

    result = await provider.fetch("https://example.com")
"""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING, Any

from gobbler_core.providers.base import ContentProvider, ProviderResult

if TYPE_CHECKING:
    from gobbler_mcp.config import Config

logger = logging.getLogger(__name__)


class FallbackCondition:
    """Standard conditions that trigger provider fallback.

    These conditions are matched against exceptions raised by the primary
    provider to determine whether to attempt the fallback provider.

    Attributes:
        ERROR: Any exception triggers fallback
        TIMEOUT: Request timeout errors
        RATE_LIMITED: HTTP 429 or rate limit errors
        IP_BLOCKED: IP blocking or ban detected
        UNAVAILABLE: Service unreachable or connection errors
    """

    ERROR = "error"
    TIMEOUT = "timeout"
    RATE_LIMITED = "rate_limited"
    IP_BLOCKED = "ip_blocked"
    UNAVAILABLE = "unavailable"

    @classmethod
    def all_conditions(cls) -> list[str]:
        """Return all valid fallback conditions.

        Returns:
            List of all condition string values.
        """
        return [
            cls.ERROR,
            cls.TIMEOUT,
            cls.RATE_LIMITED,
            cls.IP_BLOCKED,
            cls.UNAVAILABLE,
        ]


def _matches_timeout(exception: Exception) -> bool:
    """Check if exception indicates a timeout error."""
    if isinstance(exception, (TimeoutError, asyncio.TimeoutError)):
        return True
    exception_msg = str(exception).lower()
    if "timeout" in exception_msg:
        return True
    # Check for httpx.TimeoutException and similar
    return "timeout" in type(exception).__name__.lower()


def _matches_rate_limited(exception_msg: str) -> bool:
    """Check if exception message indicates rate limiting."""
    if "429" in exception_msg:
        return True
    if "rate limit" in exception_msg or "ratelimit" in exception_msg:
        return True
    return "too many requests" in exception_msg


def _matches_ip_blocked(exception_msg: str) -> bool:
    """Check if exception message indicates IP blocking."""
    blocked_indicators = [
        "blocked",
        "ipblocked",
        "ip_blocked",
        "banned",
        "forbidden",
        "access denied",
        "captcha",
    ]
    return any(indicator in exception_msg for indicator in blocked_indicators)


def _matches_unavailable(exception: Exception, exception_msg: str) -> bool:
    """Check if exception indicates service unavailability."""
    if isinstance(exception, (ConnectionError, OSError)):
        return True
    unavailable_indicators = [
        "unavailable",
        "unreachable",
        "connection refused",
        "connection error",
        "network error",
        "service unavailable",
        "503",
        "502",
        "504",
    ]
    return any(indicator in exception_msg for indicator in unavailable_indicators)


def matches_condition(exception: Exception, condition: str) -> bool:
    """Check if an exception matches a fallback condition.

    Args:
        exception: The exception raised by the primary provider.
        condition: The fallback condition to check against.

    Returns:
        True if the exception matches the condition.

    Example:
        >>> matches_condition(TimeoutError(), FallbackCondition.TIMEOUT)
        True
        >>> matches_condition(ValueError("rate limit exceeded"), FallbackCondition.RATE_LIMITED)
        True
    """
    if condition == FallbackCondition.ERROR:
        return True

    exception_msg = str(exception).lower()

    if condition == FallbackCondition.TIMEOUT:
        return _matches_timeout(exception)

    if condition == FallbackCondition.RATE_LIMITED:
        return _matches_rate_limited(exception_msg)

    if condition == FallbackCondition.IP_BLOCKED:
        return _matches_ip_blocked(exception_msg)

    if condition == FallbackCondition.UNAVAILABLE:
        return _matches_unavailable(exception, exception_msg)

    # Unknown condition, no match
    logger.warning("Unknown fallback condition: %s", condition)
    return False


class FallbackProvider(ContentProvider):
    """A provider wrapper that falls back to an alternative on specific conditions.

    This class wraps a primary ContentProvider and attempts to use a fallback
    provider when the primary fails with errors matching the specified conditions.

    Attributes:
        primary: The primary content provider to try first.
        fallback: The fallback content provider to use on failure.
        conditions: List of FallbackCondition values that trigger fallback.

    Example:
        provider = FallbackProvider(
            primary=Crawl4AIProvider(),
            fallback=SimpleHTTPProvider(),
            conditions=["timeout", "rate_limited"],
        )
        result = await provider.fetch("https://example.com")
    """

    def __init__(
        self,
        primary: ContentProvider,
        fallback: ContentProvider,
        conditions: list[str],
    ) -> None:
        """Initialize the fallback provider wrapper.

        Args:
            primary: The primary content provider to try first.
            fallback: The fallback content provider to use on failure.
            conditions: List of FallbackCondition values (e.g., ["timeout", "error"])
                that trigger fallback to the alternative provider.
        """
        self._primary = primary
        self._fallback = fallback
        self._conditions = conditions

    @property
    def name(self) -> str:
        """Return combined provider name.

        Returns:
            A name combining primary and fallback provider names.
        """
        return f"{self._primary.name}+{self._fallback.name}"

    @property
    def primary(self) -> ContentProvider:
        """Return the primary provider."""
        return self._primary

    @property
    def fallback(self) -> ContentProvider:
        """Return the fallback provider."""
        return self._fallback

    @property
    def conditions(self) -> list[str]:
        """Return the fallback conditions."""
        return self._conditions.copy()

    def supports(self, source: str) -> bool:
        """Check if either provider supports the source.

        Args:
            source: URL, file path, or identifier to check.

        Returns:
            True if either primary or fallback provider supports the source.
        """
        return self._primary.supports(source) or self._fallback.supports(source)

    async def fetch(self, source: str, **options: Any) -> ProviderResult:
        """Fetch content, falling back on matching error conditions.

        Tries the primary provider first. If it raises an exception that
        matches any of the configured fallback conditions, tries the
        fallback provider.

        Args:
            source: URL, file path, or identifier to fetch content from.
            **options: Provider-specific options passed to both providers.

        Returns:
            ProviderResult from whichever provider succeeds.

        Note:
            If the primary provider returns a ProviderResult with success=False,
            it is returned directly without attempting fallback. Fallback is
            only triggered by exceptions.
        """
        primary_error: Exception | None = None
        matching_condition: str | None = None

        try:
            logger.debug("Attempting fetch with primary provider: %s", self._primary.name)
            return await self._primary.fetch(source, **options)

        except Exception as exc:
            primary_error = exc
            matching_condition = self._find_matching_condition(exc)

            if matching_condition is None:
                # No condition matched, re-raise the original exception
                logger.debug(
                    "Primary provider '%s' failed with non-matching error: %s",
                    self._primary.name,
                    exc,
                )
                raise

        # Condition matched, try fallback
        logger.info(
            "Falling back from '%s' to '%s' due to %s condition (error: %s)",
            self._primary.name,
            self._fallback.name,
            matching_condition,
            type(primary_error).__name__,
        )

        try:
            result = await self._fallback.fetch(source, **options)
        except Exception:
            # Both providers failed
            logger.exception(
                "Both providers failed. Primary '%s': %s. Fallback '%s' also failed.",
                self._primary.name,
                primary_error,
                self._fallback.name,
            )
            # Re-raise the fallback error as it's the most recent
            raise

        # Add metadata about the fallback
        result.metadata["fallback_used"] = True
        result.metadata["fallback_reason"] = matching_condition
        result.metadata["primary_provider"] = self._primary.name
        result.metadata["fallback_provider"] = self._fallback.name

        return result

    def _find_matching_condition(self, exception: Exception) -> str | None:
        """Find the first matching fallback condition for an exception.

        Args:
            exception: The exception to check.

        Returns:
            The matching condition string, or None if no condition matches.
        """
        for condition in self._conditions:
            if matches_condition(exception, condition):
                return condition
        return None


def create_fallback_provider(
    config: Config,
    category: str,
    provider_name: str,
) -> ContentProvider:
    """Create a provider with fallback if configured.

    This factory function creates a provider instance and wraps it in a
    FallbackProvider if fallback configuration exists for the provider.

    Args:
        config: Configuration object with provider settings.
        category: Provider category (e.g., "transcription", "document", "webpage").
        provider_name: Name of the primary provider.

    Returns:
        Either the primary provider directly, or a FallbackProvider wrapping
        the primary with a configured fallback.

    Example:
        config = get_config()
        provider = create_fallback_provider(config, "webpage", "crawl4ai")

    Configuration format:
        providers:
          webpage:
            crawl4ai:
              timeout: 30
              fallback:
                provider: httpx-simple
                on: [timeout, rate_limited]
    """
    from gobbler_core.providers.registry import ProviderRegistry  # noqa: PLC0415

    # Get provider configuration and create primary provider
    provider_config = config.get_provider_config(category, provider_name)
    primary = ProviderRegistry.create(category, provider_name, **provider_config)

    # Check for fallback configuration
    fallback_config = config.get_provider_fallback(category, provider_name)

    if fallback_config is None:
        logger.debug(
            "No fallback configured for %s/%s, returning primary provider",
            category,
            provider_name,
        )
        return primary

    # Create fallback provider
    fallback_provider_name = fallback_config["provider"]
    fallback_conditions = fallback_config["on"]

    # Ensure conditions is a list
    if isinstance(fallback_conditions, str):
        fallback_conditions = [fallback_conditions]

    # Get fallback provider config and create it
    fallback_provider_config = config.get_provider_config(category, fallback_provider_name)
    fallback = ProviderRegistry.create(category, fallback_provider_name, **fallback_provider_config)

    logger.info(
        "Created fallback provider: %s -> %s (on: %s)",
        provider_name,
        fallback_provider_name,
        fallback_conditions,
    )

    return FallbackProvider(
        primary=primary,
        fallback=fallback,
        conditions=fallback_conditions,
    )
