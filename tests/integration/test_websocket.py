#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["websockets>=12.0"]
# ///
"""
Test WebSocket connection to Gobbler HTTP server.

This tests the actual WebSocket protocol used by the browser extension.
"""

import asyncio
import json
import sys
import uuid

import websockets


async def test_websocket():
    """Test WebSocket connection and command execution."""
    uri = "ws://localhost:4625/ws"

    print(f"Connecting to {uri}...")

    try:
        async with websockets.connect(uri) as websocket:
            print("✓ WebSocket connected")

            # Register with server
            await websocket.send(json.dumps({
                "type": "register",
            }))
            print("✓ Sent registration")

            # Wait for registration response
            response = await websocket.recv()
            data = json.loads(response)
            print(f"✓ Received: {data}")

            # Try to send a command (this simulates what the MCP tools do)
            command_id = str(uuid.uuid4())
            await websocket.send(json.dumps({
                "type": "command",
                "command_id": command_id,
                "command": "list_gobbler_tabs",
                "params": {}
            }))
            print(f"✓ Sent command 'list_gobbler_tabs' (id: {command_id})")

            # Wait for response (with timeout)
            try:
                response = await asyncio.wait_for(websocket.recv(), timeout=5.0)
                data = json.loads(response)
                print(f"✓ Received response: {json.dumps(data, indent=2)}")
            except asyncio.TimeoutError:
                print("✗ Timeout waiting for command response")
                print("\nNote: This is expected if no browser extension is connected.")
                print("The WebSocket connection works, but commands need the extension to respond.")

    except ConnectionRefusedError:
        print("✗ Connection refused - is the MCP server running?")
        return False
    except Exception as e:
        print(f"✗ Error: {e}")
        return False

    return True


if __name__ == "__main__":
    success = asyncio.run(test_websocket())
    sys.exit(0 if success else 1)
