"""Claude.ai interaction commands via the Gobbler browser extension."""

from __future__ import annotations

import asyncio
import json
from typing import Annotated

import typer

from gobbler_cli.output import (
    console,
    print_error,
    print_info,
    print_table,
    print_warning,
)
from gobbler_cli.progress import ProgressTracker

app = typer.Typer(help="Interact with Claude.ai via Gobbler extension")

# Global state for --no-auto-start option
_auto_start_enabled = True


def set_auto_start(enabled: bool) -> None:
    """Set whether relay auto-start is enabled."""
    global _auto_start_enabled  # noqa: PLW0603
    _auto_start_enabled = enabled


@app.callback()
def claude_callback(
    no_auto_start: Annotated[
        bool,
        typer.Option(
            "--no-auto-start",
            help="Disable automatic relay server startup (for debugging)",
        ),
    ] = False,
) -> None:
    """Interact with Claude.ai via Gobbler extension."""
    set_auto_start(not no_auto_start)


# JavaScript snippets for Claude.ai interaction
# These use the injected window.gobblerClaude API when available, with fallbacks

# Check if page API is available
CHECK_API_JS = "typeof window.gobblerClaude !== 'undefined'"

# Ask using the page API (send message and wait for response)
ASK_JS = """
(async () => {
    if (typeof window.gobblerClaude === 'undefined') {
        return {success: false,
            error: "Gobbler Claude API not injected. Ensure the tab is in the Gobbler group."};
    }
    return await window.gobblerClaude.ask(%s, %d);
})()
"""

# Get conversation info using page API
GET_INFO_JS = """
(() => {
    if (typeof window.gobblerClaude !== 'undefined') {
        return window.gobblerClaude.getConversationInfo();
    }
    // Fallback
    const title = document.title || "Claude";
    const url = window.location.href;
    const conversationId = url.match(/\\/chat\\/([^/?]+)/)?.[1] || null;
    return { title, url, conversationId, isConversation: url.includes('/chat/') };
})()
"""

# Get last response using page API
GET_LAST_RESPONSE_JS = """
(async () => {
    if (typeof window.gobblerClaude !== 'undefined') {
        return await window.gobblerClaude.getLastResponse();
    }
    // Fallback: Claude uses data-is-streaming attribute
    const messages = document.querySelectorAll('[data-is-streaming]');
    if (messages.length === 0) return { success: false, error: 'No messages found' };
    const lastMsg = messages[messages.length - 1];
    const text = lastMsg.textContent?.trim() || '';
    return { success: true, response: text, totalMessages: messages.length };
})()
"""

# Get chat history using page API
GET_CHAT_HISTORY_JS = """
(async () => {
    if (typeof window.gobblerClaude !== 'undefined') {
        const result = await window.gobblerClaude.getChatContent();
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
    return { error: 'Gobbler Claude API not available' };
})()
"""


async def _get_claude_tabs() -> list[dict]:
    """Get list of Claude.ai tabs in the Gobbler group."""
    from gobbler_relay.client import list_tabs  # noqa: PLC0415

    result = await list_tabs(filter_type="claude")

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
    """List available Claude.ai tabs."""
    asyncio.run(_list_conversations())


async def _list_conversations() -> None:
    """Async implementation of list conversations."""
    ok, auto_started, msg = await _check_relay_and_extension()
    if auto_started:
        print_info("Relay server started automatically")
    if not ok:
        print_error(msg)
        raise typer.Exit(1)

    tabs = await _get_claude_tabs()

    if not tabs:
        print_info("No Claude.ai tabs found in Gobbler group")
        console.print("\nTo use Claude.ai with Gobbler:")
        console.print("  1. Open Claude.ai in your browser")
        console.print("  2. Move the tab to the 'Gobbler' tab group")
        return

    rows = [[str(tab["tab_id"]), tab["title"]] for tab in tabs]
    print_table(
        title="Claude.ai Tabs",
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
    """Get information about a Claude.ai conversation."""
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

    tabs = await _get_claude_tabs()
    if not tabs:
        print_error("No Claude.ai tabs found in Gobbler group")
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
    message: Annotated[str, typer.Argument(help="Message to send to Claude")],
    tab_id: Annotated[
        int | None,
        typer.Option("--tab", "-t", help="Specific tab ID"),
    ] = None,
    timeout: Annotated[
        int,
        typer.Option("--timeout", help="Response timeout in seconds"),
    ] = 150,  # 2.5 minutes default
) -> None:
    """Send a message to Claude.ai and get the response."""
    asyncio.run(_query(message, tab_id, timeout))


async def _query(message: str, tab_id: int | None, timeout: int) -> None:  # noqa: PLR0912
    """Async implementation of query."""
    from gobbler_relay.client import execute_script_in_tab  # noqa: PLC0415

    ok, auto_started, msg = await _check_relay_and_extension()
    if auto_started:
        print_info("Relay server started automatically")
    if not ok:
        print_error(msg)
        raise typer.Exit(1)

    tabs = await _get_claude_tabs()
    if not tabs:
        print_error("No Claude.ai tabs found in Gobbler group")
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

    with ProgressTracker("Waiting for Claude response"):
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
            response = data.get("response", "No response")
            console.print("[bold green]Response:[/bold green]\n")
            print(response)  # noqa: T201
            print()  # noqa: T201

            if data.get("partial"):
                print_warning("Response may be incomplete (timeout reached)")
                print_info("Use 'gobbler claude last' to check for complete response")
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
    """Get the last response from Claude.ai chat."""
    asyncio.run(_last(tab_id))


async def _last(tab_id: int | None) -> None:
    """Async implementation of last."""
    from gobbler_relay.client import execute_script_in_tab  # noqa: PLC0415

    ok, auto_started, msg = await _check_relay_and_extension()
    if auto_started:
        print_info("Relay server started automatically")
    if not ok:
        print_error(msg)
        raise typer.Exit(1)

    tabs = await _get_claude_tabs()
    if not tabs:
        print_error("No Claude.ai tabs found in Gobbler group")
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

        # Handle both old format (lastResponse) and new format (response)
        response_text = data.get("response") or data.get("lastResponse", "No response")
        if data.get("totalMessages"):
            console.print(f"[dim]Total messages:[/dim] {data.get('totalMessages')}\n")
        console.print("[bold]Last Response:[/bold]\n")
        print(response_text)  # noqa: T201
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
    """Get recent messages from Claude.ai chat history."""
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

    tabs = await _get_claude_tabs()
    if not tabs:
        print_error("No Claude.ai tabs found in Gobbler group")
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
