#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "httpx",
#     "click",
# ]
# ///
"""
Gobbler NotebookLM CLI

Interact with NotebookLM notebooks via the Gobbler browser extension.
Send queries, get responses, and manage notebook interactions.

Usage:
    uv run scripts/notebooklm.py list
    uv run scripts/notebooklm.py info
    uv run scripts/notebooklm.py query "What are the key points?"
    uv run scripts/notebooklm.py query "Summarize this" --tab-id 12345
    uv run scripts/notebooklm.py last
    uv run scripts/notebooklm.py last --tab-id 12345
    uv run scripts/notebooklm.py history
    uv run scripts/notebooklm.py history --count 10
    uv run scripts/notebooklm.py history --all
"""

import json
import os
import sys
import time

import click
import httpx

# Allow override via environment variable for flexibility
GOBBLER_URL = os.environ.get("GOBBLER_RELAY_URL", "http://localhost:4625")
TIMEOUT = 120.0  # NotebookLM queries can take a while


def send_command(command: str, params: dict | None = None, timeout: float = TIMEOUT) -> dict:
    """Send command to browser extension via relay server."""
    with httpx.Client(timeout=timeout + 5) as client:
        response = client.post(
            f"{GOBBLER_URL}/command",
            json={"command": command, "params": params or {}, "timeout": timeout},
        )
        if response.status_code == 503:
            error_data = response.json()
            raise click.ClickException(error_data.get("error", "No browser extension connected"))
        response.raise_for_status()
        return response.json()


def get_notebooklm_tabs() -> list[dict]:
    """Get list of NotebookLM tabs."""
    result = send_command("list_gobbler_tabs", {"filter": "notebooklm"})

    if not result.get("success"):
        return []

    tabs_list = result.get("tabs", [])
    return [{"tab_id": tab["tabId"], "title": tab["title"]} for tab in tabs_list]


# JavaScript to interact with NotebookLM - combined send and wait
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
    const setter = Object.getOwnPropertyDescriptor(window.HTMLTextAreaElement.prototype, 'value').set;
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

    // Wait for response
    const startTime = Date.now();
    while (Date.now() - startTime < maxWait) {
        await new Promise(r => setTimeout(r, 1000));

        const messages = document.querySelectorAll('chat-message');
        if (messages.length >= initialCount + 2) {
            const lastMsg = messages[messages.length - 1];
            const text = lastMsg?.innerText || '';

            // Skip if still loading
            if (text.length < 50 && (text.includes('Finding') || text.includes('Searching') || text.includes('...'))) {
                continue;
            }

            // Wait a bit more to ensure response is complete
            await new Promise(r => setTimeout(r, 2000));

            // Get the text again in case it updated
            const finalText = messages[messages.length - 1]?.innerText || text;

            return {
                success: true,
                response: finalText,
                messageCount: messages.length
            };
        }
    }

    // Return whatever we have
    const finalMessages = document.querySelectorAll('chat-message');
    if (finalMessages.length > initialCount) {
        const text = finalMessages[finalMessages.length - 1]?.innerText || '';
        return {
            success: true,
            response: text,
            partial: true
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


@click.group()
def cli():
    """Gobbler NotebookLM CLI - Interact with NotebookLM notebooks."""
    pass


@cli.command()
@click.option("--tab-id", default=None, type=int, help="Specific tab ID to query")
def info(tab_id: int | None):
    """Get information about NotebookLM notebook."""
    try:
        # First list available tabs
        tabs = get_notebooklm_tabs()

        if not tabs:
            click.echo("No NotebookLM tabs found in Gobbler group.", err=True)
            click.echo(
                "Make sure you have a NotebookLM tab open and it's in the Gobbler tab group.",
                err=True,
            )
            sys.exit(1)

        click.echo(f"Found {len(tabs)} NotebookLM tab(s):\n")
        for tab in tabs:
            click.echo(f"  [{tab['tab_id']}] {tab['title']}")

        # Get info from specific tab or active one
        target_tab = tab_id or tabs[0]["tab_id"]

        click.echo(f"\nGetting info from tab {target_tab}...")
        result = send_command(
            "execute_script_in_tab",
            {"tabId": target_tab, "script": GET_INFO_JS},
            timeout=30,
        )

        if result.get("success"):
            info_data = result.get("result", {})
            if isinstance(info_data, dict):
                click.echo(f"\nNotebook: {info_data.get('title', 'Unknown')}")
                click.echo(f"Sources: {info_data.get('sourceCount', 0)}")
                click.echo(f"Messages: {info_data.get('messageCount', 0)}")
                click.echo(f"URL: {info_data.get('url', 'N/A')}")
            else:
                click.echo(f"\nResult: {info_data}")
        else:
            click.echo(f"Failed to get info: {result.get('error', 'Unknown error')}", err=True)

    except httpx.ConnectError:
        click.echo(f"Error: Cannot connect to Gobbler relay at {GOBBLER_URL}", err=True)
        click.echo("", err=True)
        click.echo("The relay server must be running. To start it:", err=True)
        click.echo("  uv run src/gobbler_relay/relay.py --daemon", err=True)
        click.echo("", err=True)
        click.echo("To check status:", err=True)
        click.echo("  uv run src/gobbler_relay/relay.py --status", err=True)
        sys.exit(1)
    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


@cli.command()
@click.argument("query_text")
@click.option("--tab-id", default=None, type=int, help="Specific tab ID to query")
@click.option("--timeout", "-t", default=60, help="Response timeout in seconds")
def query(query_text: str, tab_id: int | None, timeout: int):
    """Send a query to NotebookLM and get the response."""
    try:
        # Get available tabs
        tabs = get_notebooklm_tabs()

        if not tabs:
            click.echo("No NotebookLM tabs found in Gobbler group.", err=True)
            sys.exit(1)

        # Select target tab
        if tab_id:
            target_tab = tab_id
            tab_info = next((t for t in tabs if t["tab_id"] == tab_id), None)
            if not tab_info:
                click.echo(f"Tab {tab_id} not found. Available tabs:", err=True)
                for t in tabs:
                    click.echo(f"  [{t['tab_id']}] {t['title']}", err=True)
                sys.exit(1)
        else:
            target_tab = tabs[0]["tab_id"]
            tab_info = tabs[0]

        click.echo(f"Sending query to: {tab_info['title']}")
        click.echo(f"Query: {query_text}")
        click.echo("Waiting for response...\n")

        # Send query and wait for response in one script
        script = SEND_AND_WAIT_JS % (timeout * 1000, json.dumps(query_text))
        result = send_command(
            "execute_script_in_tab",
            {"tabId": target_tab, "script": script},
            timeout=timeout + 15,
        )

        if result.get("success"):
            data = result.get("result", {})
            # Parse if string
            if isinstance(data, str):
                try:
                    data = json.loads(data)
                except json.JSONDecodeError:
                    click.echo(data)
                    return

            if isinstance(data, dict):
                if data.get("success"):
                    response = data.get("response", "No response text")
                    # Clean up NotebookLM UI artifacts
                    import re

                    response = re.sub(r"keep_pin\s*Save to note", "", response)
                    response = (
                        response.replace("copy_all", "")
                        .replace("thumb_up", "")
                        .replace("thumb_down", "")
                    )
                    response = re.sub(r"\n{3,}", "\n\n", response).strip()

                    click.echo("--- Response ---\n")
                    click.echo(response)
                    if data.get("partial"):
                        click.echo("\n(Response may be incomplete)")
                else:
                    click.echo(f"Error: {data.get('error', 'Unknown error')}", err=True)
                    sys.exit(1)
            else:
                click.echo(str(data))
        else:
            click.echo(f"Failed: {result.get('error', 'Unknown error')}", err=True)
            sys.exit(1)

    except httpx.ConnectError:
        click.echo(f"Error: Cannot connect to Gobbler relay at {GOBBLER_URL}", err=True)
        click.echo("", err=True)
        click.echo("The relay server must be running. To start it:", err=True)
        click.echo("  uv run src/gobbler_relay/relay.py --daemon", err=True)
        click.echo("", err=True)
        click.echo("To check status:", err=True)
        click.echo("  uv run src/gobbler_relay/relay.py --status", err=True)
        sys.exit(1)
    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


@cli.command("list")
def list_notebooks():
    """List available NotebookLM tabs."""
    try:
        tabs = get_notebooklm_tabs()

        if not tabs:
            click.echo("No NotebookLM tabs found in Gobbler group.")
            click.echo("\nTo use NotebookLM with Gobbler:")
            click.echo("  1. Open NotebookLM in your browser")
            click.echo("  2. Move the tab to the Gobbler tab group")
            return

        click.echo(f"Found {len(tabs)} NotebookLM tab(s):\n")
        for tab in tabs:
            click.echo(f"  [{tab['tab_id']}] {tab['title']}")

    except httpx.ConnectError:
        click.echo(f"Error: Cannot connect to Gobbler relay at {GOBBLER_URL}", err=True)
        click.echo("", err=True)
        click.echo("The relay server must be running. To start it:", err=True)
        click.echo("  uv run src/gobbler_relay/relay.py --daemon", err=True)
        sys.exit(1)
    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


@cli.command()
@click.option("--tab-id", default=None, type=int, help="Specific tab ID to query")
def last(tab_id: int | None):
    """Get the last response from the NotebookLM chat without waiting."""
    try:
        # Get available tabs
        tabs = get_notebooklm_tabs()

        if not tabs:
            click.echo("No NotebookLM tabs found in Gobbler group.", err=True)
            sys.exit(1)

        # Select target tab
        if tab_id:
            target_tab = tab_id
            tab_info = next((t for t in tabs if t["tab_id"] == tab_id), None)
            if not tab_info:
                click.echo(f"Tab {tab_id} not found. Available tabs:", err=True)
                for t in tabs:
                    click.echo(f"  [{t['tab_id']}] {t['title']}", err=True)
                sys.exit(1)
        else:
            target_tab = tabs[0]["tab_id"]
            tab_info = tabs[0]

        click.echo(f"Getting last response from: {tab_info['title']}\n")

        # Execute script to get last response
        result = send_command(
            "execute_script_in_tab",
            {"tabId": target_tab, "script": GET_LAST_RESPONSE_JS},
            timeout=10,
        )

        if result.get("success"):
            data = result.get("result", {})

            # Parse if string
            if isinstance(data, str):
                try:
                    data = json.loads(data)
                except json.JSONDecodeError:
                    click.echo(data)
                    return

            if isinstance(data, dict):
                if data.get("error"):
                    click.echo(f"Error: {data['error']}", err=True)
                    sys.exit(1)

                click.echo(f"Total messages in chat: {data.get('totalMessages', 'unknown')}")
                click.echo("\n--- Last Response ---\n")
                click.echo(data.get("lastResponse", "No response text"))
            else:
                click.echo(str(data))
        else:
            click.echo(f"Failed: {result.get('error', 'Unknown error')}", err=True)
            sys.exit(1)

    except httpx.ConnectError:
        click.echo(f"Error: Cannot connect to Gobbler relay at {GOBBLER_URL}", err=True)
        click.echo("", err=True)
        click.echo("The relay server must be running. To start it:", err=True)
        click.echo("  uv run src/gobbler_relay/relay.py --daemon", err=True)
        sys.exit(1)
    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


@cli.command()
@click.option("--tab-id", default=None, type=int, help="Specific tab ID to query")
@click.option(
    "--count", "-n", default=5, type=int, help="Number of recent messages to show (default: 5)"
)
@click.option("--all", "-a", is_flag=True, help="Show all messages in the chat")
def history(tab_id: int | None, count: int, all: bool):
    """Get recent messages from the NotebookLM chat history."""
    try:
        # Get available tabs
        tabs = get_notebooklm_tabs()

        if not tabs:
            click.echo("No NotebookLM tabs found in Gobbler group.", err=True)
            sys.exit(1)

        # Select target tab
        if tab_id:
            target_tab = tab_id
            tab_info = next((t for t in tabs if t["tab_id"] == tab_id), None)
            if not tab_info:
                click.echo(f"Tab {tab_id} not found. Available tabs:", err=True)
                for t in tabs:
                    click.echo(f"  [{t['tab_id']}] {t['title']}", err=True)
                sys.exit(1)
        else:
            target_tab = tabs[0]["tab_id"]
            tab_info = tabs[0]

        # If --all flag is set, use null to get all messages
        message_count = "null" if all else str(count)

        click.echo(f"Getting chat history from: {tab_info['title']}\n")

        # Execute script to get chat history
        script = GET_CHAT_HISTORY_JS % message_count
        result = send_command(
            "execute_script_in_tab",
            {"tabId": target_tab, "script": script},
            timeout=10,
        )

        if result.get("success"):
            data = result.get("result", {})

            # Parse if string
            if isinstance(data, str):
                try:
                    data = json.loads(data)
                except json.JSONDecodeError:
                    click.echo(data)
                    return

            if isinstance(data, dict):
                if data.get("error"):
                    click.echo(f"Error: {data['error']}", err=True)
                    sys.exit(1)

                total = data.get("totalMessages", 0)
                returned = data.get("returned", 0)
                messages = data.get("messages", [])

                click.echo(f"Total messages in chat: {total}")
                click.echo(f"Showing {returned} message(s)\n")
                click.echo("=" * 60)

                for msg in messages:
                    idx = msg.get("index", 0)
                    text = msg.get("text", "")
                    click.echo(f"\n[Message {idx + 1}]\n")
                    click.echo(text)
                    click.echo("\n" + "-" * 60)
            else:
                click.echo(str(data))
        else:
            click.echo(f"Failed: {result.get('error', 'Unknown error')}", err=True)
            sys.exit(1)

    except httpx.ConnectError:
        click.echo(f"Error: Cannot connect to Gobbler relay at {GOBBLER_URL}", err=True)
        click.echo("", err=True)
        click.echo("The relay server must be running. To start it:", err=True)
        click.echo("  uv run src/gobbler_relay/relay.py --daemon", err=True)
        sys.exit(1)
    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


if __name__ == "__main__":
    cli()
