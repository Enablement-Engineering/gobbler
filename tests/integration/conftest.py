"""Fixtures for relay integration tests."""

import pytest
from aiohttp.test_utils import TestClient, TestServer

from gobbler_relay import relay


@pytest.fixture(autouse=True)
def reset_relay_state():
    """Keep process-global relay state isolated between tests."""
    relay.websocket_connections.clear()
    relay.pending_commands.clear()
    yield
    relay.websocket_connections.clear()
    relay.pending_commands.clear()


@pytest.fixture
async def relay_client():
    """Start the real relay application on an ephemeral local port."""
    client = TestClient(TestServer(relay.create_app()))
    await client.start_server()
    yield client
    await client.close()
