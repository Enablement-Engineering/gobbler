"""Claude.ai interaction commands via the Gobbler browser extension."""

from __future__ import annotations

import asyncio
import json
import re
from typing import Optional

import typer
from typing_extensions import Annotated

from gobbler_cli.output import (
    console,
    print_error,
    print_info,
    print_success,
    print_table,
    print_warning,
)
from gobbler_cli.progress import ProgressTracker

app = typer.Typer(help="Interact with Claude.ai via Gobbler extension")

# Global state for --no-auto-start option
_auto_start_enabled = True


def set_auto_start(enabled: bool) -> None:
    """Set whether relay auto-start is enabled."""
    global _auto_start_enabled
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
SEND_AND_WAIT_JS = """
(async () => {
    const maxWait = %d;  // milliseconds for response
    const query = %s;

    // Find input - Claude uses contenteditable div with ProseMirror
    const inputSelectors = [
        'div[contenteditable="true"].ProseMirror',
        'div[contenteditable="true"][data-placeholder]',
        'div.ProseMirror[contenteditable="true"]',
        'div[contenteditable="true"]',
        'textarea[placeholder*="Reply"]'
    ];
    
    let input = null;
    for (const sel of inputSelectors) {
        input = document.querySelector(sel);
        if (input) break;
    }
    
    if (!input) {
        return {success: false, error: "Could not find Claude input field"};
    }

    // Clear, focus, and set value
    input.focus();
    
    if (input.getAttribute('contenteditable') === 'true') {
        input.innerHTML = '';
        const p = document.createElement('p');
        p.textContent = query;
        input.appendChild(p);
        input.dispatchEvent(new InputEvent('input', {
            bubbles: true,
            cancelable: true,
            inputType: 'insertText',
            data: query
        }));
    } else {
        input.value = query;
        input.dispatchEvent(new Event('input', { bubbles: true }));
    }
    
    await new Promise(r => setTimeout(r, 300));

    // Find and click send button
    const buttonSelectors = [
        'button[aria-label="Send Message"]',
        'button[aria-label*="Send"]',
        'button[type="submit"]'
    ];
    
    let sendButton = null;
    for (const sel of buttonSelectors) {
        sendButton = document.querySelector(sel);
        if (sendButton && !sendButton.disabled) break;
        sendButton = null;
    }
    
    if (!sendButton) {
        // Try Enter key
        input.dispatchEvent(new KeyboardEvent('keydown', {
            key: 'Enter',
            code: 'Enter',
            keyCode: 13,
            which: 13,
            bubbles: true
        }));
    } else {
        sendButton.click();
    }

    // Track initial response count before sending
    const initialResponses = document.querySelectorAll('[data-is-streaming]');
    const initialCount = initialResponses.length;
    
    // Use MutationObserver to wait for NEW response completion
    return new Promise((resolve) => {
        const startTime = Date.now();
        let resolved = false;
        
        const getLastResponseText = () => {
            const responses = document.querySelectorAll('[data-is-streaming]');
            if (responses.length === 0) return '';
            const lastResponse = responses[responses.length - 1];
            
            const fontResponse = lastResponse.querySelector('.font-claude-response');
            if (!fontResponse) return lastResponse.textContent?.trim() || '';
            
            const childDivs = fontResponse.querySelectorAll(':scope > div');
            for (let i = childDivs.length - 1; i >= 0; i--) {
                const div = childDivs[i];
                if (div.querySelector('button[class*="cursor-pointer"]')) continue;
                const markdown = div.querySelector('.standard-markdown');
                if (markdown) return markdown.textContent?.trim() || '';
            }
            return lastResponse.textContent?.trim() || '';
        };
        
        const checkComplete = () => {
            if (resolved) return false;
            
            // Get current responses
            const responses = document.querySelectorAll('[data-is-streaming]');
            
            // Must have MORE responses than before (a new one appeared)
            if (responses.length <= initialCount) return false;
            
            // Check if the newest response is done streaming
            const lastResponse = responses[responses.length - 1];
            if (lastResponse.getAttribute('data-is-streaming') === 'false') {
                const text = getLastResponseText();
                if (text && text.length > 0) {
                    resolved = true;
                    resolve({
                        success: true,
                        response: text,
                        messageCount: responses.length,
                        waitTime: Date.now() - startTime
                    });
                    return true;
                }
            }
            return false;
        };
        
        // Set up observer for new elements and attribute changes
        const observer = new MutationObserver((mutations) => {
            // Check on any mutation - new element added or streaming attribute changed
            if (checkComplete()) {
                observer.disconnect();
            }
        });
        
        // Observe for both new children and attribute changes
        observer.observe(document.body, {
            childList: true,
            attributes: true,
            attributeFilter: ['data-is-streaming'],
            subtree: true
        });
        
        // Timeout fallback
        setTimeout(() => {
            if (resolved) return;
            observer.disconnect();
            resolved = true;
            const text = getLastResponseText();
            const responses = document.querySelectorAll('[data-is-streaming]');
            resolve({
                success: text.length > 0 && responses.length > initialCount,
                response: text || '',
                partial: true,
                waitTime: Date.now() - startTime
            });
        }, maxWait);
    });
})()
"""

GET_INFO_JS = """
(() => {
    const title = document.title || "Claude";
    const url = window.location.href;
    const conversationId = url.match(/\\/chat\\/([^/?]+)/)?.[1] || null;
    
    // Count messages
    const userMessages = document.querySelectorAll('[data-testid="user-message"], [class*="user-message"], [class*="human-message"]').length;
    const assistantMessages = document.querySelectorAll('[data-testid="assistant-message"], [class*="assistant-message"], [class*="claude-message"]').length;

    return {
        title: title,
        conversationId: conversationId,
        userMessages: userMessages,
        assistantMessages: assistantMessages,
        url: url
    };
})()
"""

GET_LAST_RESPONSE_JS = r"""
(() => {
    // Claude uses data-is-streaming attribute on response containers
    const messages = document.querySelectorAll('[data-is-streaming]');
    if (messages.length === 0) return { error: 'No messages found' };

    const lastMsg = messages[messages.length - 1];
    
    // The response structure is:
    // [data-is-streaming] > .font-claude-response > div (thinking collapsible) + div (actual response)
    // The actual response is in the last direct child div that contains .standard-markdown
    const fontResponse = lastMsg.querySelector('.font-claude-response');
    if (!fontResponse) {
        return { totalMessages: messages.length, lastResponse: lastMsg.textContent?.trim() || '' };
    }
    
    // Get direct child divs of font-claude-response
    const childDivs = fontResponse.querySelectorAll(':scope > div');
    let text = '';
    
    // The last div that's not the collapsible thinking section contains the response
    for (let i = childDivs.length - 1; i >= 0; i--) {
        const div = childDivs[i];
        // Skip the thinking/collapsible section (has a button inside)
        if (div.querySelector('button[class*="cursor-pointer"]')) {
            continue;
        }
        // This should be the actual response
        const markdown = div.querySelector('.standard-markdown');
        if (markdown) {
            text = markdown.textContent?.trim() || '';
            break;
        }
    }
    
    // Fallback: get last p with response body class
    if (!text) {
        const paragraphs = lastMsg.querySelectorAll('p.font-claude-response-body');
        if (paragraphs.length > 0) {
            text = paragraphs[paragraphs.length - 1].textContent?.trim() || '';
        }
    }

    return {
        totalMessages: messages.length,
        lastResponse: text
    };
})()
"""

GET_CHAT_HISTORY_JS = r"""
((count) => {
    const userMsgs = document.querySelectorAll('[data-testid="user-message"], [class*="user-message"], [class*="human-message"]');
    const assistantMsgs = document.querySelectorAll('[data-testid="assistant-message"], [class*="assistant-message"], [class*="claude-message"]');
    
    if (userMsgs.length === 0 && assistantMsgs.length === 0) {
        return { error: 'No messages found' };
    }

    // Combine and sort by DOM position
    const allMessages = [];
    
    userMsgs.forEach((msg, idx) => {
        allMessages.push({
            element: msg,
            role: 'user',
            text: msg.textContent?.trim() || ''
        });
    });
    
    assistantMsgs.forEach((msg, idx) => {
        allMessages.push({
            element: msg,
            role: 'assistant', 
            text: msg.textContent?.trim() || ''
        });
    });

    // Sort by document position
    allMessages.sort((a, b) => {
        const pos = a.element.compareDocumentPosition(b.element);
        if (pos & Node.DOCUMENT_POSITION_FOLLOWING) return -1;
        if (pos & Node.DOCUMENT_POSITION_PRECEDING) return 1;
        return 0;
    });

    const numMessages = count || allMessages.length;
    const startIdx = Math.max(0, allMessages.length - numMessages);
    const selectedMessages = allMessages.slice(startIdx);

    const history = selectedMessages.map((msg, idx) => ({
        index: startIdx + idx,
        role: msg.role,
        text: msg.text.slice(0, 10000)
    }));

    return {
        totalMessages: allMessages.length,
        returned: history.length,
        messages: history
    };
})(%s)
"""


async def _get_claude_tabs() -> list[dict]:
    """Get list of Claude.ai tabs in the Gobbler group."""
    from gobbler_relay.client import list_tabs

    result = await list_tabs(filter_type="claude")

    if not result.get("success"):
        return []

    tabs_list = result.get("tabs", [])
    return [{"tab_id": tab["tabId"], "title": tab["title"]} for tab in tabs_list]


async def _check_relay_and_extension() -> tuple[bool, bool, str]:
    """Check if relay is running and extension is connected."""
    from gobbler_relay.client import check_connection, ensure_relay_running, is_relay_running

    relay_auto_started = False

    if _auto_start_enabled:
        try:
            was_running = await is_relay_running()
            await ensure_relay_running()
            if not was_running:
                relay_auto_started = True
        except RuntimeError as e:
            return False, False, f"Failed to start relay: {e}"
    else:
        if not await is_relay_running():
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
        Optional[int],
        typer.Option("--tab", "-t", help="Specific tab ID"),
    ] = None,
) -> None:
    """Get information about a Claude.ai conversation."""
    asyncio.run(_info(tab_id))


async def _info(tab_id: Optional[int]) -> None:
    """Async implementation of info."""
    from gobbler_relay.client import execute_script_in_tab

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
        Optional[int],
        typer.Option("--tab", "-t", help="Specific tab ID"),
    ] = None,
    timeout: Annotated[
        int,
        typer.Option("--timeout", help="Response timeout in seconds"),
    ] = 150,  # 2.5 minutes default
) -> None:
    """Send a message to Claude.ai and get the response."""
    asyncio.run(_query(message, tab_id, timeout))


async def _query(message: str, tab_id: Optional[int], timeout: int) -> None:
    """Async implementation of query."""
    from gobbler_relay.client import execute_script_in_tab

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

    script = SEND_AND_WAIT_JS % (timeout * 1000, json.dumps(message))

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
            print(data)
            return

    if isinstance(data, dict):
        if data.get("success"):
            response = data.get("response", "No response")
            console.print("[bold green]Response:[/bold green]\n")
            print(response)
            print()

            if data.get("partial"):
                print_warning("Response may be incomplete (timeout reached)")
                print_info("Use 'gobbler claude last' to check for complete response")
        else:
            print_error(data.get("error", "Unknown error"))
            raise typer.Exit(1)
    else:
        print(str(data))


@app.command()
def last(
    tab_id: Annotated[
        Optional[int],
        typer.Option("--tab", "-t", help="Specific tab ID"),
    ] = None,
) -> None:
    """Get the last response from Claude.ai chat."""
    asyncio.run(_last(tab_id))


async def _last(tab_id: Optional[int]) -> None:
    """Async implementation of last."""
    from gobbler_relay.client import execute_script_in_tab

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
            print(data)
            return

    if isinstance(data, dict):
        if data.get("error"):
            print_error(data["error"])
            raise typer.Exit(1)

        console.print(
            f"[dim]Total assistant messages:[/dim] {data.get('totalMessages', 'unknown')}\n"
        )
        console.print("[bold]Last Response:[/bold]\n")
        print(data.get("lastResponse", "No response"))
    else:
        print(str(data))


@app.command()
def history(
    tab_id: Annotated[
        Optional[int],
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


async def _history(tab_id: Optional[int], count: int, show_all: bool) -> None:
    """Async implementation of history."""
    from gobbler_relay.client import execute_script_in_tab

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
            print(data)
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
            print(text)
            console.print("\n" + "-" * 60)
    else:
        print(str(data))
