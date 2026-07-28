"""Unit tests for relay client payload validation."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from gobbler_relay.client import check_connection, get_connection_count, send_command


def _mock_async_client(response: MagicMock) -> MagicMock:
    """Create an async context manager returning a client with one response."""
    client = MagicMock()
    client.get = AsyncMock(return_value=response)
    client.post = AsyncMock(return_value=response)
    context_manager = MagicMock()
    context_manager.__aenter__ = AsyncMock(return_value=client)
    context_manager.__aexit__ = AsyncMock(return_value=None)
    return context_manager


def _mock_response(payload: object, status_code: int = 200) -> MagicMock:
    """Create a minimal HTTP response mock."""
    response = MagicMock()
    response.status_code = status_code
    response.json.return_value = payload
    return response


@pytest.mark.asyncio
@pytest.mark.parametrize("connection_count", [True, False, "1", 1.0, None])
async def test_get_connection_count_requires_non_boolean_int(
    connection_count: object,
) -> None:
    """Test bool and other non-integer connection counts are rejected."""
    response = _mock_response({"status": "ok", "websocket_connections": connection_count})

    with (
        patch(
            "gobbler_relay.client.httpx.AsyncClient",
            return_value=_mock_async_client(response),
        ),
        pytest.raises(
            RuntimeError,
            match=r"health response\.websocket_connections must be an integer",
        ),
    ):
        await get_connection_count()


@pytest.mark.asyncio
async def test_get_connection_count_accepts_integer() -> None:
    """Test a validated connection count is returned."""
    response = _mock_response({"status": "ok", "websocket_connections": 2})

    with patch(
        "gobbler_relay.client.httpx.AsyncClient",
        return_value=_mock_async_client(response),
    ):
        assert await get_connection_count() == 2


@pytest.mark.asyncio
@pytest.mark.parametrize("payload", [[], "ok", {1: "not a string key"}])
async def test_send_command_rejects_non_object_response(payload: object) -> None:
    """Test command responses must be string-keyed dictionaries."""
    response = _mock_response(payload)

    with (
        patch(
            "gobbler_relay.client.httpx.AsyncClient",
            return_value=_mock_async_client(response),
        ),
        pytest.raises(RuntimeError, match="command response must be a string-keyed dictionary"),
    ):
        await send_command("navigate")


@pytest.mark.asyncio
@pytest.mark.parametrize("payload", [[], {"error": 503}, {"message": "unavailable"}])
async def test_send_command_validates_503_error_payload(payload: object) -> None:
    """Test malformed service-unavailable responses raise clear payload errors."""
    response = _mock_response(payload, status_code=503)

    with (
        patch(
            "gobbler_relay.client.httpx.AsyncClient",
            return_value=_mock_async_client(response),
        ),
        pytest.raises(RuntimeError, match="Malformed relay payload: 503 error response"),
    ):
        await send_command("navigate")


@pytest.mark.asyncio
async def test_send_command_raises_validated_503_message() -> None:
    """Test a valid service-unavailable payload propagates its error message."""
    response = _mock_response({"error": "No browser extension connected"}, status_code=503)

    with (
        patch(
            "gobbler_relay.client.httpx.AsyncClient",
            return_value=_mock_async_client(response),
        ),
        pytest.raises(RuntimeError, match="No browser extension connected"),
    ):
        await send_command("navigate")


@pytest.mark.asyncio
async def test_send_command_rejects_non_json_503_payload() -> None:
    """Test an undecodable service-unavailable body raises a protocol error."""
    response = _mock_response(None, status_code=503)
    response.json.side_effect = ValueError("invalid JSON")

    with (
        patch(
            "gobbler_relay.client.httpx.AsyncClient",
            return_value=_mock_async_client(response),
        ),
        pytest.raises(
            RuntimeError,
            match="503 error response is not valid JSON",
        ),
    ):
        await send_command("navigate")


@pytest.mark.asyncio
async def test_check_connection_rejects_non_object_response() -> None:
    """Test connection-check responses must be string-keyed dictionaries."""
    response = _mock_response(["ok"])

    with (
        patch(
            "gobbler_relay.client.httpx.AsyncClient",
            return_value=_mock_async_client(response),
        ),
        pytest.raises(
            RuntimeError,
            match="connection check response must be a string-keyed dictionary",
        ),
    ):
        await check_connection()


@pytest.mark.asyncio
async def test_check_connection_validates_health_connection_count() -> None:
    """Test connection checks reject bool connection counts."""
    response = _mock_response({"status": "ok", "websocket_connections": True})

    with (
        patch(
            "gobbler_relay.client.httpx.AsyncClient",
            return_value=_mock_async_client(response),
        ),
        pytest.raises(
            RuntimeError,
            match=r"health response\.websocket_connections must be an integer",
        ),
    ):
        await check_connection()
