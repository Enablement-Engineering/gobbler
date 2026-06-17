"""Tests for Crawl4AI readiness and conversion diagnostics."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, patch

import httpx
import pytest

from gobbler_core.converters.webpage import convert_webpage_to_markdown
from gobbler_core.providers.webpage.crawl4ai import (
    Crawl4AIConversionError,
    Crawl4AIProvider,
    _build_crawl_request,
    _parse_proxy_url,
    _sensitive_fragments,
    check_crawl4ai_conversion_probe,
)
from gobbler_core.utils.redaction import REDACTED


def test_crawl_request_uses_documented_proxy_config_dict() -> None:
    """Crawl4AI requests send proxy_config as a CrawlerRunConfig dict."""
    request = _build_crawl_request(
        "https://example.com",
        proxy_url="http://proxy-user:proxy-pass@proxy.example:8080",
    )

    proxy_config = request["crawler_config"]["params"]["proxy_config"]

    assert proxy_config == {
        "server": "http://proxy.example:8080",
        "username": "proxy-user",
        "password": "proxy-pass",
    }
    assert "type" not in proxy_config
    assert "params" not in proxy_config


def test_crawl_request_omits_proxy_config_without_proxy() -> None:
    """Direct Crawl4AI requests do not send stale proxy settings."""
    request = _build_crawl_request("https://example.com", proxy_url=None)

    assert "proxy_config" not in request["crawler_config"]["params"]


def test_parse_proxy_url_decodes_credentials_and_preserves_missing_port() -> None:
    """Proxy URL parsing passes raw credentials and avoids inventing ports."""
    proxy_config = _parse_proxy_url("https://user%40name:p%40ss@proxy.example")

    assert proxy_config == {
        "server": "https://proxy.example",
        "username": "user@name",
        "password": "p@ss",
    }


def test_parse_proxy_url_accepts_crawl4ai_host_port_shorthand() -> None:
    """Crawl4AI shorthand proxy syntax is accepted for environment overrides."""
    proxy_config = _parse_proxy_url("proxy.example:8080:proxy-user:proxy-pass")

    assert proxy_config == {
        "server": "http://proxy.example:8080",
        "username": "proxy-user",
        "password": "proxy-pass",
    }


def test_shorthand_proxy_credentials_are_treated_as_sensitive() -> None:
    """Authenticated shorthand proxy credentials are redacted from diagnostics."""
    fragments = _sensitive_fragments(proxy_url="proxy.example:8080:proxy-user:proxy-pass")

    assert "proxy-user" in fragments
    assert "proxy-pass" in fragments
    assert "proxy-user:proxy-pass" in fragments


def test_safe_proxy_url_masks_authenticated_shorthand() -> None:
    """Provider debug logging masks authenticated proxy shorthand credentials."""
    provider = Crawl4AIProvider(proxy_url="proxy.example:8080:proxy-user:proxy-pass")

    assert provider._safe_proxy_url(provider.proxy_url or "") == "proxy.example:8080:***:***"


@pytest.mark.asyncio
async def test_fetch_http_error_includes_sanitized_diagnostics() -> None:
    """Crawl4AI HTTP failures include endpoint details without leaking proxy secrets."""
    proxy_url = "http://proxy-user:proxy-pass@proxy.example:8080"
    api_token = "secret-token"  # noqa: S105
    response = httpx.Response(
        500,
        request=httpx.Request("POST", "http://crawl.local/crawl"),
        json={
            "error": f"proxy auth failed for {proxy_url}",
            "token": api_token,
        },
    )

    with patch("gobbler_core.providers.webpage.crawl4ai.RetryableHTTPClient") as mock_client:
        client_instance = AsyncMock()
        mock_client.return_value.__aenter__.return_value = client_instance
        client_instance.post = AsyncMock(return_value=response)

        provider = Crawl4AIProvider(
            service_url="http://crawl.local",
            api_token=api_token,
            proxy_url=proxy_url,
        )

        with pytest.raises(Crawl4AIConversionError) as exc_info:
            await provider.fetch("https://example.com")

    error = exc_info.value
    dumped = json.dumps({"message": str(error), "diagnostics": error.diagnostics})

    assert "Crawl4AI /crawl returned HTTP 500" in str(error)
    assert error.diagnostics["status_code"] == 500
    assert error.diagnostics["proxy_configured"] is True
    assert REDACTED in dumped
    assert "proxy-user" not in dumped
    assert "proxy-pass" not in dumped
    assert api_token not in dumped


def test_conversion_probe_reports_crawl_failure_without_secrets(httpx_mock) -> None:
    """The /crawl probe reports failed conversion readiness with sanitized details."""
    proxy_url = "http://proxy-user:proxy-pass@proxy.example:8080"
    api_token = "secret-token"  # noqa: S105
    httpx_mock.add_response(
        method="POST",
        url="http://crawl.local/crawl",
        status_code=500,
        json={
            "error": f"proxy auth failed for {proxy_url}",
            "token": api_token,
        },
    )

    result = check_crawl4ai_conversion_probe(
        "http://crawl.local",
        api_token=api_token,
        proxy_url=proxy_url,
        timeout=1,
    )
    dumped = json.dumps(result)

    assert result["status"] == "failed"
    assert result["ok"] is False
    assert result["stage"] == "crawl_probe"
    assert result["status_code"] == 500
    assert result["proxy_configured"] is True
    assert REDACTED in dumped
    assert "proxy-user" not in dumped
    assert "proxy-pass" not in dumped
    assert api_token not in dumped


def test_response_snippet_redacts_before_truncating(httpx_mock) -> None:
    """Response snippets do not leak partial credentials that cross the cutoff."""
    proxy_secret = "supersecretpassword"  # noqa: S105
    proxy_url = f"http://proxy-user:{proxy_secret}@proxy.example:8080"
    body = "x" * 495 + proxy_secret + " after-secret"
    httpx_mock.add_response(
        method="POST",
        url="http://crawl.local/crawl",
        status_code=500,
        text=body,
    )

    result = check_crawl4ai_conversion_probe(
        "http://crawl.local",
        proxy_url=proxy_url,
        timeout=1,
    )
    snippet = result["response_body_snippet"]

    assert len(snippet) <= 500
    assert proxy_secret not in snippet
    assert "super" not in snippet
    assert REDACTED in snippet


@pytest.mark.asyncio
async def test_default_webpage_converter_accepts_direct_crawl4ai_results() -> None:
    """The no-provider converter path uses the provider and accepts direct results."""
    post_response = httpx.Response(
        200,
        request=httpx.Request("POST", "http://crawl.local/crawl"),
        json={
            "success": True,
            "results": [
                {
                    "markdown": "# Example\n\nConverted content.",
                    "title": "Example",
                }
            ],
        },
    )

    with (
        patch("gobbler_core.providers.proxy.get_crawl4ai_proxy_url", return_value=None),
        patch("gobbler_core.providers.webpage.crawl4ai.RetryableHTTPClient") as mock_client,
    ):
        client_instance = AsyncMock()
        mock_client.return_value.__aenter__.return_value = client_instance
        client_instance.post = AsyncMock(return_value=post_response)

        markdown, metadata = await convert_webpage_to_markdown(
            "https://example.com",
            service_url="http://crawl.local",
            api_token="local-token",  # noqa: S106
        )

    assert "# Example" in markdown
    assert "Converted content." in markdown
    assert metadata["title"] == "Example"
    assert metadata["provider"] == "crawl4ai"
