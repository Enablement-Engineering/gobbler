"""NotebookLM interaction commands via the Gobbler browser extension."""

from __future__ import annotations

import asyncio
import json
import re
from typing import Annotated, Any

import typer

from gobbler_cli.output import (
    console,
    print_error,
    print_info,
    print_table,
    print_warning,
)
from gobbler_cli.progress import ProgressTracker

app = typer.Typer(help="Interact with NotebookLM via Gobbler extension")

# Global state for --no-auto-start option
_auto_start_enabled = True


def set_auto_start(enabled: bool) -> None:
    """Set whether relay auto-start is enabled."""
    global _auto_start_enabled  # noqa: PLW0603
    _auto_start_enabled = enabled


@app.callback()
def notebooklm_callback(
    no_auto_start: Annotated[
        bool,
        typer.Option(
            "--no-auto-start",
            help="Disable automatic relay server startup (for debugging)",
        ),
    ] = False,
) -> None:
    """Interact with NotebookLM via Gobbler extension."""
    set_auto_start(not no_auto_start)


# JavaScript snippets for NotebookLM interaction
SEND_AND_WAIT_JS = """
(async () => {
    const maxWait = %d;  // milliseconds for response
    const query = %s;

    // Find textarea
    const textarea = document.querySelector('textarea[aria-label="Query box"]');
    if (!textarea) {
        return {success: false, error: "Could not find NotebookLM input textarea"};
    }

    // Get initial message count
    const initialCount = document.querySelectorAll('chat-message').length;

    // Clear, focus, and set value
    textarea.value = '';
    textarea.focus();
    textarea.click();
    await new Promise(r => setTimeout(r, 200));

    // Set value using native setter
    const setter = Object.getOwnPropertyDescriptor(
        window.HTMLTextAreaElement.prototype, 'value').set;
    setter.call(textarea, query);
    textarea.dispatchEvent(new Event('input', { bubbles: true }));
    await new Promise(r => setTimeout(r, 500));

    // Find and click send button
    const sendButton = document.querySelector('query-box form button');
    if (!sendButton) {
        return {success: false, error: "Could not find send button"};
    }
    if (sendButton.disabled) {
        return {success: false, error: "Send button disabled", textareaValue: textarea.value};
    }

    sendButton.click();

    // Wait for response with text stability check
    const startTime = Date.now();
    let lastText = '';
    let stableCount = 0;
    const STABLE_THRESHOLD = 3;  // Need 3 consecutive stable checks (3 seconds)

    while (Date.now() - startTime < maxWait) {
        await new Promise(r => setTimeout(r, 1000));

        const messages = document.querySelectorAll('chat-message');

        // Check if we have a new response (user message + assistant message)
        if (messages.length >= initialCount + 2) {
            const lastMsg = messages[messages.length - 1];
            const text = lastMsg?.innerText || '';

            // Skip if still showing loading text
            if (text.length < 50 && (text.includes('Finding') ||
                    text.includes('Searching') || text.includes('...'))) {
                stableCount = 0;
                lastText = '';
                continue;
            }

            // Check if text is stable (same as last check)
            if (text.length > 0 && text === lastText) {
                stableCount++;
                // If stable for 3 consecutive seconds, response is complete
                if (stableCount >= STABLE_THRESHOLD) {
                    return {
                        success: true,
                        response: text,
                        messageCount: messages.length,
                        waitTime: Date.now() - startTime
                    };
                }
            } else {
                // Text changed, reset stability counter
                lastText = text;
                stableCount = 1;  // Start at 1 since we have valid text
            }
        }
    }

    // Timeout reached - return whatever we have
    const finalMessages = document.querySelectorAll('chat-message');
    if (finalMessages.length > initialCount) {
        const text = finalMessages[finalMessages.length - 1]?.innerText || '';
        return {
            success: true,
            response: text,
            partial: true,
            waitTime: Date.now() - startTime
        };
    }

    return {success: false, error: "Timeout waiting for response"};
})()
"""

GET_INFO_JS = """
(() => {
    const title = document.title || "Unknown";
    const sources = document.querySelectorAll('.source-item, [data-source-id]').length;
    const chatMessages = document.querySelectorAll('.chat-message, .response-content').length;

    return {
        title: title,
        sourceCount: sources,
        messageCount: chatMessages,
        url: window.location.href
    };
})()
"""

GET_LAST_RESPONSE_JS = r"""
(() => {
    const messages = document.querySelectorAll('chat-message');
    if (messages.length === 0) return { error: 'No messages found' };

    const lastMsg = messages[messages.length - 1];
    const text = lastMsg?.innerText || '';

    // Clean up UI artifacts
    let clean = text.replace(/keep_pin\s*Save to note/g, '');
    clean = clean.replace(/copy_all|thumb_up|thumb_down/g, '');
    clean = clean.replace(/\n{3,}/g, '\n\n').trim();

    return {
        totalMessages: messages.length,
        lastResponse: clean
    };
})()
"""

GET_CHAT_HISTORY_JS = r"""
((count) => {
    const messages = document.querySelectorAll('chat-message');
    if (messages.length === 0) return { error: 'No messages found' };

    const numMessages = count || messages.length;
    const startIdx = Math.max(0, messages.length - numMessages);
    const selectedMessages = Array.from(messages).slice(startIdx);

    const history = selectedMessages.map((msg, idx) => {
        const text = msg?.innerText || '';

        // Clean up UI artifacts
        let clean = text.replace(/keep_pin\s*Save to note/g, '');
        clean = clean.replace(/copy_all|thumb_up|thumb_down/g, '');
        clean = clean.replace(/\n{3,}/g, '\n\n').trim();

        return {
            index: startIdx + idx,
            text: clean
        };
    });

    return {
        totalMessages: messages.length,
        returned: history.length,
        messages: history
    };
})(%s)
"""


def _clean_response(text: str) -> str:
    """Clean up NotebookLM UI artifacts from response text."""
    text = re.sub(r"keep_pin\s*Save to note", "", text)
    text = text.replace("copy_all", "").replace("thumb_up", "").replace("thumb_down", "")
    return re.sub(r"\n{3,}", "\n\n", text).strip()


async def _get_notebooklm_tabs() -> list[dict[str, Any]]:
    """Get list of NotebookLM tabs in the Gobbler group."""
    from gobbler_relay.client import list_tabs

    result = await list_tabs(filter_type="notebooklm")

    if not result.get("success"):
        return []

    tabs_list = result.get("tabs", [])
    return [{"tab_id": tab["tabId"], "title": tab["title"]} for tab in tabs_list]


async def _check_relay_and_extension() -> tuple[bool, bool, str]:
    """Check if relay is running and extension is connected.

    Returns:
        Tuple of (success, relay_was_auto_started, message)
    """
    from gobbler_relay.client import (
        check_connection,
        ensure_relay_running,
        is_relay_running,
    )

    relay_auto_started = False

    # Try to ensure relay is running (auto-start if enabled)
    if _auto_start_enabled:
        try:
            # Check if already running before we try to ensure
            was_running = await is_relay_running()
            await ensure_relay_running()
            if not was_running:
                relay_auto_started = True
        except RuntimeError as e:
            return False, False, f"Failed to start relay: {e}"
    # Auto-start disabled, just check if running
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
def list_notebooks() -> None:
    """List available NotebookLM tabs."""
    asyncio.run(_list_notebooks())


async def _list_notebooks() -> None:
    """Async implementation of list notebooks."""
    ok, auto_started, msg = await _check_relay_and_extension()
    if auto_started:
        print_info("Relay server started automatically")
    if not ok:
        print_error(msg)
        raise typer.Exit(1)

    tabs = await _get_notebooklm_tabs()

    if not tabs:
        print_info("No NotebookLM tabs found in Gobbler group")
        console.print("\nTo use NotebookLM with Gobbler:")
        console.print("  1. Open NotebookLM in your browser")
        console.print("  2. Move the tab to the 'Gobbler' tab group")
        return

    rows = [[str(tab["tab_id"]), tab["title"]] for tab in tabs]
    print_table(
        title="NotebookLM Tabs",
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
    """Get information about a NotebookLM notebook."""
    asyncio.run(_info(tab_id))


async def _info(tab_id: int | None) -> None:
    """Async implementation of info."""
    from gobbler_relay.client import execute_script_in_tab

    ok, auto_started, msg = await _check_relay_and_extension()
    if auto_started:
        print_info("Relay server started automatically")
    if not ok:
        print_error(msg)
        raise typer.Exit(1)

    tabs = await _get_notebooklm_tabs()
    if not tabs:
        print_error("No NotebookLM tabs found in Gobbler group")
        raise typer.Exit(1)

    # Select target tab
    if tab_id:
        target = next((t for t in tabs if t["tab_id"] == tab_id), None)
        if not target:
            print_error(f"Tab {tab_id} not found")
            for t in tabs:
                console.print(f"  [{t['tab_id']}] {t['title']}")
            raise typer.Exit(1)
        target_id = tab_id
    else:
        target_id = tabs[0]["tab_id"]

    result = await execute_script_in_tab(tab_id=target_id, script=GET_INFO_JS, timeout=30)

    if not result.get("success"):
        print_error(result.get("error", "Failed to get info"))
        raise typer.Exit(1)

    info_data = result.get("result", {})
    if isinstance(info_data, dict):
        console.print(f"\n[bold]Notebook:[/bold] {info_data.get('title', 'Unknown')}")
        console.print(f"[bold]Sources:[/bold] {info_data.get('sourceCount', 0)}")
        console.print(f"[bold]Messages:[/bold] {info_data.get('messageCount', 0)}")
        console.print(f"[bold]URL:[/bold] {info_data.get('url', 'N/A')}")
    else:
        console.print(str(info_data))


@app.command()
def query(
    message: Annotated[str, typer.Argument(help="Query to send to NotebookLM")],
    tab_id: Annotated[
        int | None,
        typer.Option("--tab", "-t", help="Specific tab ID"),
    ] = None,
    timeout: Annotated[
        int,
        typer.Option("--timeout", help="Response timeout in seconds"),
    ] = 150,  # 2.5 minutes default
) -> None:
    """Send a query to NotebookLM and get the response."""
    asyncio.run(_query(message, tab_id, timeout))


async def _query(message: str, tab_id: int | None, timeout: int) -> None:  # noqa: PLR0912
    """Async implementation of query."""
    from gobbler_relay.client import execute_script_in_tab

    ok, auto_started, msg = await _check_relay_and_extension()
    if auto_started:
        print_info("Relay server started automatically")
    if not ok:
        print_error(msg)
        raise typer.Exit(1)

    tabs = await _get_notebooklm_tabs()
    if not tabs:
        print_error("No NotebookLM tabs found in Gobbler group")
        raise typer.Exit(1)

    # Select target tab
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
    console.print(f"[dim]Query:[/dim] {message}\n")

    # Build and execute script
    script = SEND_AND_WAIT_JS % (timeout * 1000, json.dumps(message))

    with ProgressTracker("Waiting for NotebookLM response"):
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
            console.print(data)
            return

    if isinstance(data, dict):
        if data.get("success"):
            response = _clean_response(data.get("response", "No response"))

            # Print full response without truncation
            console.print("[bold green]Response:[/bold green]\n")
            # Use print() for raw output to avoid any rich formatting issues
            print(response)  # noqa: T201
            print()  # Blank line after response  # noqa: T201

            if data.get("partial"):
                print_warning("Response may be incomplete (timeout reached)")
                print_info("Use 'gobbler notebooklm last' to check for complete response")
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
    """Get the last response from NotebookLM chat."""
    asyncio.run(_last(tab_id))


async def _last(tab_id: int | None) -> None:
    """Async implementation of last."""
    from gobbler_relay.client import execute_script_in_tab

    ok, auto_started, msg = await _check_relay_and_extension()
    if auto_started:
        print_info("Relay server started automatically")
    if not ok:
        print_error(msg)
        raise typer.Exit(1)

    tabs = await _get_notebooklm_tabs()
    if not tabs:
        print_error("No NotebookLM tabs found in Gobbler group")
        raise typer.Exit(1)

    # Select target tab
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
            console.print(data)
            return

    if isinstance(data, dict):
        if data.get("error"):
            print_error(data["error"])
            raise typer.Exit(1)

        console.print(f"[dim]Total messages:[/dim] {data.get('totalMessages', 'unknown')}\n")
        console.print("[bold]Last Response:[/bold]\n")
        console.print(data.get("lastResponse", "No response"))
    else:
        console.print(str(data))


@app.command()
def history(
    tab_id: Annotated[
        int | None,
        typer.Option("--tab", "-t", help="Specific tab ID"),
    ] = None,
    count: Annotated[
        int,
        typer.Option("--count", "-n", help="Number of messages to show"),
    ] = 5,
    show_all: Annotated[
        bool,
        typer.Option("--all", "-a", help="Show all messages"),
    ] = False,
) -> None:
    """Get recent messages from NotebookLM chat history."""
    asyncio.run(_history(tab_id, count, show_all))


async def _history(tab_id: int | None, count: int, show_all: bool) -> None:
    """Async implementation of history."""
    from gobbler_relay.client import execute_script_in_tab

    ok, auto_started, msg = await _check_relay_and_extension()
    if auto_started:
        print_info("Relay server started automatically")
    if not ok:
        print_error(msg)
        raise typer.Exit(1)

    tabs = await _get_notebooklm_tabs()
    if not tabs:
        print_error("No NotebookLM tabs found in Gobbler group")
        raise typer.Exit(1)

    # Select target tab
    target_id = tab_id if tab_id else tabs[0]["tab_id"]
    if tab_id and not any(t["tab_id"] == tab_id for t in tabs):
        print_error(f"Tab {tab_id} not found")
        raise typer.Exit(1)

    # Build script
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
            console.print(data)
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
            idx = msg.get("index", 0)
            text = msg.get("text", "")
            console.print(f"\n[bold]Message {idx + 1}[/bold]\n")
            console.print(text)
            console.print("\n" + "-" * 60)
    else:
        console.print(str(data))
