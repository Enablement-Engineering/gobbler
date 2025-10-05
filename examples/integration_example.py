#!/usr/bin/env python3
"""
Integration Example: Using Browser Extension with Gobbler MCP

This example demonstrates a complete workflow using the bidirectional
communication between Gobbler MCP and the browser extension.

Prerequisites:
1. Gobbler MCP server running (uv run gobbler-mcp)
2. Browser extension installed and connected
3. Browser open with a tab active
"""

import asyncio
import sys
from pathlib import Path

# Add src to path for direct import
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from gobbler_mcp.http_server import send_command_to_extension, websocket_connections


async def research_workflow():
    """
    Example: Research a topic by navigating to multiple sources and extracting content.
    """
    print("=" * 70)
    print("Integration Example: Research Workflow")
    print("=" * 70)

    # 1. Check connection
    print("\n[1/5] Checking browser extension connection...")
    if not websocket_connections:
        print("❌ No browser extension connected!")
        print("Please install and open the browser extension.")
        return

    print(f"✅ Extension connected ({len(websocket_connections)} connection(s))")

    # 2. Get current page info
    print("\n[2/5] Getting current page information...")
    try:
        response = await send_command_to_extension(
            command="get_page_info",
            params={},
            timeout=10.0
        )

        if response.get("success"):
            info = response.get("info", {})
            print(f"✅ Current page:")
            print(f"   URL: {info.get('url')}")
            print(f"   Title: {info.get('title')}")
            print(f"   Links: {info.get('links_count')}")
        else:
            print(f"❌ Failed: {response.get('error')}")
            return
    except Exception as e:
        print(f"❌ Error: {e}")
        return

    # 3. Navigate to Python documentation
    print("\n[3/5] Navigating to Python documentation...")
    try:
        response = await send_command_to_extension(
            command="navigate",
            params={
                "url": "https://docs.python.org/3/tutorial/",
                "wait_for_load": True
            },
            timeout=30.0
        )

        if response.get("success"):
            print("✅ Navigation successful")
        else:
            print(f"❌ Navigation failed: {response.get('error')}")
            return
    except Exception as e:
        print(f"❌ Error: {e}")
        return

    # 4. Extract table of contents using JavaScript
    print("\n[4/5] Extracting table of contents...")
    try:
        response = await send_command_to_extension(
            command="execute_script",
            params={
                "script": """
                    Array.from(document.querySelectorAll('.toctree-l1 > a')).map(a => ({
                        title: a.textContent.trim(),
                        url: a.href
                    }))
                """
            },
            timeout=10.0
        )

        if response.get("success"):
            import json
            toc = response.get("result", [])
            print(f"✅ Found {len(toc)} sections:")
            for item in toc[:5]:  # Show first 5
                title = item.get("title", "")
                print(f"   • {title}")
            if len(toc) > 5:
                print(f"   ... and {len(toc) - 5} more")
        else:
            print(f"❌ Script failed: {response.get('error')}")
    except Exception as e:
        print(f"❌ Error: {e}")

    # 5. Extract page content as markdown
    print("\n[5/5] Extracting page content...")
    try:
        response = await send_command_to_extension(
            command="extract_page",
            params={
                "selector": "#the-python-tutorial"  # Extract just the main content
            },
            timeout=15.0
        )

        if response.get("success"):
            markdown = response.get("markdown", "")
            print(f"✅ Content extracted")
            print(f"   Markdown length: {len(markdown)} characters")
            print(f"\n   Preview:")
            print("   " + "-" * 60)
            # Show first 300 characters
            preview = markdown[:300].replace("\n", "\n   ")
            print(f"   {preview}...")
            print("   " + "-" * 60)

            # Optionally save to file
            output_file = Path.home() / "Downloads" / "python_tutorial.md"
            output_file.write_text(markdown)
            print(f"\n   📄 Saved to: {output_file}")
        else:
            print(f"❌ Extraction failed: {response.get('error')}")
    except Exception as e:
        print(f"❌ Error: {e}")

    print("\n" + "=" * 70)
    print("Workflow Complete!")
    print("=" * 70)


async def interactive_demo():
    """
    Interactive demo showing various browser commands.
    """
    print("=" * 70)
    print("Interactive Browser Control Demo")
    print("=" * 70)

    # Check connection
    if not websocket_connections:
        print("\n❌ No browser extension connected!")
        print("Please install and open the browser extension.")
        return

    print(f"\n✅ Extension connected!")

    while True:
        print("\n" + "-" * 70)
        print("Available commands:")
        print("  1. Get current page info")
        print("  2. Navigate to URL")
        print("  3. Execute JavaScript")
        print("  4. Extract page content")
        print("  5. Exit")
        print("-" * 70)

        choice = input("\nSelect command (1-5): ").strip()

        if choice == "1":
            # Get page info
            response = await send_command_to_extension(
                command="get_page_info",
                params={},
                timeout=10.0
            )
            if response.get("success"):
                import json
                print("\n" + json.dumps(response.get("info", {}), indent=2))

        elif choice == "2":
            # Navigate
            url = input("Enter URL: ").strip()
            if url:
                response = await send_command_to_extension(
                    command="navigate",
                    params={"url": url, "wait_for_load": True},
                    timeout=30.0
                )
                if response.get("success"):
                    print(f"\n✅ Navigated to {url}")
                else:
                    print(f"\n❌ Error: {response.get('error')}")

        elif choice == "3":
            # Execute script
            print("\nEnter JavaScript (single line):")
            script = input().strip()
            if script:
                response = await send_command_to_extension(
                    command="execute_script",
                    params={"script": script},
                    timeout=10.0
                )
                if response.get("success"):
                    import json
                    result = response.get("result")
                    if isinstance(result, (dict, list)):
                        print("\n" + json.dumps(result, indent=2))
                    else:
                        print(f"\nResult: {result}")
                else:
                    print(f"\n❌ Error: {response.get('error')}")

        elif choice == "4":
            # Extract page
            selector = input("Enter CSS selector (or press Enter for entire page): ").strip()
            params = {"selector": selector} if selector else {}

            response = await send_command_to_extension(
                command="extract_page",
                params=params,
                timeout=15.0
            )
            if response.get("success"):
                markdown = response.get("markdown", "")
                print(f"\n✅ Extracted {len(markdown)} characters")
                print("\nPreview:")
                print(markdown[:500] + "...")
            else:
                print(f"\n❌ Error: {response.get('error')}")

        elif choice == "5":
            print("\nGoodbye!")
            break

        else:
            print("\n❌ Invalid choice")


async def main():
    """Main entry point."""
    import sys

    print("\nGobbler MCP - Browser Extension Integration Examples")
    print("\nAvailable demos:")
    print("  1. Research workflow (automated)")
    print("  2. Interactive demo (manual)")

    choice = input("\nSelect demo (1-2): ").strip()

    if choice == "1":
        await research_workflow()
    elif choice == "2":
        await interactive_demo()
    else:
        print("\n❌ Invalid choice")


if __name__ == "__main__":
    print("\n" + "=" * 70)
    print("⚠️  Prerequisites:")
    print("  1. Gobbler MCP server must be running: uv run gobbler-mcp")
    print("  2. Browser extension must be installed and connected")
    print("  3. A browser tab must be open")
    print("=" * 70)

    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\nInterrupted by user")
    except Exception as e:
        print(f"\n\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
