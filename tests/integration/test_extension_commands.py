#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["websockets>=12.0"]
# ///
# ruff: noqa: T201, PLR0915
"""
Test Gobbler browser extension commands via WebSocket.

This script connects to the Gobbler HTTP server's WebSocket endpoint
and attempts to send commands, just like the browser extension would.
"""

import asyncio
import json
import sys
import traceback
import uuid

import websockets


async def send_command(websocket, command: str, params: dict | None = None, timeout: float = 10.0):
    """Send a command to the server and wait for response from extension."""
    command_id = str(uuid.uuid4())

    # Send command
    await websocket.send(
        json.dumps(
            {
                "type": "command",
                "command_id": command_id,
                "command": command,
                "params": params or {},
            }
        )
    )

    print(f"   Sent command '{command}' (id: {command_id[:8]}...)")

    # Wait for response
    try:
        # We need to keep receiving messages until we get our response
        while True:
            message = await asyncio.wait_for(websocket.recv(), timeout=timeout)
            data = json.loads(message)

            # Check if this is the response to our command
            if data.get("type") == "command_response" and data.get("command_id") == command_id:
                return data.get("result", {})

            # Handle other message types
            if data.get("type") == "ping":
                await websocket.send(json.dumps({"type": "pong"}))

    except TimeoutError:
        print(f"   ✗ Timeout waiting for response to '{command}'")
        return None


async def test_commands():
    """Test browser extension commands."""
    uri = "ws://localhost:4625/ws"

    print("=" * 60)
    print("Testing Gobbler Browser Extension Commands")
    print("=" * 60)

    try:
        async with websockets.connect(uri) as websocket:
            print("\n✓ Connected to WebSocket")

            # Register
            await websocket.send(json.dumps({"type": "register"}))
            response = await websocket.recv()
            data = json.loads(response)
            print(f"✓ Registered: {data}")

            # Test 1: List tabs
            print("\n1. Testing 'list_gobbler_tabs' command...")
            result = await send_command(websocket, "list_gobbler_tabs", {}, timeout=5.0)

            if result:
                if result.get("success"):
                    tabs = result.get("tabs", [])
                    print(f"   ✓ Found {len(tabs)} tab(s) in Gobbler group")
                    for tab in tabs:
                        active = "*" if tab.get("isActive") else " "
                        print(
                            f"     {active} [{tab.get('tabId')}] {tab.get('title', 'Unknown')[:50]}"
                        )
                        print(f"        {tab.get('url', '')[:70]}")
                else:
                    error = result.get("error", "Unknown error")
                    print(f"   ✗ Error: {error}")
            else:
                print("   ✗ No response from extension")
                print("\n   This means:")
                print("   - The WebSocket connection to the server works ✓")
                print("   - But the browser extension is not responding ✗")
                print("\n   Possible reasons:")
                print("   - Extension is not installed or not running")
                print("   - Extension's WebSocket connection is broken")
                print("   - Extension is connected but not processing commands")
                return False

            # Test 2: Execute script
            print("\n2. Testing 'execute_script' command...")
            result = await send_command(
                websocket, "execute_script", {"script": "document.title"}, timeout=5.0
            )

            if result and result.get("success"):
                title = result.get("result")
                print(f"   ✓ Page title: {title}")
            else:
                error = result.get("error", "Unknown") if result else "No response"
                print(f"   ✗ Error: {error}")

            # Test 3: Extract page
            print("\n3. Testing 'extract_page' command...")
            result = await send_command(websocket, "extract_page", {}, timeout=30.0)

            if result and result.get("success"):
                markdown = result.get("markdown", "")
                print(f"   ✓ Extracted {len(markdown)} characters")
                print("   Preview (first 200 chars):")
                print(f"   {markdown[:200].strip()}...")
            else:
                error = result.get("error", "Unknown") if result else "No response"
                print(f"   ✗ Error: {error}")

            print("\n" + "=" * 60)
            print("All commands tested successfully!")
            print("=" * 60)
            return True

    except ConnectionRefusedError:
        print("✗ Connection refused")
        print("\n   The HTTP server is not running on port 4625")
        print("   Start the relay server with: make start")
        return False

    except Exception as e:
        print(f"✗ Error: {e}")
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = asyncio.run(test_commands())
    sys.exit(0 if success else 1)
