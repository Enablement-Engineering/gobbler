"""Gemini interaction commands via the Gobbler browser extension."""

from __future__ import annotations

import asyncio
import base64
import json
from pathlib import Path
from typing import Annotated

import typer

from gobbler_cli.output import (
    console,
    print_error,
    print_info,
    print_success,
    print_table,
    print_warning,
)
from gobbler_cli.progress import ProgressTracker

app = typer.Typer(help="Interact with Google Gemini via Gobbler extension")

# Global state for --no-auto-start option
_auto_start_enabled = True


def set_auto_start(enabled: bool) -> None:
    """Set whether relay auto-start is enabled."""
    global _auto_start_enabled  # noqa: PLW0603
    _auto_start_enabled = enabled


@app.callback()
def gemini_callback(
    no_auto_start: Annotated[
        bool,
        typer.Option(
            "--no-auto-start",
            help="Disable automatic relay server startup (for debugging)",
        ),
    ] = False,
) -> None:
    """Interact with Google Gemini via Gobbler extension."""
    set_auto_start(not no_auto_start)


# JavaScript snippets for Gemini interaction
# These use the injected window.gobblerGemini API when available, with fallbacks

# Check if page API is available
CHECK_API_JS = "typeof window.gobblerGemini !== 'undefined'"

# Ask using the page API (send message and wait for response)
ASK_JS = """
(async () => {
    if (typeof window.gobblerGemini === 'undefined') {
        return {success: false,
            error: "Gobbler Gemini API not injected. Ensure the tab is in the Gobbler group."};
    }
    return await window.gobblerGemini.ask(%s, %d);
})()
"""

# Get conversation info using page API
GET_INFO_JS = """
(() => {
    if (typeof window.gobblerGemini !== 'undefined') {
        return window.gobblerGemini.getConversationInfo();
    }
    // Fallback
    const title = document.title || "Gemini";
    const url = window.location.href;
    const conversationId = url.match(/\\/app\\/([^/?]+)/)?.[1] || null;
    return { title, url, conversationId, isConversation: url.includes('/app/') };
})()
"""

# Get last response using page API
GET_LAST_RESPONSE_JS = """
(async () => {
    if (typeof window.gobblerGemini !== 'undefined') {
        return await window.gobblerGemini.getLastResponse();
    }
    // Fallback
    const messages = document.querySelectorAll('model-response message-content');
    if (messages.length === 0) return { success: false, error: 'No messages found' };
    const lastMsg = messages[messages.length - 1];
    const textEl = lastMsg.querySelector('.markdown') || lastMsg;
    const text = textEl.textContent?.trim() || '';
    return { success: true, response: text, totalMessages: messages.length };
})()
"""

# Get chat history using page API
GET_CHAT_HISTORY_JS = """
(async () => {
    if (typeof window.gobblerGemini !== 'undefined') {
        const result = await window.gobblerGemini.getChatContent();
        if (result.success) {
            const count = %s;
            const messages = result.messages || [];
            const numMessages = count || messages.length;
            const startIdx = Math.max(0, messages.length - numMessages);
            const selected = messages.slice(startIdx);
            return {
                totalMessages: messages.length,
                returned: selected.length,
                messages: selected.map((m, i) => (
                    {index: startIdx + i, role: m.role, text: m.content}))
            };
        }
        return result;
    }
    return { error: 'Gobbler Gemini API not available' };
})()
"""


async def _get_gemini_tabs() -> list[dict]:
    """Get list of Gemini tabs in the Gobbler group."""
    from gobbler_relay.client import list_tabs  # noqa: PLC0415

    result = await list_tabs(filter_type="gemini")

    if not result.get("success"):
        return []

    tabs_list = result.get("tabs", [])
    return [{"tab_id": tab["tabId"], "title": tab["title"]} for tab in tabs_list]


async def _check_relay_and_extension() -> tuple[bool, bool, str]:
    """Check if relay is running and extension is connected."""
    from gobbler_relay.client import (  # noqa: PLC0415
        check_connection,
        ensure_relay_running,
        is_relay_running,
    )

    relay_auto_started = False

    if _auto_start_enabled:
        try:
            was_running = await is_relay_running()
            await ensure_relay_running()
            if not was_running:
                relay_auto_started = True
        except RuntimeError as e:
            return False, False, f"Failed to start relay: {e}"
    elif not await is_relay_running():
        return False, False, "Relay server is not running. Start it with: gobbler relay start"

    status = await check_connection()
    if status.get("status") == "error":
        return False, relay_auto_started, status.get("message", "Unknown error")

    connections = status.get("websocket_connections", 0)
    if connections == 0:
        return (
            False,
            relay_auto_started,
            "No browser extension connected. Install and connect the Gobbler extension.",
        )

    return True, relay_auto_started, f"{connections} extension(s) connected"


@app.command("list")
def list_conversations() -> None:
    """List available Gemini tabs."""
    asyncio.run(_list_conversations())


async def _list_conversations() -> None:
    """Async implementation of list conversations."""
    ok, auto_started, msg = await _check_relay_and_extension()
    if auto_started:
        print_info("Relay server started automatically")
    if not ok:
        print_error(msg)
        raise typer.Exit(1)

    tabs = await _get_gemini_tabs()

    if not tabs:
        print_info("No Gemini tabs found in Gobbler group")
        console.print("\nTo use Gemini with Gobbler:")
        console.print("  1. Open Gemini in your browser")
        console.print("  2. Move the tab to the 'Gobbler' tab group")
        return

    rows = [[str(tab["tab_id"]), tab["title"]] for tab in tabs]
    print_table(
        title="Gemini Tabs",
        columns=["Tab ID", "Title"],
        rows=rows,
    )


@app.command()
def info(
    tab_id: Annotated[
        int | None,
        typer.Option("--tab", "-t", help="Specific tab ID"),
    ] = None,
) -> None:
    """Get information about a Gemini conversation."""
    asyncio.run(_info(tab_id))


async def _info(tab_id: int | None) -> None:
    """Async implementation of info."""
    from gobbler_relay.client import execute_script_in_tab  # noqa: PLC0415

    ok, auto_started, msg = await _check_relay_and_extension()
    if auto_started:
        print_info("Relay server started automatically")
    if not ok:
        print_error(msg)
        raise typer.Exit(1)

    tabs = await _get_gemini_tabs()
    if not tabs:
        print_error("No Gemini tabs found in Gobbler group")
        raise typer.Exit(1)

    target_id = tab_id if tab_id else tabs[0]["tab_id"]
    if tab_id and not any(t["tab_id"] == tab_id for t in tabs):
        print_error(f"Tab {tab_id} not found")
        raise typer.Exit(1)

    result = await execute_script_in_tab(tab_id=target_id, script=GET_INFO_JS, timeout=30)

    if not result.get("success"):
        print_error(result.get("error", "Failed to get info"))
        raise typer.Exit(1)

    info_data = result.get("result", {})
    if isinstance(info_data, dict):
        console.print(f"\n[bold]Conversation:[/bold] {info_data.get('title', 'Unknown')}")
        console.print(f"[bold]Conversation ID:[/bold] {info_data.get('conversationId', 'N/A')}")
        console.print(f"[bold]User Messages:[/bold] {info_data.get('userMessages', 0)}")
        console.print(f"[bold]Assistant Messages:[/bold] {info_data.get('assistantMessages', 0)}")
        console.print(f"[bold]URL:[/bold] {info_data.get('url', 'N/A')}")
    else:
        console.print(str(info_data))


@app.command()
def query(
    message: Annotated[str, typer.Argument(help="Message to send to Gemini")],
    tab_id: Annotated[
        int | None,
        typer.Option("--tab", "-t", help="Specific tab ID"),
    ] = None,
    timeout: Annotated[
        int,
        typer.Option("--timeout", help="Response timeout in seconds"),
    ] = 150,  # 2.5 minutes default
) -> None:
    """Send a message to Gemini and get the response."""
    asyncio.run(_query(message, tab_id, timeout))


async def _query(  # noqa: C901, PLR0912, PLR0915
    message: str, tab_id: int | None, timeout: int
) -> None:
    """Async implementation of query."""
    from gobbler_relay.client import execute_script_in_tab  # noqa: PLC0415

    ok, auto_started, msg = await _check_relay_and_extension()
    if auto_started:
        print_info("Relay server started automatically")
    if not ok:
        print_error(msg)
        raise typer.Exit(1)

    tabs = await _get_gemini_tabs()
    if not tabs:
        print_error("No Gemini tabs found in Gobbler group")
        raise typer.Exit(1)

    if tab_id:
        target = next((t for t in tabs if t["tab_id"] == tab_id), None)
        if not target:
            print_error(f"Tab {tab_id} not found")
            raise typer.Exit(1)
        target_id = tab_id
        tab_title = target["title"]
    else:
        target_id = tabs[0]["tab_id"]
        tab_title = tabs[0]["title"]

    console.print(f"[dim]Sending to:[/dim] {tab_title}")
    console.print(f"[dim]Message:[/dim] {message}\n")

    script = ASK_JS % (json.dumps(message), timeout * 1000)

    with ProgressTracker("Waiting for Gemini response"):
        result = await execute_script_in_tab(
            tab_id=target_id, script=script, timeout=float(timeout + 15)
        )

    if not result.get("success"):
        print_error(result.get("error", "Script execution failed"))
        raise typer.Exit(1)

    data = result.get("result", {})
    if isinstance(data, str):
        try:
            data = json.loads(data)
        except json.JSONDecodeError:
            print(data)  # noqa: T201
            return

    if isinstance(data, dict):
        if data.get("success"):
            response = data.get("response", "")
            images = data.get("images", [])
            has_images = data.get("hasImages", False)

            if response:
                console.print("[bold green]Response:[/bold green]\n")
                print(response)  # noqa: T201
                print()  # noqa: T201

            if has_images and images:
                console.print(f"[bold cyan]Images Generated:[/bold cyan] {len(images)}\n")
                for i, img_url in enumerate(images, 1):
                    console.print(f"  [dim]Image {i}:[/dim] {img_url[:80]}...")
                print()  # noqa: T201
                print_info("Use 'gobbler gemini download' to save images")

            if not response and not has_images:
                print("No response")  # noqa: T201

            if data.get("partial"):
                print_warning("Response may be incomplete (timeout reached)")
                print_info("Use 'gobbler gemini last' to check for complete response")
        else:
            print_error(data.get("error", "Unknown error"))
            raise typer.Exit(1)
    else:
        print(str(data))  # noqa: T201


@app.command()
def last(
    tab_id: Annotated[
        int | None,
        typer.Option("--tab", "-t", help="Specific tab ID"),
    ] = None,
) -> None:
    """Get the last response from Gemini chat."""
    asyncio.run(_last(tab_id))


async def _last(tab_id: int | None) -> None:  # noqa: C901, PLR0912
    """Async implementation of last."""
    from gobbler_relay.client import execute_script_in_tab  # noqa: PLC0415

    ok, auto_started, msg = await _check_relay_and_extension()
    if auto_started:
        print_info("Relay server started automatically")
    if not ok:
        print_error(msg)
        raise typer.Exit(1)

    tabs = await _get_gemini_tabs()
    if not tabs:
        print_error("No Gemini tabs found in Gobbler group")
        raise typer.Exit(1)

    target_id = tab_id if tab_id else tabs[0]["tab_id"]
    if tab_id and not any(t["tab_id"] == tab_id for t in tabs):
        print_error(f"Tab {tab_id} not found")
        raise typer.Exit(1)

    result = await execute_script_in_tab(tab_id=target_id, script=GET_LAST_RESPONSE_JS, timeout=10)

    if not result.get("success"):
        print_error(result.get("error", "Failed to get last response"))
        raise typer.Exit(1)

    data = result.get("result", {})
    if isinstance(data, str):
        try:
            data = json.loads(data)
        except json.JSONDecodeError:
            print(data)  # noqa: T201
            return

    if isinstance(data, dict):
        if not data.get("success", True):
            print_error(data.get("error", "Unknown error"))
            raise typer.Exit(1)

        response_text = data.get("response") or data.get("lastResponse", "")
        images = data.get("images", [])
        has_images = data.get("hasImages", False)

        if data.get("totalMessages"):
            console.print(f"[dim]Total messages:[/dim] {data.get('totalMessages')}\n")

        if response_text:
            console.print("[bold]Last Response:[/bold]\n")
            print(response_text)  # noqa: T201

        if has_images and images:
            console.print(f"\n[bold cyan]Images:[/bold cyan] {len(images)}\n")
            for i, img_url in enumerate(images, 1):
                console.print(f"  [dim]Image {i}:[/dim] {img_url[:80]}...")
            print()  # noqa: T201
            print_info("Use 'gobbler gemini download' to save images")

        if not response_text and not has_images:
            print("No response")  # noqa: T201
    else:
        print(str(data))  # noqa: T201


@app.command()
def history(
    tab_id: Annotated[
        int | None,
        typer.Option("--tab", "-t", help="Specific tab ID"),
    ] = None,
    count: Annotated[
        int,
        typer.Option("--count", "-n", help="Number of messages to show"),
    ] = 10,
    show_all: Annotated[
        bool,
        typer.Option("--all", "-a", help="Show all messages"),
    ] = False,
) -> None:
    """Get recent messages from Gemini chat history."""
    asyncio.run(_history(tab_id, count, show_all))


async def _history(tab_id: int | None, count: int, show_all: bool) -> None:
    """Async implementation of history."""
    from gobbler_relay.client import execute_script_in_tab  # noqa: PLC0415

    ok, auto_started, msg = await _check_relay_and_extension()
    if auto_started:
        print_info("Relay server started automatically")
    if not ok:
        print_error(msg)
        raise typer.Exit(1)

    tabs = await _get_gemini_tabs()
    if not tabs:
        print_error("No Gemini tabs found in Gobbler group")
        raise typer.Exit(1)

    target_id = tab_id if tab_id else tabs[0]["tab_id"]
    if tab_id and not any(t["tab_id"] == tab_id for t in tabs):
        print_error(f"Tab {tab_id} not found")
        raise typer.Exit(1)

    message_count = "null" if show_all else str(count)
    script = GET_CHAT_HISTORY_JS % message_count

    result = await execute_script_in_tab(tab_id=target_id, script=script, timeout=10)

    if not result.get("success"):
        print_error(result.get("error", "Failed to get history"))
        raise typer.Exit(1)

    data = result.get("result", {})
    if isinstance(data, str):
        try:
            data = json.loads(data)
        except json.JSONDecodeError:
            print(data)  # noqa: T201
            return

    if isinstance(data, dict):
        if data.get("error"):
            print_error(data["error"])
            raise typer.Exit(1)

        total = data.get("totalMessages", 0)
        returned = data.get("returned", 0)
        messages = data.get("messages", [])

        console.print(f"[dim]Total messages: {total} | Showing: {returned}[/dim]\n")
        console.print("=" * 60)

        for msg in messages:
            role = msg.get("role", "unknown")
            text = msg.get("text", "")
            role_color = "cyan" if role == "user" else "green"
            console.print(f"\n[bold {role_color}]{role.upper()}[/bold {role_color}]\n")
            print(text)  # noqa: T201
            console.print("\n" + "-" * 60)
    else:
        print(str(data))  # noqa: T201


@app.command()
def download(
    output_dir: Annotated[
        str | None,
        typer.Option("--output", "-o", help="Output directory for images"),
    ] = None,
    tab_id: Annotated[
        int | None,
        typer.Option("--tab", "-t", help="Specific tab ID"),
    ] = None,
) -> None:
    """Download images from the last Gemini response."""
    asyncio.run(_download(output_dir, tab_id))


async def _download(  # noqa: C901, PLR0912, PLR0915
    output_dir: str | None, tab_id: int | None
) -> None:
    """Async implementation of download."""
    from gobbler_relay.client import execute_script_in_tab, send_command  # noqa: PLC0415

    ok, auto_started, msg = await _check_relay_and_extension()
    if auto_started:
        print_info("Relay server started automatically")
    if not ok:
        print_error(msg)
        raise typer.Exit(1)

    tabs = await _get_gemini_tabs()
    if not tabs:
        print_error("No Gemini tabs found in Gobbler group")
        raise typer.Exit(1)

    target_id = tab_id if tab_id else tabs[0]["tab_id"]
    if tab_id and not any(t["tab_id"] == tab_id for t in tabs):
        print_error(f"Tab {tab_id} not found")
        raise typer.Exit(1)

    # Get last response with images
    result = await execute_script_in_tab(tab_id=target_id, script=GET_LAST_RESPONSE_JS, timeout=10)

    if not result.get("success"):
        print_error(result.get("error", "Failed to get last response"))
        raise typer.Exit(1)

    data = result.get("result", {})
    images = data.get("images", [])

    if not images:
        print_info("No images found in last response")
        return

    console.print(f"[bold]Found {len(images)} image(s)[/bold]\n")

    # Determine output directory
    out_path = Path(output_dir) if output_dir else Path.cwd()
    out_path.mkdir(parents=True, exist_ok=True)

    for i, img_url in enumerate(images, 1):
        console.print(f"[dim]Downloading image {i}...[/dim]")

        # Open image in new tab
        open_result = await send_command("open_tabs", {"urls": [img_url]})
        if not open_result.get("success"):
            print_warning(f"Failed to open image {i}")
            continue

        new_tab_id = open_result.get("tabs", [{}])[0].get("id")
        if not new_tab_id:
            print_warning(f"Failed to get tab ID for image {i}")
            continue

        # Wait for image to load
        await asyncio.sleep(2)

        # Extract image as base64 from the new tab
        extract_script = """
        (async () => {
            const img = document.querySelector('img');
            if (!img) return {error: 'No image found'};

            // Wait for image to load
            if (!img.complete) {
                await new Promise(resolve => {
                    img.onload = resolve;
                    img.onerror = resolve;
                });
            }

            const canvas = document.createElement('canvas');
            canvas.width = img.naturalWidth;
            canvas.height = img.naturalHeight;
            const ctx = canvas.getContext('2d');
            ctx.drawImage(img, 0, 0);

            try {
                const dataUrl = canvas.toDataURL('image/png');
                return {
                    success: true,
                    dataUrl: dataUrl,
                    width: img.naturalWidth,
                    height: img.naturalHeight
                };
            } catch (e) {
                return {error: 'Failed to extract image: ' + e.message};
            }
        })()
        """

        extract_result = await execute_script_in_tab(
            tab_id=new_tab_id, script=extract_script, timeout=120
        )

        if not extract_result.get("success"):
            print_warning(f"Failed to extract image {i}: {extract_result.get('error')}")
            continue

        img_data = extract_result.get("result", {})
        if img_data.get("error"):
            print_warning(f"Failed to extract image {i}: {img_data.get('error')}")
            continue

        data_url = img_data.get("dataUrl", "")
        if not data_url.startswith("data:image"):
            print_warning(f"Invalid image data for image {i}")
            continue

        # Decode base64 and save
        try:
            # Remove data URL prefix
            base64_data = data_url.split(",", 1)[1]
            image_bytes = base64.b64decode(base64_data)

            # Save to file
            filename = f"gemini_image_{i}.png"
            filepath = out_path / filename
            filepath.write_bytes(image_bytes)

            width = img_data.get("width", "?")
            height = img_data.get("height", "?")
            print_success(f"Saved: {filepath} ({width}x{height})")
        except Exception as e:
            print_warning(f"Failed to save image {i}: {e}")

    console.print("\n[bold green]Download complete![/bold green]")
