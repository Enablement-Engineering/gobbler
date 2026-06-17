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
