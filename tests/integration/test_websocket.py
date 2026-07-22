"""Integration tests for the relay WebSocket protocol."""

import pytest

from gobbler_core import __version__

pytestmark = pytest.mark.integration


async def test_websocket_registration_and_ping(relay_client):
    """A real WebSocket client can register and exchange a heartbeat."""
    websocket = await relay_client.ws_connect("/ws")

    await websocket.send_json({"type": "register"})
    registration = await websocket.receive_json(timeout=2)
    assert registration == {"type": "registered", "server_version": __version__}

    await websocket.send_json({"type": "ping"})
    assert await websocket.receive_json(timeout=2) == {"type": "pong"}

    await websocket.close()
