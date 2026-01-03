#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
# ruff: noqa: T201, PLR0915, PLC0415
"""
Test the browser tools by directly calling the http_server functions.

This simulates what the MCP tools do internally.
"""

import asyncio
import sys
from pathlib import Path

# Add src to path so we can import gobbler_mcp
sys.path.insert(0, str(Path(__file__).parent / "../../../src"))


async def test_browser_tools():
    """Test browser extension tools."""
    from gobbler_mcp.http_server import send_command_to_extension, websocket_connections

    print("=" * 60)
    print("Testing Gobbler Browser Extension Tools")
    print("=" * 60)

    # Test 1: Check connection
    print("\n1. Checking WebSocket connections...")
    print(f"   Active connections: {len(websocket_connections)}")

    if not websocket_connections:
        print("   ✗ No browser extension connected")
        print("\n   To connect:")
        print("   1. Install the Gobbler extension in Chrome/Arc")
        print("   2. Navigate to any webpage")
        print("   3. The extension will auto-connect")
        return False

    print("   ✓ Browser extension is connected")

    # Test 2: List tabs
    print("\n2. Listing tabs in Gobbler group...")
    try:
        result = await send_command_to_extension(
            command="list_gobbler_tabs", params={}, timeout=10.0
        )

        if result.get("success"):
            tabs = result.get("tabs", [])
            print(f"   ✓ Found {len(tabs)} tab(s)")
            for tab in tabs:
                active = "*" if tab.get("isActive") else " "
                print(f"     {active} [{tab.get('tabId')}] {tab.get('title', 'Unknown')[:50]}")
                print(f"        {tab.get('url', '')[:70]}")
        else:
            error = result.get("error", "Unknown error")
            print(f"   ✗ Error: {error}")
            return False

    except Exception as e:
        print(f"   ✗ Error: {e}")
        return False

    # Test 3: Extract current page (if there's an active tab)
    print("\n3. Extracting current page content...")
    try:
        result = await send_command_to_extension(command="extract_page", params={}, timeout=30.0)

        if result.get("success"):
            markdown = result.get("markdown", "")
            print(f"   ✓ Extracted {len(markdown)} characters")
            print("   Preview (first 200 chars):")
            print(f"   {markdown[:200]}...")
        else:
            error = result.get("error", "Unknown error")
            print(f"   ✗ Error: {error}")

    except Exception as e:
        print(f"   ✗ Error: {e}")

    # Test 4: Execute simple script
    print("\n4. Executing JavaScript in active tab...")
    try:
        result = await send_command_to_extension(
            command="execute_script", params={"script": "document.title"}, timeout=10.0
        )

        if result.get("success"):
            title = result.get("result")
            print(f"   ✓ Page title: {title}")
        else:
            error = result.get("error", "Unknown error")
            print(f"   ✗ Error: {error}")

    except Exception as e:
        print(f"   ✗ Error: {e}")

    print("\n" + "=" * 60)
    print("Testing complete!")
    print("=" * 60)
    return True


if __name__ == "__main__":
    success = asyncio.run(test_browser_tools())
    sys.exit(0 if success else 1)
