"""Integration tests for HTTP-to-WebSocket relay command dispatch."""

import asyncio

import pytest

pytestmark = pytest.mark.integration


async def test_http_command_round_trip_through_extension(relay_client):
    """An HTTP command reaches the extension and returns its real response."""
    websocket = await relay_client.ws_connect("/ws")
    await websocket.send_json({"type": "register"})
    await websocket.receive_json(timeout=2)

    request_task = asyncio.create_task(
        relay_client.post(
            "/command",
            json={
                "command": "execute_script",
                "params": {"script": "document.title"},
                "timeout": 2,
            },
        )
    )

    command = await websocket.receive_json(timeout=2)
    assert command["type"] == "command"
    assert command["command"] == "execute_script"
    assert command["params"] == {"script": "document.title"}

    expected_result = {"success": True, "result": "Example Domain"}
    await websocket.send_json(
        {
            "type": "command_response",
            "command_id": command["command_id"],
            "result": expected_result,
        }
    )

    response = await request_task
    assert response.status == 200
    assert await response.json() == expected_result

    await websocket.close()
