"""YouTube transcript providers with proxy and fallback support.

This module provides multiple backends for fetching YouTube transcripts:
- YouTubeTranscriptAPIProvider: Free, uses youtube-transcript-api (may get IP blocked)
- TranscriptAPIProvider: Paid API via TranscriptAPI.com (reliable, no IP blocks)
- AutoFallbackProvider: Tries free first, falls back to paid if blocked

Proxy support:
- Webshare rotating proxies (WEBSHARE_USER, WEBSHARE_PASS)
- Generic HTTP/SOCKS proxy (YOUTUBE_PROXY)

Environment variables:
- WEBSHARE_USER: Webshare proxy username
- WEBSHARE_PASS: Webshare proxy password
- YOUTUBE_PROXY: Generic proxy URL (http://user:pass@host:port)
- TRANSCRIPTAPI_KEY: API key for YoutubeToTranscript.com

Note: This module uses its own TranscriptProvider base class for backwards
compatibility. The existing providers don't implement ContentProvider from
base.py since they have a different interface (sync vs async, different params).
"""

import logging
import os
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any

import httpx
from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api.proxies import GenericProxyConfig, WebshareProxyConfig

logger = logging.getLogger(__name__)


@dataclass
class TranscriptSegment:
    """A single segment of a transcript."""

    text: str
    start: float
    duration: float


@dataclass
class TranscriptResult:
    """Result from a transcript provider."""

    segments: list[TranscriptSegment]
    language: str
    metadata: dict[str, Any]


class TranscriptProvider(ABC):
    """Base class for transcript providers."""

    @abstractmethod
    def fetch(
        self,
        video_id: str,
        language: str = "auto",
    ) -> TranscriptResult:
        """Fetch transcript from provider.

        Args:
            video_id: YouTube video ID (11 characters)
            language: Language code or 'auto' for auto-detection

        Returns:
            TranscriptResult with segments, detected language, and metadata
        """


class YouTubeTranscriptAPIProvider(TranscriptProvider):
    """Provider using youtube-transcript-api (free, may get IP blocked)."""

    def __init__(self, proxy_config=None):
        """Initialize provider.

        Args:
            proxy_config: Optional WebshareProxyConfig or GenericProxyConfig
        """
        self.proxy_config = proxy_config

    def fetch(
        self,
        video_id: str,
        language: str = "auto",
    ) -> TranscriptResult:
        """Fetch transcript using youtube-transcript-api."""
        if self.proxy_config:
            api = YouTubeTranscriptApi(proxy_config=self.proxy_config)
            logger.debug("Using proxy for YouTube transcript API")
        else:
            api = YouTubeTranscriptApi()

        if language == "auto":
            transcript_list = api.list(video_id)
            try:
                transcript = transcript_list.find_generated_transcript(["en"])
            except Exception:
                transcript = transcript_list.find_transcript(
                    ["en", "es", "de", "fr", "pt", "ja", "ko", "zh"]
                )
            transcript_data = transcript.fetch()
            detected_language = transcript.language_code
        else:
            transcript_list = api.list(video_id)
            transcript = transcript_list.find_transcript([language])
            transcript_data = transcript.fetch()
            detected_language = language

        segments = [
            TranscriptSegment(
                text=entry.text.strip(),
                start=entry.start,
                duration=entry.duration,
            )
            for entry in transcript_data
        ]

        return TranscriptResult(
            segments=segments,
            language=detected_language,
            metadata={},
        )


class TranscriptAPIProvider(TranscriptProvider):
    """Provider using TranscriptAPI.com (paid, reliable, no IP blocks)."""

    BASE_URL = "https://transcriptapi.com/api/v2/youtube/transcript"

    def __init__(self, api_key: str):
        """Initialize provider.

        Args:
            api_key: TranscriptAPI.com API key
        """
        self.api_key = api_key

    def fetch(
        self,
        video_id: str,
        language: str = "auto",  # noqa: ARG002
    ) -> TranscriptResult:
        """Fetch transcript using TranscriptAPI.com."""
        headers = {
            "Authorization": f"Bearer {self.api_key}",
        }
        params = {
            "video_url": video_id,
            "format": "json",
            "include_timestamp": "true",
            "send_metadata": "true",
        }

        with httpx.Client(timeout=60) as client:
            response = client.get(self.BASE_URL, headers=headers, params=params)

            if response.status_code == httpx.codes.UNAUTHORIZED:
                msg = "TranscriptAPI: Invalid API key"
                raise RuntimeError(msg)
            if response.status_code == httpx.codes.PAYMENT_REQUIRED:
                data = response.json()
                detail = data.get("detail", {})
                msg = (
                    f"TranscriptAPI: {detail.get('message', 'Payment required')}. "
                    f"Action: {detail.get('action_url', 'https://transcriptapi.com/billing')}"
                )
                raise RuntimeError(msg)
            if response.status_code == httpx.codes.NOT_FOUND:
                msg = "TranscriptAPI: Transcript not available for this video"
                raise RuntimeError(msg)
            if response.status_code == httpx.codes.TOO_MANY_REQUESTS:
                retry_after = response.headers.get("Retry-After", "60")
                msg = f"TranscriptAPI: Rate limited. Retry after {retry_after}s"
                raise RuntimeError(msg)
            if response.status_code != httpx.codes.OK:
                msg = f"TranscriptAPI error: {response.status_code} {response.text}"
                raise RuntimeError(msg)

            data = response.json()

        transcript_raw = data.get("transcript", [])
        segments = []
        for entry in transcript_raw:
            if isinstance(entry, dict):
                segments.append(
                    TranscriptSegment(
                        text=entry.get("text", "").strip(),
                        start=entry.get("start", 0),
                        duration=entry.get("duration", 0),
                    )
                )

        detected_language = data.get("language", "en")

        meta = data.get("metadata", {}) or {}
        metadata = {
            "title": meta.get("title"),
            "channel": meta.get("author_name"),
            "thumbnail": meta.get("thumbnail_url"),
        }

        return TranscriptResult(
            segments=segments,
            language=detected_language,
            metadata=metadata,
        )


class AutoFallbackProvider(TranscriptProvider):
    """Try free provider first, fall back to paid API if blocked."""

    def __init__(self, api_key: str, proxy_config=None):
        """Initialize provider.

        Args:
            api_key: TranscriptAPI.com API key for fallback
            proxy_config: Optional proxy config for free provider
        """
        self.free_provider = YouTubeTranscriptAPIProvider(proxy_config=proxy_config)
        self.paid_provider = TranscriptAPIProvider(api_key=api_key)

    def fetch(
        self,
        video_id: str,
        language: str = "auto",
    ) -> TranscriptResult:
        """Try free provider, fall back to paid if blocked."""
        try:
            logger.info("Trying free youtube-transcript-api...")
            return self.free_provider.fetch(video_id, language)
        except Exception as e:
            error_msg = str(e)
            if "IpBlocked" in error_msg or "blocked" in error_msg.lower() or "429" in error_msg:
                logger.warning(
                    "Free API blocked (%s), falling back to TranscriptAPI.com", error_msg
                )
                return self.paid_provider.fetch(video_id, language)
            raise


def create_proxy_config(
    webshare_user: str | None = None,
    webshare_pass: str | None = None,
    proxy_url: str | None = None,
):
    """Create proxy configuration for youtube-transcript-api.

    Checks environment variables if arguments not provided:
    - WEBSHARE_USER, WEBSHARE_PASS for Webshare proxy
    - YOUTUBE_PROXY for generic proxy URL

    Args:
        webshare_user: Webshare username
        webshare_pass: Webshare password
        proxy_url: Generic proxy URL (http://user:pass@host:port)

    Returns:
        WebshareProxyConfig, GenericProxyConfig, or None
    """
    webshare_user = webshare_user or os.environ.get("WEBSHARE_USER")
    webshare_pass = webshare_pass or os.environ.get("WEBSHARE_PASS")
    proxy_url = proxy_url or os.environ.get("YOUTUBE_PROXY")

    if webshare_user and webshare_pass:
        logger.info("Using Webshare proxy for YouTube transcripts")
        return WebshareProxyConfig(
            proxy_username=webshare_user,
            proxy_password=webshare_pass,
        )
    if proxy_url:
        # Log proxy without credentials
        safe_url = proxy_url.split("@")[-1] if "@" in proxy_url else proxy_url
        logger.info("Using proxy for YouTube transcripts: %s", safe_url)
        return GenericProxyConfig(
            http_url=proxy_url,
            https_url=proxy_url,
        )

    return None


def create_provider(
    provider_name: str = "auto",
    api_key: str | None = None,
    proxy_config=None,
) -> TranscriptProvider:
    """Create the appropriate transcript provider.

    Checks TRANSCRIPTAPI_KEY environment variable if api_key not provided.

    Args:
        provider_name: One of "youtube-transcript-api", "transcriptapi", "auto"
        api_key: TranscriptAPI.com API key
        proxy_config: Proxy configuration for free provider

    Returns:
        Configured TranscriptProvider instance
    """
    api_key = api_key or os.environ.get("TRANSCRIPTAPI_KEY")

    if provider_name == "transcriptapi":
        if not api_key:
            msg = "TranscriptAPI requires an API key. Set TRANSCRIPTAPI_KEY environment variable."
            raise ValueError(msg)
        return TranscriptAPIProvider(api_key=api_key)

    if provider_name == "auto":
        # Auto mode: use proxy if available, fall back to paid API if we have a key
        if api_key:
            return AutoFallbackProvider(api_key=api_key, proxy_config=proxy_config)
        if proxy_config:
            # No paid API key, but we have proxy - use free with proxy
            logger.info("No TRANSCRIPTAPI_KEY set, using free API with proxy only")
            return YouTubeTranscriptAPIProvider(proxy_config=proxy_config)
        # No proxy, no paid key - just use free and hope for the best
        logger.warning(
            "No proxy or TRANSCRIPTAPI_KEY configured. "
            "YouTube may block your IP. Set WEBSHARE_USER/WEBSHARE_PASS "
            "or TRANSCRIPTAPI_KEY for reliability."
        )
        return YouTubeTranscriptAPIProvider()

    # default: youtube-transcript-api
    return YouTubeTranscriptAPIProvider(proxy_config=proxy_config)
