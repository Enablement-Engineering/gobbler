"""Tests for retryable HTTP client logging behavior."""

from __future__ import annotations

import logging
from typing import Any

import httpx
import pytest

from gobbler_core.utils.http_client import RetryableHTTPClient

LOGGER_NAME = "gobbler_core.utils.http_client"


async def test_post_final_http_status_error_retries_without_unexpected_traceback(
    httpx_mock: Any,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Final retryable POST HTTP failures are re-raised without exception logging."""
    url = "https://service.example/crawl"
    for _ in range(3):
        httpx_mock.add_response(method="POST", url=url, status_code=500)

    with caplog.at_level(logging.WARNING, logger=LOGGER_NAME):
        async with RetryableHTTPClient(max_retries=3) as client:
            with pytest.raises(httpx.HTTPStatusError):
                await client.post(url, json={"url": "https://example.com"})

    retry_records = [
        record
        for record in caplog.records
        if record.message.startswith("Request failed with status")
    ]
    assert [record.levelno for record in retry_records] == [logging.WARNING, logging.WARNING]
    assert [record.message for record in retry_records] == [
        "Request failed with status 500, retrying (1/3)...",
        "Request failed with status 500, retrying (2/3)...",
    ]
    assert not any(
        "Request failed with unexpected error" in record.message for record in caplog.records
    )
    assert not any(record.exc_info for record in caplog.records)


async def test_get_final_http_status_error_retries_without_unexpected_traceback(
    httpx_mock: Any,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Final retryable GET HTTP failures are re-raised without exception logging."""
    url = "https://service.example/status"
    for _ in range(2):
        httpx_mock.add_response(method="GET", url=url, status_code=503)

    with caplog.at_level(logging.WARNING, logger=LOGGER_NAME):
        async with RetryableHTTPClient(max_retries=2) as client:
            with pytest.raises(httpx.HTTPStatusError):
                await client.get(url)

    retry_records = [
        record
        for record in caplog.records
        if record.message.startswith("Request failed with status")
    ]
    assert len(retry_records) == 1
    assert retry_records[0].levelno == logging.WARNING
    assert retry_records[0].message == "Request failed with status 503, retrying (1/2)..."
    assert not any(
        "Request failed with unexpected error" in record.message for record in caplog.records
    )
    assert not any(record.exc_info for record in caplog.records)


async def test_unexpected_get_exception_still_logs_traceback(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Unexpected non-HTTP errors keep traceback logging for debugging."""

    class FailingClient:
        async def get(self, url: str, headers: dict[str, str] | None = None) -> httpx.Response:
            msg = "boom"
            raise ValueError(msg)

    client = RetryableHTTPClient(max_retries=1)
    client._client = FailingClient()  # type: ignore[assignment]

    with (
        caplog.at_level(logging.ERROR, logger=LOGGER_NAME),
        pytest.raises(ValueError, match="boom"),
    ):
        await client.get("https://service.example/status")

    unexpected_records = [
        record
        for record in caplog.records
        if record.message == "Request failed with unexpected error"
    ]
    assert len(unexpected_records) == 1
    assert unexpected_records[0].exc_info is not None
    assert unexpected_records[0].exc_info[0] is ValueError


async def test_unexpected_http_status_error_still_logs_traceback(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """HTTP status errors outside retry exhaustion remain unexpected errors."""

    class FailingClient:
        async def get(self, url: str, headers: dict[str, str] | None = None) -> httpx.Response:
            request = httpx.Request("GET", url)
            response = httpx.Response(418, request=request)
            msg = "teapot"
            raise httpx.HTTPStatusError(msg, request=request, response=response)

    client = RetryableHTTPClient(max_retries=1)
    client._client = FailingClient()  # type: ignore[assignment]

    with (
        caplog.at_level(logging.ERROR, logger=LOGGER_NAME),
        pytest.raises(httpx.HTTPStatusError, match="teapot"),
    ):
        await client.get("https://service.example/status")

    unexpected_records = [
        record
        for record in caplog.records
        if record.message == "Request failed with unexpected error"
    ]
    assert len(unexpected_records) == 1
    assert unexpected_records[0].exc_info is not None
    assert unexpected_records[0].exc_info[0] is httpx.HTTPStatusError
