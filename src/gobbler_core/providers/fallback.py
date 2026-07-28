"""Fallback wrapper for content providers.

This module provides a generic fallback mechanism that wraps any ContentProvider
and automatically falls back to an alternative provider when specified conditions
are met (e.g., errors, timeouts, rate limiting).

Example:
    def with_fallback(
        primary: ContentProvider,
        fallback: ContentProvider,
    ) -> FallbackProvider:
        return FallbackProvider(
            primary=primary,
            fallback=fallback,
            conditions=[FallbackCondition.TIMEOUT, FallbackCondition.RATE_LIMITED],
        )
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import TYPE_CHECKING, Any, Generic, Protocol, TypeAlias, TypeVar

from gobbler_core.providers.base import ContentProvider, ProviderResult
from gobbler_core.providers.document.base import DocumentProvider, DocumentResult
from gobbler_core.providers.registry import (
    ContentProviderProtocol,
    DocumentProviderProtocol,
    TranscriptionProviderProtocol,
    WebPageProviderProtocol,
)
from gobbler_core.providers.transcription.base import (
    TranscriptionProvider,
    TranscriptionResult,
)
from gobbler_core.providers.webpage.base import WebPageProvider, WebPageResult

if TYPE_CHECKING:
    from gobbler_core.config import Config

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


class _NamedProvider(Protocol):
    """Common provider behavior required by fallback orchestration."""

    @property
    def name(self) -> str:
        """Return the provider name."""


class _MetadataResult(Protocol):
    """Result carrying metadata that can record fallback details."""

    metadata: dict[str, Any]


_ProviderT = TypeVar("_ProviderT", bound=_NamedProvider)
_ResultT = TypeVar("_ResultT", bound=_MetadataResult)


class _FallbackBase(Generic[_ProviderT]):
    """Shared exception matching and metadata enrichment for typed wrappers."""

    def __init__(
        self,
        primary: _ProviderT,
        fallback: _ProviderT,
        conditions: list[str],
    ) -> None:
        """Initialize shared fallback state."""
        if not conditions or any(
            not isinstance(condition, str) or not condition.strip() for condition in conditions
        ):
            msg = "Fallback conditions must be a nonempty list of nonempty strings"
            raise TypeError(msg)
        self._primary = primary
        self._fallback = fallback
        self._conditions = tuple(conditions)

    @property
    def name(self) -> str:
        """Return a name combining the primary and fallback providers."""
        return f"{self._primary.name}+{self._fallback.name}"

    @property
    def primary(self) -> _ProviderT:
        """Return the primary provider."""
        return self._primary

    @property
    def fallback(self) -> _ProviderT:
        """Return the fallback provider."""
        return self._fallback

    @property
    def conditions(self) -> list[str]:
        """Return a copy of the configured fallback conditions."""
        return list(self._conditions)

    async def _run_with_fallback(
        self,
        operation_name: str,
        primary_call: Callable[[], Awaitable[_ResultT]],
        fallback_call: Callable[[], Awaitable[_ResultT]],
    ) -> _ResultT:
        """Run a provider operation and fall back on a matching exception."""
        primary_error: Exception
        try:
            logger.debug(
                "Attempting %s with primary provider: %s",
                operation_name,
                self._primary.name,
            )
            return await primary_call()
        except Exception as exc:
            primary_error = exc
            matching_condition = self._find_matching_condition(exc)
            if matching_condition is None:
                logger.debug(
                    "Primary provider '%s' failed with non-matching error: %s",
                    self._primary.name,
                    exc,
                )
                raise

        logger.info(
            "Falling back from '%s' to '%s' due to %s condition (error: %s)",
            self._primary.name,
            self._fallback.name,
            matching_condition,
            type(primary_error).__name__,
        )

        try:
            result = await fallback_call()
        except Exception:
            logger.exception(
                "Both providers failed. Primary '%s': %s. Fallback '%s' also failed.",
                self._primary.name,
                primary_error,
                self._fallback.name,
            )
            raise

        result.metadata["fallback_used"] = True
        result.metadata["fallback_reason"] = matching_condition
        result.metadata["primary_provider"] = self._primary.name
        result.metadata["fallback_provider"] = self._fallback.name
        return result

    def _find_matching_condition(self, exception: Exception) -> str | None:
        """Return the first configured condition matching an exception."""
        return next(
            (
                condition
                for condition in self._conditions
                if matches_condition(exception, condition)
            ),
            None,
        )


class FallbackProvider(_FallbackBase[ContentProviderProtocol], ContentProvider):
    """Fallback wrapper for the generic ``ContentProvider`` interface."""

    def supports(self, source: str) -> bool:
        """Return whether either provider supports the source."""
        return self._primary.supports(source) or self._fallback.supports(source)

    async def fetch(self, source: str, **options: Any) -> ProviderResult:
        """Fetch content, falling back on a matching primary exception."""
        return await self._run_with_fallback(
            "fetch",
            lambda: self._primary.fetch(source, **options),
            lambda: self._fallback.fetch(source, **options),
        )


class FallbackWebPageProvider(_FallbackBase[WebPageProviderProtocol], WebPageProvider):
    """Fallback wrapper for the ``WebPageProvider`` interface."""

    async def fetch(
        self,
        url: str,
        timeout: int = 30,
        **options: Any,
    ) -> WebPageResult:
        """Fetch a webpage, falling back on a matching primary exception."""
        return await self._run_with_fallback(
            "fetch",
            lambda: self._primary.fetch(url, timeout=timeout, **options),
            lambda: self._fallback.fetch(url, timeout=timeout, **options),
        )


class FallbackDocumentProvider(_FallbackBase[DocumentProviderProtocol], DocumentProvider):
    """Fallback wrapper for the ``DocumentProvider`` interface."""

    def supports_format(self, file_extension: str) -> bool:
        """Return whether either provider supports the document format."""
        return self._primary.supports_format(file_extension) or self._fallback.supports_format(
            file_extension
        )

    async def convert(
        self,
        file_path: Path,
        ocr: bool = True,
        **options: Any,
    ) -> DocumentResult:
        """Convert a document, falling back on a matching primary exception."""
        return await self._run_with_fallback(
            "convert",
            lambda: self._primary.convert(file_path, ocr=ocr, **options),
            lambda: self._fallback.convert(file_path, ocr=ocr, **options),
        )


class FallbackTranscriptionProvider(
    _FallbackBase[TranscriptionProviderProtocol],
    TranscriptionProvider,
):
    """Fallback wrapper for the ``TranscriptionProvider`` interface."""

    def supports_format(self, file_extension: str) -> bool:
        """Return whether either provider supports the audio format."""
        return self._primary.supports_format(file_extension) or self._fallback.supports_format(
            file_extension
        )

    async def transcribe(
        self,
        audio_path: Path,
        language: str = "auto",
        **options: Any,
    ) -> TranscriptionResult:
        """Transcribe audio, falling back on a matching primary exception."""
        return await self._run_with_fallback(
            "transcribe",
            lambda: self._primary.transcribe(audio_path, language=language, **options),
            lambda: self._fallback.transcribe(audio_path, language=language, **options),
        )


FallbackCapableProvider: TypeAlias = (
    ContentProviderProtocol
    | WebPageProviderProtocol
    | DocumentProviderProtocol
    | TranscriptionProviderProtocol
)


def _provider_config_kwargs(provider_config: dict[str, Any]) -> dict[str, Any]:
    """Remove fallback orchestration settings from provider constructor arguments."""
    return {key: value for key, value in provider_config.items() if key != "fallback"}


def _validate_category_provider(
    provider: object,
    category: str,
    provider_name: str,
) -> FallbackCapableProvider:
    """Validate a registry result against its category-specific interface."""
    expected_types: dict[str, type[FallbackCapableProvider]] = {
        "content": ContentProviderProtocol,
        "webpage": WebPageProviderProtocol,
        "document": DocumentProviderProtocol,
        "transcription": TranscriptionProviderProtocol,
    }
    expected_type = expected_types.get(category)
    expected_names = {
        "content": "ContentProvider",
        "webpage": "WebPageProvider",
        "document": "DocumentProvider",
        "transcription": "TranscriptionProvider",
    }
    if expected_type is None:
        msg = (
            f"Provider category '{category}' is incompatible with fallback handling; "
            "expected one of: content, webpage, document, transcription"
        )
        raise TypeError(msg)
    if not isinstance(provider, expected_type):
        msg = (
            f"Provider '{provider_name}' in category '{category}' is incompatible with "
            f"fallback handling: expected {expected_names[category]}, "
            f"got {type(provider).__name__}"
        )
        raise TypeError(msg)
    return provider


def _validate_fallback_config(
    fallback_config: object,
    category: str,
    provider_name: str,
) -> tuple[str, list[str]]:
    """Validate fallback provider and condition values from configuration."""
    if not isinstance(fallback_config, dict) or not all(
        isinstance(key, str) for key in fallback_config
    ):
        msg = (
            f"Fallback configuration for '{category}/{provider_name}' must be "
            "a string-keyed dictionary"
        )
        raise TypeError(msg)

    fallback_provider_name = fallback_config.get("provider")
    conditions_value = fallback_config.get("on")

    if not isinstance(fallback_provider_name, str) or not fallback_provider_name.strip():
        msg = (
            f"Fallback configuration for '{category}/{provider_name}' requires "
            "a nonempty string 'provider'"
        )
        raise TypeError(msg)

    if isinstance(conditions_value, str):
        conditions = [conditions_value]
    elif isinstance(conditions_value, list) and all(
        isinstance(condition, str) for condition in conditions_value
    ):
        conditions = conditions_value
    else:
        msg = (
            f"Fallback configuration for '{category}/{provider_name}' requires "
            "'on' to be a nonempty string or list of nonempty strings"
        )
        raise TypeError(msg)

    if not conditions or any(not condition.strip() for condition in conditions):
        msg = (
            f"Fallback configuration for '{category}/{provider_name}' requires "
            "'on' to be a nonempty string or list of nonempty strings"
        )
        raise TypeError(msg)
    return fallback_provider_name, conditions


def _wrap_providers(
    primary: FallbackCapableProvider,
    fallback: FallbackCapableProvider,
    conditions: list[str],
    category: str,
) -> FallbackCapableProvider:
    """Create the wrapper matching two already category-validated providers."""
    if category == "content":
        if isinstance(primary, ContentProviderProtocol) and isinstance(
            fallback, ContentProviderProtocol
        ):
            return FallbackProvider(primary, fallback, conditions)
    elif category == "webpage":
        if isinstance(primary, WebPageProviderProtocol) and isinstance(
            fallback, WebPageProviderProtocol
        ):
            return FallbackWebPageProvider(primary, fallback, conditions)
    elif category == "document":
        if isinstance(primary, DocumentProviderProtocol) and isinstance(
            fallback, DocumentProviderProtocol
        ):
            return FallbackDocumentProvider(primary, fallback, conditions)
    elif (
        category == "transcription"
        and isinstance(primary, TranscriptionProviderProtocol)
        and isinstance(fallback, TranscriptionProviderProtocol)
    ):
        return FallbackTranscriptionProvider(primary, fallback, conditions)

    msg = (
        f"Primary and fallback providers in category '{category}' expose "
        f"incompatible interfaces: {type(primary).__name__} and {type(fallback).__name__}"
    )
    raise TypeError(msg)


def create_fallback_provider(
    config: Config,
    category: str,
    provider_name: str,
) -> FallbackCapableProvider:
    """Create a category-native provider with an optional typed fallback wrapper.

    Args:
        config: Configuration object with provider settings.
        category: One of ``content``, ``webpage``, ``document``, or ``transcription``.
        provider_name: Name of the primary provider.

    Returns:
        A provider exposing the interface native to the requested category.

    Raises:
        TypeError: If configuration or registry results do not match the category.
    """
    from gobbler_core.providers.registry import ProviderRegistry

    provider_config = config.get_provider_config(category, provider_name)
    primary = _validate_category_provider(
        ProviderRegistry.create(
            category,
            provider_name,
            **_provider_config_kwargs(provider_config),
        ),
        category,
        provider_name,
    )

    fallback_config = config.get_provider_fallback(category, provider_name)
    if fallback_config is None:
        logger.debug(
            "No fallback configured for %s/%s, returning primary provider",
            category,
            provider_name,
        )
        return primary

    fallback_provider_name, fallback_conditions = _validate_fallback_config(
        fallback_config,
        category,
        provider_name,
    )
    fallback_provider_config = config.get_provider_config(category, fallback_provider_name)
    fallback = _validate_category_provider(
        ProviderRegistry.create(
            category,
            fallback_provider_name,
            **_provider_config_kwargs(fallback_provider_config),
        ),
        category,
        fallback_provider_name,
    )

    logger.info(
        "Created fallback provider: %s -> %s (on: %s)",
        provider_name,
        fallback_provider_name,
        fallback_conditions,
    )
    return _wrap_providers(primary, fallback, fallback_conditions, category)
