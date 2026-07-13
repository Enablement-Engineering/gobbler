"""Tests for webpage command diagnostic output."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest
import typer

from gobbler_cli.commands import convert
from gobbler_cli.output import OutputFormat
from gobbler_core.utils.redaction import REDACTED


class _NoopProgress:
    """No-op replacement for CLI progress in JSON output tests."""

    def __init__(self, *_args: Any, **_kwargs: Any) -> None:
        """Accept progress arguments without side effects."""

    def __enter__(self) -> _NoopProgress:
        """Enter the no-op context."""
        return self

    def __exit__(self, *_args: Any) -> None:
        """Exit the no-op context."""


class _DiagnosticError(RuntimeError):
    """Exception carrying structured diagnostics like Crawl4AIConversionError."""

    def __init__(self) -> None:
        """Create a diagnostic failure with a credential-bearing URL."""
        self.diagnostics = {
            "provider": "crawl4ai",
            "endpoint": "/crawl",
            "proxy_url": "http://proxy-user:proxy-pass@proxy.example:8080",
            "advice": "Check Crawl4AI proxy settings.",
        }
        super().__init__(
            "Crawl4AI /crawl returned HTTP 500 for http://proxy-user:proxy-pass@proxy.example:8080"
        )


@pytest.mark.asyncio
async def test_webpage_no_proxy_bypasses_default_provider_proxy_lookup(capsys) -> None:
    """The webpage command can bypass configured Crawl4AI proxy settings."""
    captured_kwargs: dict[str, Any] = {}

    async def convert_page(*_args: Any, **_kwargs: Any) -> tuple[str, dict[str, Any]]:
        return "# Page", {"title": "Page"}

    def get_provider(**kwargs: Any) -> object:
        captured_kwargs.update(kwargs)
        return object()

    with (
        patch("gobbler_cli.commands.convert.ProgressTracker", _NoopProgress),
        patch("gobbler_core.providers.webpage.get_default_provider", side_effect=get_provider),
        patch(
            "gobbler_core.converters.webpage.convert_webpage_to_markdown",
            side_effect=convert_page,
        ),
    ):
        await convert._convert_webpage(
            url="https://example.com",
            output=None,
            css_selector=None,
            clean=False,
            timeout=30,
            include_images=True,
            output_format=OutputFormat.JSON,
            use_proxy=False,
        )

    payload = json.loads(capsys.readouterr().out)

    assert captured_kwargs["use_proxy"] is False
    assert payload["success"] is True
    receipt = payload["receipt"]
    assert receipt["provider"] == "crawl4ai"
    assert receipt["proxy_mode"] == "disabled"
    assert receipt["source_host"] == "example.com"
    assert receipt["output_path"] is None
    assert receipt["byte_count"] == len(b"# Page")
    assert isinstance(receipt["elapsed_time_ms"], int)
    assert receipt["elapsed_time_ms"] >= 0


@pytest.mark.asyncio
async def test_webpage_json_success_includes_conversion_receipt(tmp_path: Path, capsys) -> None:
    """Standard proxied conversions report a safe machine-readable receipt."""
    output = tmp_path / "page.json"

    async def convert_page(*_args: Any, **_kwargs: Any) -> tuple[str, dict[str, Any]]:
        return "# Café", {"title": "Page", "provider": "crawl4ai"}

    with (
        patch("gobbler_core.providers.webpage.get_default_provider", return_value=object()),
        patch(
            "gobbler_core.converters.webpage.convert_webpage_to_markdown",
            side_effect=convert_page,
        ),
    ):
        await convert._convert_webpage(
            url="https://example.com/article",
            output=output,
            css_selector=None,
            clean=False,
            timeout=30,
            include_images=True,
            output_format=OutputFormat.JSON,
        )

    assert capsys.readouterr().out == ""
    payload = json.loads(output.read_text(encoding="utf-8"))
    receipt = payload["receipt"]

    assert receipt["provider"] == "crawl4ai"
    assert receipt["proxy_mode"] == "enabled"
    assert receipt["source_host"] == "example.com"
    assert receipt["output_path"] == str(output)
    assert receipt["byte_count"] == len("# Café".encode())
    assert isinstance(receipt["elapsed_time_ms"], int)
    assert receipt["elapsed_time_ms"] >= 0


@pytest.mark.asyncio
async def test_webpage_receipt_redacts_credential_bearing_source(capsys) -> None:
    """Receipt source details never include URL credentials or sensitive components."""
    source = (
        "https://user:password@example.com/reset/secret-path-token"
        "?session=query-secret#access_token=fragment-secret"
    )

    async def convert_page(*_args: Any, **_kwargs: Any) -> tuple[str, dict[str, Any]]:
        return "# Page", {"title": "Page", "provider": "crawl4ai"}

    with (
        patch("gobbler_core.providers.webpage.get_default_provider", return_value=object()),
        patch(
            "gobbler_core.converters.webpage.convert_webpage_to_markdown",
            side_effect=convert_page,
        ),
    ):
        await convert._convert_webpage(
            url=source,
            output=None,
            css_selector=None,
            clean=False,
            timeout=30,
            include_images=True,
            output_format=OutputFormat.JSON,
        )

    payload = json.loads(capsys.readouterr().out)
    receipt = payload["receipt"]
    dumped = json.dumps(payload)

    assert receipt["source_host"] == "example.com"
    for secret in (
        "user",
        "password",
        "secret-path-token",
        "query-secret",
        "fragment-secret",
    ):
        assert secret not in dumped


@pytest.mark.asyncio
async def test_webpage_json_error_includes_sanitized_diagnostics(capsys) -> None:
    """Webpage JSON failures include structured diagnostics without proxy credentials."""

    async def fail_conversion(*_args: Any, **_kwargs: Any) -> tuple[str, dict[str, Any]]:
        raise _DiagnosticError()

    with (
        patch("gobbler_cli.commands.convert.ProgressTracker", _NoopProgress),
        patch(
            "gobbler_core.converters.webpage.convert_webpage_to_markdown",
            side_effect=fail_conversion,
        ),
        pytest.raises(typer.Exit),
    ):
        await convert._convert_webpage(
            url="https://example.com",
            output=Path("unused.md"),
            css_selector=None,
            clean=False,
            timeout=30,
            include_images=True,
            output_format=OutputFormat.JSON,
        )

    payload = json.loads(capsys.readouterr().out)
    dumped = json.dumps(payload)

    assert payload["success"] is False
    assert payload["error_code"] == "WEBPAGE_CONVERSION_ERROR"
    assert payload["diagnostics"]["endpoint"] == "/crawl"
    assert payload["diagnostics"]["proxy_url"] == f"http://{REDACTED}@proxy.example:8080"
    assert "proxy-user" not in dumped
    assert "proxy-pass" not in dumped


@pytest.mark.asyncio
async def test_webpage_invalid_url_rejected_before_provider_lookup(capsys) -> None:
    """Malformed webpage URLs fail locally before provider lookup or conversion."""
    with (
        patch("gobbler_core.providers.webpage.get_default_provider") as get_provider,
        patch("gobbler_core.converters.webpage.convert_webpage_to_markdown") as convert_page,
        pytest.raises(typer.Exit) as exc_info,
    ):
        await convert._convert_webpage(
            url="not-a-url",
            output=None,
            css_selector=None,
            clean=False,
            timeout=30,
            include_images=True,
            output_format=OutputFormat.MARKDOWN,
        )

    captured = capsys.readouterr()

    assert exc_info.value.exit_code == 1
    assert "Invalid webpage URL" in captured.err
    get_provider.assert_not_called()
    convert_page.assert_not_called()


@pytest.mark.asyncio
async def test_webpage_invalid_url_json_has_stable_error_code(capsys) -> None:
    """Malformed webpage URLs produce the stable JSON invalid-input error code."""
    with (
        patch("gobbler_core.providers.webpage.get_default_provider") as get_provider,
        patch("gobbler_core.converters.webpage.convert_webpage_to_markdown") as convert_page,
        pytest.raises(typer.Exit) as exc_info,
    ):
        await convert._convert_webpage(
            url="not-a-url",
            output=None,
            css_selector=None,
            clean=False,
            timeout=30,
            include_images=True,
            output_format=OutputFormat.JSON,
        )

    payload = json.loads(capsys.readouterr().out)

    assert exc_info.value.exit_code == 1
    assert payload["success"] is False
    assert payload["error_code"] == "WEBPAGE_INVALID_URL"
    assert payload["source"] == "not-a-url"
    assert "Invalid webpage URL" in payload["error"]
    assert payload["suggestion"] == "Provide a URL like https://example.com."
    get_provider.assert_not_called()
    convert_page.assert_not_called()


@pytest.mark.parametrize(
    "malformed_url",
    [
        "http://[::1",
        "https://example.com:bad",
        "https://example.com:99999",
        "http://exa mple.com",
    ],
)
@pytest.mark.asyncio
async def test_webpage_malformed_absolute_url_json_has_stable_error_code(
    malformed_url: str,
    capsys,
) -> None:
    """Parser-error malformed absolute URLs fail locally with stable JSON code."""
    with (
        patch("gobbler_core.providers.webpage.get_default_provider") as get_provider,
        patch("gobbler_core.converters.webpage.convert_webpage_to_markdown") as convert_page,
        pytest.raises(typer.Exit) as exc_info,
    ):
        await convert._convert_webpage(
            url=malformed_url,
            output=None,
            css_selector=None,
            clean=False,
            timeout=30,
            include_images=True,
            output_format=OutputFormat.JSON,
        )

    payload = json.loads(capsys.readouterr().out)

    assert exc_info.value.exit_code == 1
    assert payload["success"] is False
    assert payload["error_code"] == "WEBPAGE_INVALID_URL"
    assert payload["source"] == malformed_url
    assert "Invalid webpage URL" in payload["error"]
    assert payload["suggestion"] == "Provide a URL like https://example.com."
    get_provider.assert_not_called()
    convert_page.assert_not_called()


@pytest.mark.asyncio
async def test_webpage_skip_if_exists_precedes_url_validation(tmp_path: Path, capsys) -> None:
    """Existing output keeps idempotent skip behavior even for an invalid source URL."""
    output = tmp_path / "existing.md"
    output.write_text("already converted", encoding="utf-8")

    with (
        patch("gobbler_core.providers.webpage.get_default_provider") as get_provider,
        patch("gobbler_core.converters.webpage.convert_webpage_to_markdown") as convert_page,
    ):
        await convert._convert_webpage(
            url="not-a-url",
            output=output,
            css_selector=None,
            clean=False,
            timeout=30,
            include_images=True,
            output_format=OutputFormat.JSON,
            skip_if_exists=True,
        )

    payload = json.loads(capsys.readouterr().out)

    assert payload["success"] is True
    assert payload["skipped"] is True
    assert payload["reason"] == "output_exists"
    assert payload["source"] == "not-a-url"
    get_provider.assert_not_called()
    convert_page.assert_not_called()


@pytest.mark.asyncio
async def test_webpage_invalid_url_clean_mode_does_not_call_selector_converter(capsys) -> None:
    """Invalid clean-mode URLs fail before selector conversion imports or dispatch."""
    with (
        patch(
            "gobbler_core.converters.webpage_selector.convert_webpage_with_selector"
        ) as convert_with_selector,
        pytest.raises(typer.Exit) as exc_info,
    ):
        await convert._convert_webpage(
            url="https://example.com:bad",
            output=None,
            css_selector=None,
            clean=True,
            timeout=30,
            include_images=True,
            output_format=OutputFormat.MARKDOWN,
        )

    captured = capsys.readouterr()

    assert exc_info.value.exit_code == 1
    assert "Invalid webpage URL" in captured.err
    convert_with_selector.assert_not_called()


@pytest.mark.asyncio
async def test_webpage_valid_http_url_dispatches_conversion(capsys) -> None:
    """Absolute http:// webpage URLs continue through the conversion path."""
    captured_url = ""

    async def convert_page(*_args: Any, **kwargs: Any) -> tuple[str, dict[str, Any]]:
        nonlocal captured_url
        captured_url = str(kwargs["url"])
        return "# Page", {"title": "Page"}

    with (
        patch("gobbler_cli.commands.convert.ProgressTracker", _NoopProgress),
        patch("gobbler_core.providers.webpage.get_default_provider", return_value=object()),
        patch(
            "gobbler_core.converters.webpage.convert_webpage_to_markdown",
            side_effect=convert_page,
        ),
    ):
        await convert._convert_webpage(
            url="http://example.com",
            output=None,
            css_selector=None,
            clean=False,
            timeout=30,
            include_images=True,
            output_format=OutputFormat.JSON,
        )

    payload = json.loads(capsys.readouterr().out)

    assert captured_url == "http://example.com"
    assert payload["success"] is True
