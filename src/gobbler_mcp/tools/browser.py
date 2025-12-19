"""Browser automation tools.

Tools for controlling and extracting content from browser tabs:
- browser_check_connection: Check if browser extension is connected
- browser_navigate_to_url: Navigate to a URL in the active tab
- browser_execute_script: Execute JavaScript in the active tab
- browser_execute_script_in_tab: Execute JavaScript in a specific tab
- browser_extract_current_page: Extract page content as markdown
- browser_list_tabs: List all tabs in the Gobbler tab group
"""

import json
import logging
from typing import Optional

from fastmcp import FastMCP

from ..constants import MIN_SCRIPT_TIMEOUT, MAX_SCRIPT_TIMEOUT, DEFAULT_SCRIPT_TIMEOUT

logger = logging.getLogger(__name__)


def register_tools(mcp: FastMCP):
    """Register browser automation tools with the MCP server."""

    @mcp.tool()
    async def browser_check_connection() -> str:
        """
        Check if browser extension is connected and ready.

        Verifies that the Gobbler browser extension is installed, running, and
        connected to the MCP server via WebSocket.

        Returns:
            Connection status message
        """
        try:
            from gobbler_relay.client import check_connection, get_connection_count

            status = await check_connection()

            if status.get("status") == "ok":
                conn_count = status.get("websocket_connections", 0)
                if conn_count > 0:
                    return f"Browser extension is connected and ready. ({conn_count} connection(s))"
                else:
                    return (
                        "Relay server is running but no browser extension connected.\n\n"
                        "To connect:\n"
                        "1. Install the Gobbler browser extension in Chrome\n"
                        "2. Add tabs to the Gobbler group via the extension popup\n"
                        "3. The extension will auto-connect to the relay server"
                    )
            else:
                return (
                    "Relay server is not running.\n\n"
                    "The relay should start automatically. If it doesn't, run:\n"
                    "  python -m gobbler_relay.relay --daemon"
                )
        except Exception as e:
            logger.error(f"Error checking browser connection: {e}", exc_info=True)
            return f"Failed to check browser connection: {str(e)}"

    @mcp.tool()
    async def browser_navigate_to_url(url: str, wait_for_load: bool = True) -> str:
        """
        Navigate browser extension's active tab to a URL.

        Sends a navigation command to the browser extension to load the specified URL
        in the currently active tab.

        Args:
            url: Full URL to navigate to (must include http:// or https://)
            wait_for_load: Wait for page to fully load before returning (default: True)

        Returns:
            Success message with the URL navigated to
        """
        try:
            from gobbler_relay.client import send_command

            # Validate URL
            if not url.startswith(('http://', 'https://')):
                return "Error: URL must start with http:// or https://"

            # Send navigation command via HTTP client
            result = await send_command(
                command="navigate",
                params={"url": url, "wait_for_load": wait_for_load},
                timeout=60.0  # Long timeout for page loads
            )

            if result.get("success"):
                return f"Successfully navigated to: {url}"
            else:
                error = result.get("error", "Unknown error")
                return f"Failed to navigate: {error}"

        except RuntimeError as e:
            return str(e)
        except Exception as e:
            logger.error(f"Error navigating browser: {e}", exc_info=True)
            return f"Failed to navigate browser: {str(e)}"

    @mcp.tool()
    async def browser_execute_script(script: str, timeout: int = DEFAULT_SCRIPT_TIMEOUT) -> str:
        """
        Execute JavaScript in the browser extension's active tab.

        Runs arbitrary JavaScript code in the context of the currently active tab
        and returns the result. The script can access the DOM, interact with the page,
        and return data back to Claude.

        Args:
            script: JavaScript code to execute (must be a complete expression or IIFE)
            timeout: Maximum time to wait for script execution in seconds (default: 30, max: 150)

        Returns:
            JSON-serialized result of the script execution, or error message

        Examples:
            Get page title:
            browser_execute_script("document.title")

            Scroll and wait:
            browser_execute_script("(async () => { window.scrollTo(0, document.body.scrollHeight); await new Promise(r => setTimeout(r, 1000)); return {scrolled: true}; })()")

            Extract data:
            browser_execute_script("Array.from(document.querySelectorAll('h1')).map(h => h.textContent)")
        """
        try:
            from gobbler_relay.client import execute_script

            # Validate timeout
            if timeout < MIN_SCRIPT_TIMEOUT or timeout > MAX_SCRIPT_TIMEOUT:
                return f"Error: timeout must be between {MIN_SCRIPT_TIMEOUT} and {MAX_SCRIPT_TIMEOUT} seconds"

            # Send script execution command via HTTP client
            result = await execute_script(script=script, timeout=float(timeout))

            if result.get("success"):
                # Return the result as JSON
                script_result = result.get("result")
                if script_result is None:
                    return "null"
                return json.dumps(script_result) if not isinstance(script_result, str) else script_result
            else:
                error = result.get("error", "Unknown error")
                return f"Script execution failed: {error}"

        except RuntimeError as e:
            return str(e)
        except Exception as e:
            logger.error(f"Error executing script: {e}", exc_info=True)
            return f"Failed to execute script: {str(e)}"

    @mcp.tool()
    async def browser_extract_current_page(selector: Optional[str] = None) -> str:
        """
        Extract the current page's content as markdown.

        Extracts HTML content from the browser extension's active tab and converts
        it to clean markdown format. Optionally uses a CSS selector to extract only
        a specific part of the page.

        Args:
            selector: Optional CSS selector to extract specific content (e.g., "article.main", ".content")

        Returns:
            Markdown text with YAML frontmatter containing page metadata
        """
        try:
            from gobbler_relay.client import extract_page

            # Send extraction command via HTTP client
            result = await extract_page(selector=selector)

            if result.get("success"):
                markdown = result.get("markdown", "")
                return markdown
            else:
                error = result.get("error", "Unknown error")
                return f"Failed to extract page: {error}"

        except RuntimeError as e:
            return str(e)
        except Exception as e:
            logger.error(f"Error extracting page: {e}", exc_info=True)
            return f"Failed to extract page: {str(e)}"

    @mcp.tool()
    async def browser_list_tabs(filter: Optional[str] = None) -> str:
        """
        List all tabs in the Gobbler tab group with their IDs, titles, and URLs.

        Returns a list of tabs that Claude can interact with. Only tabs in the
        Gobbler group are accessible for security.

        Args:
            filter: Optional filter - use 'notebooklm' to only show NotebookLM tabs

        Returns:
            JSON list of tabs with tabId, title, url, and isActive fields
        """
        try:
            from gobbler_relay.client import list_tabs

            # Send list tabs command via HTTP client
            result = await list_tabs(filter_type=filter)

            if result.get("success"):
                tabs = result.get("tabs", [])
                if not tabs:
                    return "No tabs in Gobbler group. Add tabs via extension popup or right-click menu."

                # Format as readable output
                lines = [f"Found {len(tabs)} tab(s) in Gobbler group:\n"]
                for tab in tabs:
                    active_marker = " (active)" if tab.get("isActive") else ""
                    lines.append(f"  [{tab['tabId']}] {tab['title']}{active_marker}")
                    lines.append(f"       {tab['url']}")
                return "\n".join(lines)
            else:
                error = result.get("error", "Unknown error")
                return f"Failed to list tabs: {error}"

        except RuntimeError as e:
            return str(e)
        except Exception as e:
            logger.error(f"Error listing tabs: {e}", exc_info=True)
            return f"Failed to list tabs: {str(e)}"

    @mcp.tool()
    async def browser_execute_script_in_tab(tab_id: int, script: str, timeout: int = DEFAULT_SCRIPT_TIMEOUT) -> str:
        """
        Execute JavaScript in a specific browser tab (must be in Gobbler group).

        Use browser_list_tabs() first to get available tab IDs. This allows targeting
        specific tabs instead of just the active tab - useful for multi-instance
        scenarios like having multiple NotebookLM notebooks open.

        Args:
            tab_id: The tab ID to execute the script in (from browser_list_tabs)
            script: JavaScript code to execute (must be a complete expression or IIFE)
            timeout: Maximum time to wait for script execution in seconds (default: 30, max: 150)

        Returns:
            JSON-serialized result of the script execution, or error message
        """
        try:
            from gobbler_relay.client import execute_script_in_tab

            # Validate timeout
            timeout = min(max(timeout, MIN_SCRIPT_TIMEOUT), MAX_SCRIPT_TIMEOUT)

            # Send command via HTTP client
            result = await execute_script_in_tab(
                tab_id=tab_id,
                script=script,
                timeout=float(timeout)
            )

            if result.get("success"):
                script_result = result.get("result")
                executed_tab_id = result.get("tabId")

                # Return result as JSON if it's complex, otherwise as string
                if script_result is None:
                    return f"Script executed successfully in tab {executed_tab_id} (no return value)"
                elif isinstance(script_result, (dict, list)):
                    return json.dumps(script_result, indent=2)
                else:
                    return str(script_result)
            else:
                error = result.get("error", "Unknown error")
                return f"Script execution failed: {error}"

        except RuntimeError as e:
            return str(e)
        except Exception as e:
            logger.error(f"Error executing script in tab: {e}", exc_info=True)
            return f"Failed to execute script in tab: {str(e)}"
