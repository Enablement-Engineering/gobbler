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
import logging
import sys
import uuid

import websockets

# Configure logging for test output
logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)


async def test_websocket():
    """Test WebSocket connection and command execution."""
    uri = "ws://localhost:4625/ws"

    logger.info("Connecting to %s...", uri)

    try:
        async with websockets.connect(uri) as websocket:
            logger.info("✓ WebSocket connected")

            # Register with server
            await websocket.send(
                json.dumps(
                    {
                        "type": "register",
                    }
                )
            )
            logger.info("✓ Sent registration")

            # Wait for registration response
            response = await websocket.recv()
            data = json.loads(response)
            logger.info("✓ Received: %s", data)

            # Try to send a command (this simulates what the MCP tools do)
            command_id = str(uuid.uuid4())
            await websocket.send(
                json.dumps(
                    {
                        "type": "command",
                        "command_id": command_id,
                        "command": "list_gobbler_tabs",
                        "params": {},
                    }
                )
            )
            logger.info("✓ Sent command 'list_gobbler_tabs' (id: %s)", command_id)

            # Wait for response (with timeout)
            try:
                response = await asyncio.wait_for(websocket.recv(), timeout=5.0)
                data = json.loads(response)
                logger.info("✓ Received response: %s", json.dumps(data, indent=2))
            except TimeoutError:
                logger.info("✗ Timeout waiting for command response")
                logger.info("\nNote: This is expected if no browser extension is connected.")
                logger.info(
                    "The WebSocket connection works, but commands need the extension to respond."
                )

    except ConnectionRefusedError:
        logger.info("✗ Connection refused - is the MCP server running?")
        return False
    except Exception as e:
        logger.info("✗ Error: %s", e)
        return False

    return True


if __name__ == "__main__":
    success = asyncio.run(test_websocket())
    sys.exit(0 if success else 1)
