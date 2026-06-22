"""Crawl4AI web page conversion provider.

This provider uses the Crawl4AI Docker service for web page scraping
and markdown conversion with JavaScript rendering support.
"""

from __future__ import annotations

import asyncio
import logging
import re
import shlex
from dataclasses import dataclass
from typing import Any, cast
from urllib.parse import unquote, urlparse, urlsplit, urlunparse, urlunsplit

import httpx

from gobbler_core.providers.registry import ProviderRegistry
from gobbler_core.providers.webpage.base import WebPageProvider, WebPageResult
from gobbler_core.utils.http_client import RetryableHTTPClient
from gobbler_core.utils.redaction import REDACTED, redact_url_userinfo, redact_value

logger = logging.getLogger(__name__)

CRAWL4AI_PROBE_URL = "https://example.com"
DIAGNOSTIC_SNIPPET_LIMIT = 500
MIN_SECRET_FRAGMENT_LENGTH = 4
HOST_PORT_PROXY_PARTS = 2
AUTHENTICATED_HOST_PORT_PROXY_PARTS = 4


@dataclass
class Crawl4AIConversionError(RuntimeError):
    """Sanitized Crawl4AI conversion error with machine-readable diagnostics."""

    message: str
    diagnostics: dict[str, Any]

    def __post_init__(self) -> None:
        """Initialize RuntimeError with the sanitized message."""
        sanitized_message = str(redact_value(self.message))
        sanitized_diagnostics = redact_value(self.diagnostics)
        self.message = sanitized_message
        self.diagnostics = (
            cast("dict[str, Any]", sanitized_diagnostics)
            if isinstance(sanitized_diagnostics, dict)
            else {}
        )
        super().__init__(sanitized_message)


def _shorthand_proxy_credentials(proxy_url: str) -> tuple[str, str] | None:
    """Return username/password from host:port:username:password proxy shorthand."""
    if "://" in proxy_url:
        return None
    parts = proxy_url.split(":")
    if len(parts) != AUTHENTICATED_HOST_PORT_PROXY_PARTS or not all(parts):
        return None
    _host, _port, username, password = parts
    return unquote(username), unquote(password)


def _sensitive_fragments(
    api_token: str | None = None,
    proxy_url: str | None = None,
) -> list[str]:
    """Return secret-like fragments that should be removed from diagnostics."""
    fragments: list[str] = []
    if api_token:
        fragments.append(api_token)

    if proxy_url:
        fragments.append(proxy_url)
        shorthand_credentials = _shorthand_proxy_credentials(proxy_url)
        if shorthand_credentials is not None:
            username, password = shorthand_credentials
            fragments.extend([username, password, f"{username}:{password}"])
        try:
            parsed = urlparse(proxy_url)
        except ValueError:
            parsed = None
        if parsed is not None:
            if parsed.username:
                fragments.append(unquote(parsed.username))
            if parsed.password:
                fragments.append(unquote(parsed.password))
            if "@" in parsed.netloc:
                fragments.append(parsed.netloc.split("@", 1)[0])

    return [fragment for fragment in fragments if len(fragment) >= MIN_SECRET_FRAGMENT_LENGTH]


def _redact_text(text: str, sensitive_fragments: list[str] | None = None) -> str:
    """Redact known credentials and URL userinfo from diagnostic text."""
    redacted = str(redact_value(text))
    for fragment in sensitive_fragments or []:
        redacted = redacted.replace(fragment, REDACTED)
    return redacted


def _response_body_snippet(
    response: httpx.Response,
    sensitive_fragments: list[str],
) -> str | None:
    """Return a short sanitized response body snippet for diagnostics."""
    try:
        body = response.text.strip()
    except Exception:
        return None

    if not body:
        return None

    redacted_body = _redact_text(body, sensitive_fragments)
    snippet = redacted_body[:DIAGNOSTIC_SNIPPET_LIMIT]
    redaction_index = redacted_body.find(REDACTED)
    if 0 <= redaction_index < DIAGNOSTIC_SNIPPET_LIMIT and REDACTED not in snippet:
        prefix_length = DIAGNOSTIC_SNIPPET_LIMIT - len(REDACTED)
        snippet = f"{redacted_body[:prefix_length]}{REDACTED}"
    return snippet


def _endpoint_path(response: httpx.Response) -> str:
    """Return a stable endpoint path from an HTTPX response."""
    try:
        return urlparse(str(response.request.url)).path or "unknown"
    except RuntimeError:
        return "unknown"


def _extract_response_error(
    data: Any,
    sensitive_fragments: list[str],
) -> str | None:
    """Extract a sanitized error-like field from a Crawl4AI response payload."""
    if not isinstance(data, dict):
        return None

    for key in ("error", "message", "detail"):
        value = data.get(key)
        if value:
            return _redact_text(str(value), sensitive_fragments)[:DIAGNOSTIC_SNIPPET_LIMIT]
    return None


def _build_diagnostic_error(
    *,
    message: str,
    stage: str,
    proxy_configured: bool,
    service_url: str,
    source_url: str | None = None,
    endpoint: str = "unknown",
    status_code: int | None = None,
    response_body: str | None = None,
    response_error: str | None = None,
    response_keys: list[str] | None = None,
) -> Crawl4AIConversionError:
    """Create a sanitized Crawl4AIConversionError."""
    suggested_command: str | None = None
    advice = (
        "Crawl4AI /health only confirms the service is reachable; inspect the "
        "Crawl4AI container logs and proxy settings for /crawl failures."
    )
    if proxy_configured:
        advice = (
            "A proxy is configured for Crawl4AI; verify proxy credentials, network "
            "reachability, and Crawl4AI container logs."
        )
        if source_url:
            suggested_command = _suggest_no_proxy_command(source_url)
            advice = (
                "A proxy is configured for Crawl4AI; retry the single-page CLI "
                f"without the proxy to isolate degraded proxy paths: {suggested_command}. "
                "Also verify proxy credentials, network reachability, and Crawl4AI "
                "container logs."
            )
            message = f"{message} Retry with --no-proxy to isolate proxy-path failures."

    diagnostics: dict[str, Any] = {
        "provider": "crawl4ai",
        "stage": stage,
        "endpoint": endpoint,
        "service_url": service_url,
        "proxy_configured": proxy_configured,
        "advice": advice,
    }
    if suggested_command is not None:
        diagnostics["suggested_command_fragment"] = suggested_command
    if status_code is not None:
        diagnostics["status_code"] = status_code
    if response_body:
        diagnostics["response_body_snippet"] = response_body
    if response_error:
        diagnostics["response_error"] = response_error
    if response_keys:
        diagnostics["response_keys"] = response_keys

    return Crawl4AIConversionError(message=message, diagnostics=diagnostics)


def _suggest_no_proxy_command(source_url: str) -> str:
    """Return a shell-safe single-page retry command for proxy diagnostics."""
    safe_url = _redact_retry_url(source_url)
    return f"gobbler webpage {shlex.quote(safe_url)} --no-proxy"


def _redact_retry_url(source_url: str) -> str:
    """Return a URL origin safe to embed in proxy retry guidance."""
    try:
        parts = urlsplit(source_url)
    except ValueError:
        return redact_url_userinfo(source_url)
    retry_url = urlunsplit((parts.scheme, parts.netloc, "/", "", ""))
    return redact_url_userinfo(retry_url)


def _raise_for_crawl4ai_status(
    response: httpx.Response,
    *,
    stage: str,
    service_url: str,
    api_token: str | None,
    proxy_url: str | None,
    source_url: str | None = None,
) -> None:
    """Raise a sanitized diagnostic error for non-success Crawl4AI responses."""
    try:
        response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        sensitive = _sensitive_fragments(api_token=api_token, proxy_url=proxy_url)
        if source_url:
            sensitive.extend([source_url, redact_url_userinfo(source_url)])
        endpoint = _endpoint_path(exc.response)
        body = _response_body_snippet(exc.response, sensitive)
        message = (
            f"Crawl4AI {endpoint} returned HTTP {exc.response.status_code} during "
            f"{stage}. Service health may still pass while conversion is failing."
        )
        if body:
            message = f"{message} Response: {body}"
        raise _build_diagnostic_error(
            message=message,
            stage=stage,
            endpoint=endpoint,
            service_url=service_url,
            source_url=source_url,
            proxy_configured=proxy_url is not None,
            status_code=exc.response.status_code,
            response_body=body,
        ) from exc


def _format_proxy_server(scheme: str, host: str, port: int | None) -> str:
    """Return a Playwright-compatible proxy server URL."""
    bracketed_host = f"[{host}]" if ":" in host and not host.startswith("[") else host
    server = f"{scheme}://{bracketed_host}"
    if port is not None:
        server = f"{server}:{port}"
    return server


def _parse_host_port_proxy(proxy_url: str) -> dict[str, str] | None:
    """Parse Crawl4AI shorthand proxy formats."""
    parts = proxy_url.split(":")
    if len(parts) == HOST_PORT_PROXY_PARTS:
        host, port = parts
        if host and port:
            return {"server": f"http://{host}:{port}"}
    if len(parts) == AUTHENTICATED_HOST_PORT_PROXY_PARTS:
        host, port, username, password = parts
        if host and port and username and password:
            return {
                "server": f"http://{host}:{port}",
                "username": unquote(username),
                "password": unquote(password),
            }
    return None


def _parse_proxy_url(proxy_url: str) -> dict[str, str]:
    """Parse proxy URL into Crawl4AI proxy_config format."""
    clean_proxy_url = proxy_url.strip()
    if "://" not in clean_proxy_url:
        shorthand_config = _parse_host_port_proxy(clean_proxy_url)
        if shorthand_config is not None:
            return shorthand_config

    parsed = urlparse(clean_proxy_url)
    if not parsed.scheme or not parsed.hostname:
        msg = "Invalid Crawl4AI proxy URL; expected scheme://host[:port] or host:port"
        raise ValueError(msg)

    config: dict[str, str] = {
        "server": _format_proxy_server(parsed.scheme, parsed.hostname, parsed.port)
    }
    if parsed.username:
        config["username"] = unquote(parsed.username)
    if parsed.password:
        config["password"] = unquote(parsed.password)
    return config


def _build_crawl_request(
    url: str,
    *,
    proxy_url: str | None = None,
    wait_for: str | None = None,
    headless: bool = True,
) -> dict[str, Any]:
    """Build a Crawl4AI /crawl request payload."""
    crawler_params: dict[str, Any] = {
        "stream": False,
        "cache_mode": "bypass",
    }
    if wait_for:
        crawler_params["wait_for"] = wait_for

    if proxy_url:
        crawler_params["proxy_config"] = _parse_proxy_url(proxy_url)

    return {
        "urls": [url],
        "browser_config": {
            "type": "BrowserConfig",
            "params": {"headless": headless},
        },
        "crawler_config": {
            "type": "CrawlerRunConfig",
            "params": crawler_params,
        },
    }


def _probe_success(
    *,
    service_url: str,
    proxy_configured: bool,
    probe_url: str,
    stage: str,
    result_mode: str,
) -> dict[str, Any]:
    """Return a successful Crawl4AI probe payload."""
    return {
        "status": "ready",
        "ok": True,
        "provider": "crawl4ai",
        "stage": stage,
        "result_mode": result_mode,
        "probe_url": probe_url,
        "service_url": service_url,
        "proxy_configured": proxy_configured,
    }


def check_crawl4ai_conversion_probe(  # noqa: PLR0911
    service_url: str,
    *,
    api_token: str = "gobbler-local-token",  # noqa: S107
    proxy_url: str | None = None,
    probe_url: str = CRAWL4AI_PROBE_URL,
    timeout: float = 8.0,
) -> dict[str, Any]:
    """Submit a lightweight Crawl4AI /crawl probe and return sanitized readiness data.

    The probe intentionally checks the conversion endpoint instead of `/health`.
    For direct-result Crawl4AI APIs it validates that markdown is present. For
    task-id APIs it treats task acceptance as ready because this lightweight
    probe does not block on full task completion.
    """
    service_url = service_url.rstrip("/")
    headers = {"Authorization": f"Bearer {api_token}"}
    sensitive = _sensitive_fragments(api_token=api_token, proxy_url=proxy_url)

    try:
        with httpx.Client(timeout=timeout) as client:
            response = client.post(
                f"{service_url}/crawl",
                json=_build_crawl_request(probe_url, proxy_url=proxy_url),
                headers=headers,
            )
            _raise_for_crawl4ai_status(
                response,
                stage="crawl_probe",
                service_url=service_url,
                api_token=api_token,
                proxy_url=proxy_url,
            )
            data = response.json()
    except Crawl4AIConversionError as exc:
        result = {
            "status": "failed",
            "ok": False,
            "error": str(exc),
            **exc.diagnostics,
        }
        result["probe_url"] = probe_url
        return cast("dict[str, Any]", redact_value(result))
    except httpx.ConnectError:
        return {
            "status": "unavailable",
            "ok": False,
            "provider": "crawl4ai",
            "stage": "service_connection",
            "service_url": service_url,
            "proxy_configured": proxy_url is not None,
            "probe_url": probe_url,
            "error": "connection refused",
            "advice": "Start the Crawl4AI service before probing /crawl.",
        }
    except httpx.TimeoutException:
        return {
            "status": "failed",
            "ok": False,
            "provider": "crawl4ai",
            "stage": "crawl_probe",
            "service_url": service_url,
            "proxy_configured": proxy_url is not None,
            "probe_url": probe_url,
            "error": f"timeout after {timeout:g} seconds",
            "advice": "Crawl4AI /crawl did not respond within the probe timeout.",
        }
    except ValueError as exc:
        return {
            "status": "failed",
            "ok": False,
            "provider": "crawl4ai",
            "stage": "crawl_probe",
            "service_url": service_url,
            "proxy_configured": proxy_url is not None,
            "probe_url": probe_url,
            "error": _redact_text(f"invalid JSON response: {exc}", sensitive),
            "advice": "Inspect the Crawl4AI service response for /crawl.",
        }
    except Exception as exc:
        return {
            "status": "failed",
            "ok": False,
            "provider": "crawl4ai",
            "stage": "crawl_probe",
            "service_url": service_url,
            "proxy_configured": proxy_url is not None,
            "probe_url": probe_url,
            "error": _redact_text(str(exc), sensitive),
            "advice": "Inspect Crawl4AI container logs for /crawl failures.",
        }

    if isinstance(data, dict) and "results" in data and data.get("success"):
        results = data.get("results") or []
        if results:
            try:
                Crawl4AIProvider(
                    service_url=service_url,
                    api_token=api_token,
                    proxy_url=proxy_url,
                )._extract_markdown(results[0])
            except RuntimeError as exc:
                return {
                    "status": "failed",
                    "ok": False,
                    "provider": "crawl4ai",
                    "stage": "crawl_result",
                    "service_url": service_url,
                    "proxy_configured": proxy_url is not None,
                    "probe_url": probe_url,
                    "error": _redact_text(str(exc), sensitive),
                    "advice": "Crawl4AI /crawl responded, but no markdown was produced.",
                }
            return _probe_success(
                service_url=service_url,
                proxy_configured=proxy_url is not None,
                probe_url=probe_url,
                stage="crawl_result",
                result_mode="direct_results",
            )

    if isinstance(data, dict) and data.get("task_id"):
        return _probe_success(
            service_url=service_url,
            proxy_configured=proxy_url is not None,
            probe_url=probe_url,
            stage="crawl_start",
            result_mode="task_id",
        )

    response_keys = sorted(str(key) for key in data) if isinstance(data, dict) else None
    response_error = _extract_response_error(data, sensitive)
    error = _build_diagnostic_error(
        message=(
            "Crawl4AI /crawl probe returned an unexpected response format. "
            "Service health may still pass while conversion is not ready."
        ),
        stage="crawl_probe",
        endpoint="/crawl",
        service_url=service_url,
        proxy_configured=proxy_url is not None,
        response_error=response_error,
        response_keys=response_keys,
    )
    return cast(
        "dict[str, Any]",
        redact_value(
            {
                "status": "failed",
                "ok": False,
                "error": str(error),
                "probe_url": probe_url,
                **error.diagnostics,
            }
        ),
    )


class Crawl4AIProvider(WebPageProvider):
    """Web page conversion provider using Crawl4AI Docker service.

    Scrapes web pages and converts them to markdown using the Crawl4AI
    service running in Docker. Supports JavaScript rendering, content
    extraction, proxy configuration, and clean markdown output.

    Attributes:
        service_url: URL of the Crawl4AI service
        api_token: Authentication token for the service
        proxy_url: Optional proxy URL for browser requests

    Example:
        provider = Crawl4AIProvider(service_url="http://localhost:11235")
        result = await provider.fetch("https://example.com", timeout=60)
        print(result.markdown)

        # With proxy
        provider = Crawl4AIProvider(
            service_url="http://localhost:11235",
            proxy_url="http://user:pass@proxy.example.com:8080"
        )
    """

    def __init__(
        self,
        service_url: str = "http://localhost:11235",
        api_token: str = "gobbler-local-token",  # nosec B107 # noqa: S107 # nosec B107
        proxy_url: str | None = None,
    ) -> None:
        """Initialize the Crawl4AI provider.

        Args:
            service_url: URL of the Crawl4AI service
            api_token: Authentication token for the service
            proxy_url: Optional proxy URL for browser requests (e.g.,
                "http://user:pass@proxy.example.com:8080")
        """
        self.service_url = service_url.rstrip("/")
        self.api_token = api_token
        self.proxy_url = proxy_url

    @property
    def name(self) -> str:
        """Return provider name."""
        return "crawl4ai"

    def _safe_proxy_url(self, url: str) -> str:
        """Mask credentials in proxy URL for safe logging.

        Args:
            url: Proxy URL that may contain credentials

        Returns:
            URL with username and password replaced with '***'

        Example:
            >>> self._safe_proxy_url("http://user:pass@host:port")
            'http://***:***@host:port'
        """
        credentials = _shorthand_proxy_credentials(url)
        if credentials is not None:
            host, port, *_credential_parts = url.split(":")
            return f"{host}:{port}:***:***"

        parsed = urlparse(url)
        if parsed.username or parsed.password:
            # Reconstruct with masked credentials
            host = parsed.hostname or ""
            netloc = f"***:***@{host}"
            if parsed.port:
                netloc += f":{parsed.port}"
            return urlunparse(parsed._replace(netloc=netloc))
        return url

    def _parse_proxy_url(self, proxy_url: str) -> dict[str, str]:
        """Parse proxy URL into Crawl4AI proxy_config format.

        Crawl4AI requires authenticated proxies to use a proxy_config dict
        with separate server, username, and password fields.

        Args:
            proxy_url: Proxy URL (e.g., "http://user:pass@host:port")

        Returns:
            Dict with server, username, and password keys

        Example:
            >>> self._parse_proxy_url("http://user:pass@proxy.example.com:8080")
            {'server': 'http://proxy.example.com:8080', 'username': 'user', 'password': 'pass'}
        """
        return _parse_proxy_url(proxy_url)

    async def fetch(
        self,
        url: str,
        timeout: int = 30,
        **options: Any,
    ) -> WebPageResult:
        """Fetch and convert web page using Crawl4AI.

        Args:
            url: Web page URL to fetch
            timeout: Request timeout in seconds
            **options: Additional options:
                - include_images (bool): Include image markdown (default: True)
                - wait_for (str): CSS selector to wait for (optional)
                - headless (bool): Run browser in headless mode (default: True)

        Returns:
            WebPageResult with markdown content and metadata

        Raises:
            RuntimeError: If fetching or conversion fails
            TimeoutError: If request times out
        """
        include_images = options.get("include_images", True)
        wait_for = options.get("wait_for")
        headless = options.get("headless", True)

        if self.proxy_url:
            logger.debug("Using proxy for Crawl4AI: %s", self._safe_proxy_url(self.proxy_url))

        crawl_request = _build_crawl_request(
            url,
            proxy_url=self.proxy_url,
            wait_for=wait_for,
            headless=headless,
        )
        headers = {"Authorization": f"Bearer {self.api_token}"}
        sensitive = _sensitive_fragments(api_token=self.api_token, proxy_url=self.proxy_url)
        sensitive.extend([url, redact_url_userinfo(url)])

        try:
            async with RetryableHTTPClient(timeout=float(timeout)) as client:
                # Start crawl task
                response = await client.post(
                    f"{self.service_url}/crawl",
                    json=crawl_request,
                    headers=headers,
                )
                _raise_for_crawl4ai_status(
                    response,
                    stage="crawl_start",
                    service_url=self.service_url,
                    api_token=self.api_token,
                    proxy_url=self.proxy_url,
                    source_url=url,
                )
                task_data = response.json()

                # Handle both API formats:
                # - v0.7.x: Returns {"success": true, "results": [...]} directly
                # - v0.3.x: Returns {"task_id": "..."} for polling
                if "results" in task_data and task_data.get("success"):
                    # New API (v0.7.x) - results returned directly
                    results = task_data.get("results", [])
                    if not results:
                        raise _build_diagnostic_error(
                            message=(
                                "Crawl4AI /crawl returned success but no results. "
                                "Service health may still pass while conversion is failing."
                            ),
                            stage="crawl_result",
                            endpoint="/crawl",
                            service_url=self.service_url,
                            source_url=url,
                            proxy_configured=self.proxy_url is not None,
                            response_error=_extract_response_error(task_data, sensitive),
                            response_keys=sorted(str(key) for key in task_data),
                        )
                    result = results[0]
                elif task_data.get("task_id"):
                    # Old API (v0.3.x) - poll for completion
                    task_id = task_data["task_id"]
                    result = await self._poll_for_completion(
                        client,
                        task_id,
                        headers,
                        timeout,
                        source_url=url,
                    )
                else:
                    raise _build_diagnostic_error(
                        message=(
                            "Crawl4AI /crawl returned an unexpected response format. "
                            "Service health may still pass while conversion is failing."
                        ),
                        stage="crawl_start",
                        endpoint="/crawl",
                        service_url=self.service_url,
                        source_url=url,
                        proxy_configured=self.proxy_url is not None,
                        response_error=_extract_response_error(task_data, sensitive),
                        response_keys=sorted(str(key) for key in task_data),
                    )

                # Extract markdown
                markdown_content = self._extract_markdown(result)
                page_title = result.get("title") or result.get("metadata", {}).get(
                    "title", "Web Page"
                )

                # Remove images if requested
                if not include_images:
                    markdown_content = re.sub(r"!\[([^\]]*)\]\([^\)]+\)", r"\1", markdown_content)

                # Extract links if available
                links = result.get("links")

                return WebPageResult(
                    markdown=markdown_content,
                    title=page_title,
                    url=url,
                    metadata={
                        "service": "crawl4ai",
                    },
                    links=links,
                )

        except httpx.TimeoutException as e:
            msg = f"Request timed out after {timeout} seconds"
            raise TimeoutError(msg) from e
        except httpx.ConnectError as e:
            msg = (
                "Crawl4AI service unavailable. The service may not be running. "
                "Start with: docker-compose up -d crawl4ai"
            )
            raise RuntimeError(msg) from e
        except httpx.HTTPStatusError as e:
            _raise_for_crawl4ai_status(
                e.response,
                stage="crawl_start",
                service_url=self.service_url,
                api_token=self.api_token,
                proxy_url=self.proxy_url,
                source_url=url,
            )
            raise
        except RuntimeError:
            raise
        except Exception as e:
            msg = _redact_text(
                f"Web page conversion failed: {e}",
                _sensitive_fragments(api_token=self.api_token, proxy_url=self.proxy_url),
            )
            raise RuntimeError(msg) from e

    async def _poll_for_completion(
        self,
        client: RetryableHTTPClient,
        task_id: str,
        headers: dict[str, str],
        timeout: int,
        source_url: str | None = None,
    ) -> dict[str, Any]:
        """Poll Crawl4AI for task completion.

        Args:
            client: HTTP client
            task_id: Task ID to poll
            headers: HTTP headers
            timeout: Maximum wait time in seconds
            source_url: Original page URL for actionable retry diagnostics

        Returns:
            First result from completed task

        Raises:
            RuntimeError: If task fails or returns no results
            TimeoutError: If task doesn't complete in time
        """
        wait_interval = 1
        elapsed = 0

        while elapsed < timeout:
            await asyncio.sleep(wait_interval)
            elapsed += wait_interval

            response = await client.get(
                f"{self.service_url}/task/{task_id}",
                headers=headers,
            )
            _raise_for_crawl4ai_status(
                response,
                stage="task_poll",
                service_url=self.service_url,
                api_token=self.api_token,
                proxy_url=self.proxy_url,
                source_url=source_url,
            )
            task_status = response.json()

            status = task_status.get("status")

            if status == "completed":
                results = task_status.get("results")
                if not results:
                    sensitive = _sensitive_fragments(
                        api_token=self.api_token,
                        proxy_url=self.proxy_url,
                    )
                    if source_url:
                        sensitive.extend([source_url, redact_url_userinfo(source_url)])
                    raise _build_diagnostic_error(
                        message=(
                            "Crawl4AI task completed but returned no results. "
                            "Service health may still pass while conversion is failing."
                        ),
                        stage="task_result",
                        endpoint=f"/task/{task_id}",
                        service_url=self.service_url,
                        source_url=source_url,
                        proxy_configured=self.proxy_url is not None,
                        response_error=_extract_response_error(task_status, sensitive),
                        response_keys=sorted(str(key) for key in task_status),
                    )
                return results[0]

            if status == "failed":
                error = task_status.get("error", "Unknown error")
                sensitive = _sensitive_fragments(
                    api_token=self.api_token,
                    proxy_url=self.proxy_url,
                )
                if source_url:
                    sensitive.extend([source_url, redact_url_userinfo(source_url)])
                raise _build_diagnostic_error(
                    message=(
                        "Crawl4AI task failed during webpage conversion. "
                        f"Error: {_redact_text(str(error), sensitive)}"
                    ),
                    stage="task_result",
                    endpoint=f"/task/{task_id}",
                    service_url=self.service_url,
                    source_url=source_url,
                    proxy_configured=self.proxy_url is not None,
                    response_error=_redact_text(str(error), sensitive),
                    response_keys=sorted(str(key) for key in task_status),
                )

        msg = f"Crawl task did not complete within {timeout} seconds"
        raise TimeoutError(msg)

    def _extract_markdown(self, result: dict[str, Any]) -> str:
        """Extract markdown content from Crawl4AI result.

        Args:
            result: Crawl4AI result dictionary

        Returns:
            Extracted markdown content

        Raises:
            RuntimeError: If no markdown content found
        """
        markdown_content = None

        if isinstance(result.get("markdown"), dict):
            # Prefer fit_markdown if available, fallback to raw_markdown
            markdown_content = result["markdown"].get("fit_markdown") or result["markdown"].get(
                "raw_markdown"
            )
        elif isinstance(result.get("markdown"), str):
            markdown_content = result["markdown"]

        if not markdown_content:
            msg = "No markdown content in Crawl4AI response"
            raise RuntimeError(msg)

        return markdown_content


# Register provider with the registry
ProviderRegistry.register("webpage", "crawl4ai", Crawl4AIProvider)
