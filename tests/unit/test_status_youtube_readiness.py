"""Tests for YouTube fallback readiness in status output."""

from __future__ import annotations

from typing import Any

from gobbler_cli.commands.status import _youtube_readiness


class DummyConfig:
    """Minimal config stub for YouTube readiness tests."""

    def __init__(self, provider: str, fallback: dict[str, Any] | None) -> None:
        """Store provider and fallback values returned by status helpers."""
        self.provider = provider
        self.fallback = fallback

    def get(self, key: str, default: Any = None) -> Any:
        """Return the configured YouTube provider for status lookups."""
        if key == "providers.youtube.default":
            return self.provider
        return default

    def get_provider_fallback(
        self, category: str, provider_name: str | None = None
    ) -> dict[str, Any] | None:
        """Return the configured fallback for the YouTube provider."""
        assert category == "youtube"
        assert provider_name == self.provider
        return self.fallback


def test_youtube_readiness_reports_transcriptapi_fallback_key_present(monkeypatch) -> None:
    """Configured TranscriptAPI fallback reports ready when the key is visible."""
    monkeypatch.setenv("TRANSCRIPTAPI_KEY", "secret-key")
    config = DummyConfig(
        "youtube-transcript-api",
        {"provider": "transcriptapi", "on": ["ip_blocked", "rate_limited"]},
    )

    readiness = _youtube_readiness(config)

    assert readiness["status"] == "ready"
    assert readiness["provider"] == "youtube-transcript-api"
    assert readiness["fallback_configured"] is True
    assert readiness["fallback_provider"] == "transcriptapi"
    assert readiness["fallback_conditions"] == ["ip_blocked", "rate_limited"]
    assert readiness["transcriptapi_env_present"] is True
    assert readiness["fallback_readiness"] == "ready"
    assert "secret-key" not in str(readiness)


def test_youtube_readiness_reports_transcriptapi_fallback_key_missing(monkeypatch) -> None:
    """Configured TranscriptAPI fallback reports missing_api_key without a visible key."""
    monkeypatch.delenv("TRANSCRIPTAPI_KEY", raising=False)
    config = DummyConfig(
        "youtube-transcript-api",
        {"provider": "transcriptapi", "on": "rate_limited"},
    )

    readiness = _youtube_readiness(config)

    assert readiness["fallback_configured"] is True
    assert readiness["fallback_provider"] == "transcriptapi"
    assert readiness["fallback_conditions"] == ["rate_limited"]
    assert readiness["transcriptapi_env_present"] is False
    assert readiness["fallback_readiness"] == "missing_api_key"


def test_youtube_readiness_reports_auto_provider_implicit_fallback(monkeypatch) -> None:
    """Auto provider reports its implicit TranscriptAPI fallback readiness."""
    monkeypatch.setenv("TRANSCRIPTAPI_KEY", "secret-key")
    config = DummyConfig("auto", None)

    readiness = _youtube_readiness(config)

    assert readiness["provider"] == "auto"
    assert readiness["fallback_configured"] is True
    assert readiness["fallback_provider"] == "transcriptapi"
    assert readiness["fallback_conditions"] == ["ip_blocked", "rate_limited"]
    assert readiness["transcriptapi_env_present"] is True
    assert readiness["fallback_readiness"] == "ready"


def test_youtube_readiness_reports_default_provider_env_fallback(monkeypatch) -> None:
    """Default CLI provider reports env-enabled TranscriptAPI fallback readiness."""
    monkeypatch.setenv("TRANSCRIPTAPI_KEY", "secret-key")
    config = DummyConfig("youtube-transcript-api", None)

    readiness = _youtube_readiness(config)

    assert readiness["provider"] == "youtube-transcript-api"
    assert readiness["fallback_configured"] is True
    assert readiness["fallback_provider"] == "transcriptapi"
    assert readiness["fallback_conditions"] == ["ip_blocked", "rate_limited"]
    assert readiness["transcriptapi_env_present"] is True
    assert readiness["fallback_readiness"] == "ready"


def test_youtube_readiness_does_not_report_primary_transcriptapi_as_fallback(monkeypatch) -> None:
    """TranscriptAPI primary provider does not masquerade as a fallback provider."""
    monkeypatch.setenv("TRANSCRIPTAPI_KEY", "secret-key")
    config = DummyConfig("transcriptapi", None)

    readiness = _youtube_readiness(config)

    assert readiness["provider"] == "transcriptapi"
    assert readiness["fallback_configured"] is False
    assert readiness["fallback_provider"] is None
    assert readiness["transcriptapi_env_present"] is True
    assert readiness["fallback_readiness"] == "not_configured"


def test_youtube_readiness_reports_unconfigured_fallback(monkeypatch) -> None:
    """Unconfigured fallback reports not_configured while keeping YouTube ready."""
    monkeypatch.delenv("TRANSCRIPTAPI_KEY", raising=False)
    config = DummyConfig("youtube-transcript-api", None)

    readiness = _youtube_readiness(config)

    assert readiness["status"] == "ready"
    assert readiness["fallback_configured"] is False
    assert readiness["fallback_provider"] is None
    assert readiness["fallback_conditions"] == []
    assert readiness["transcriptapi_env_present"] is False
    assert readiness["fallback_readiness"] == "not_configured"
