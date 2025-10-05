"""HTTP server for Gobbler browser extension."""

import asyncio
import json
import logging
import re
import uuid
from typing import Dict, Optional

from aiohttp import web
from bs4 import BeautifulSoup
from markdownify import markdownify as md

from .utils.frontmatter import count_words, create_webpage_frontmatter

logger = logging.getLogger(__name__)

# Global WebSocket connections and command queue
websocket_connections = set()
pending_commands = {}  # command_id -> {event: asyncio.Event, response: dict}


async def extract_handler(request: web.Request) -> web.Response:
    """
    Handle page extraction requests from browser extension.

    Expects JSON body with:
    {
        "url": "https://example.com",
        "title": "Page Title",
        "html": "<html>...</html>",
        "text": "page text content",
        "selector": "optional CSS selector"
    }

    Returns JSON with:
    {
        "markdown": "# Page Title\n\n...",
        "metadata": {...}
    }
    """
    try:
        data = await request.json()

        url = data.get("url", "")
        title = data.get("title", "Unknown Page")
        html = data.get("html", "")
        text = data.get("text", "")
        selector = data.get("selector")

        # Convert HTML to markdown preserving links
        soup = BeautifulSoup(html, "html.parser")

        # If selector provided, extract only that element
        if selector:
            element = soup.select_one(selector)
            if element:
                soup = BeautifulSoup(str(element), "html.parser")
            else:
                return web.json_response(
                    {"error": f"Selector '{selector}' not found"},
                    status=400
                )

        # Remove scripts, styles, and navigation elements
        for script in soup(["script", "style", "nav", "header", "footer"]):
            script.decompose()

        # Convert HTML to markdown using markdownify
        # This preserves links in [text](url) format
        markdown_content = md(
            str(soup),
            heading_style="ATX",  # Use # for headings
            bullets="-",  # Use - for bullet points
            strip=["script", "style"],  # Strip these tags
            escape_asterisks=False,  # Don't escape * in markdown
            escape_underscores=False,  # Don't escape _ in markdown
        )

        # Clean up excessive newlines (3+ newlines -> 2 newlines)
        markdown_content = re.sub(r'\n{3,}', '\n\n', markdown_content)

        # Clean up excessive spaces at line starts/ends
        markdown_content = '\n'.join(line.strip() for line in markdown_content.split('\n'))

        # Remove leading/trailing whitespace
        markdown_content = markdown_content.strip()

        # Create frontmatter
        word_count = count_words(markdown_content)
        frontmatter = create_webpage_frontmatter(
            url=url,
            title=title,
            word_count=word_count,
            conversion_time_ms=0,
        )

        # Add selector info if present
        if selector:
            lines = frontmatter.split('\n')
            frontmatter_lines = []
            for line in lines:
                frontmatter_lines.append(line)
                if line == '---' and len(frontmatter_lines) > 1:
                    frontmatter_lines.insert(-1, f'selector: {selector}')
                    frontmatter_lines.insert(-1, 'source: browser_extension')
                    break
            frontmatter = '\n'.join(frontmatter_lines)
        else:
            lines = frontmatter.split('\n')
            frontmatter_lines = []
            for line in lines:
                frontmatter_lines.append(line)
                if line == '---' and len(frontmatter_lines) > 1:
                    frontmatter_lines.insert(-1, 'source: browser_extension')
                    break
            frontmatter = '\n'.join(frontmatter_lines)

        # Combine frontmatter and content
        full_markdown = frontmatter + markdown_content

        metadata = {
            "url": url,
            "title": title,
            "word_count": word_count,
            "source": "browser_extension",
        }

        if selector:
            metadata["selector"] = selector

        logger.info(f"Extracted content from browser extension: {url}")

        return web.json_response({
            "markdown": full_markdown,
            "metadata": metadata
        })

    except Exception as e:
        logger.error(f"Extension extraction error: {e}", exc_info=True)
        return web.json_response(
            {"error": str(e)},
            status=500
        )


async def health_handler(request: web.Request) -> web.Response:
    """Health check endpoint."""
    return web.json_response({
        "status": "ok",
        "websocket_connections": len(websocket_connections)
    })


async def websocket_handler(request: web.Request) -> web.WebSocketResponse:
    """
    Handle WebSocket connections from browser extension.

    Enables bidirectional communication for sending commands to the extension
    and receiving responses.
    """
    ws = web.WebSocketResponse()
    await ws.prepare(request)

    websocket_connections.add(ws)
    logger.info(f"WebSocket connected. Total connections: {len(websocket_connections)}")

    try:
        async for msg in ws:
            if msg.type == web.WSMsgType.TEXT:
                try:
                    data = json.loads(msg.data)
                    message_type = data.get("type")

                    if message_type == "command_response":
                        # Handle response to a command we sent
                        command_id = data.get("command_id")
                        if command_id in pending_commands:
                            pending_commands[command_id]["response"] = data.get("result", {})
                            pending_commands[command_id]["event"].set()

                    elif message_type == "ping":
                        # Respond to ping with pong
                        await ws.send_json({"type": "pong"})

                    elif message_type == "register":
                        # Extension registered successfully
                        await ws.send_json({
                            "type": "registered",
                            "server_version": "0.1.0"
                        })
                        logger.info("Extension registered via WebSocket")

                except json.JSONDecodeError:
                    logger.error(f"Invalid JSON received: {msg.data}")

            elif msg.type == web.WSMsgType.ERROR:
                logger.error(f"WebSocket error: {ws.exception()}")

    finally:
        websocket_connections.discard(ws)
        logger.info(f"WebSocket disconnected. Total connections: {len(websocket_connections)}")

    return ws


async def send_command_to_extension(
    command: str,
    params: Optional[Dict] = None,
    timeout: float = 30.0
) -> Dict:
    """
    Send a command to the browser extension and wait for response.

    Args:
        command: Command name (e.g., "extract_page", "navigate", "execute_script")
        params: Optional parameters for the command
        timeout: Timeout in seconds to wait for response

    Returns:
        Response from the extension

    Raises:
        RuntimeError: If no extension is connected or command times out
    """
    if not websocket_connections:
        raise RuntimeError("No browser extension connected")

    # Generate unique command ID
    command_id = str(uuid.uuid4())

    # Create event to wait for response
    event = asyncio.Event()
    pending_commands[command_id] = {
        "event": event,
        "response": None
    }

    # Prepare command message
    message = {
        "type": "command",
        "command_id": command_id,
        "command": command,
        "params": params or {}
    }

    try:
        # Send to all connected extensions (usually just one)
        for ws in websocket_connections:
            await ws.send_json(message)
            logger.info(f"Sent command '{command}' to extension (id: {command_id})")

        # Wait for response with timeout
        try:
            await asyncio.wait_for(event.wait(), timeout=timeout)
            response = pending_commands[command_id]["response"]

            if response is None:
                raise RuntimeError("Extension response was empty")

            return response

        except asyncio.TimeoutError:
            raise RuntimeError(f"Command '{command}' timed out after {timeout} seconds")

    finally:
        # Cleanup
        pending_commands.pop(command_id, None)


def create_app() -> web.Application:
    """Create and configure the HTTP server application."""
    # Increase max request size to 50MB for large pages
    app = web.Application(client_max_size=50 * 1024 * 1024)

    # Add CORS middleware to allow browser extension requests
    async def cors_middleware(app, handler):
        async def middleware_handler(request):
            if request.method == "OPTIONS":
                # Preflight request
                response = web.Response()
            else:
                response = await handler(request)

            response.headers["Access-Control-Allow-Origin"] = "*"
            response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
            response.headers["Access-Control-Allow-Headers"] = "Content-Type"
            return response
        return middleware_handler

    app.middlewares.append(cors_middleware)

    # Add routes
    app.router.add_post("/extract", extract_handler)
    app.router.add_get("/health", health_handler)
    app.router.add_get("/ws", websocket_handler)

    return app


async def start_http_server(host: str = "127.0.0.1", port: int = 8080):
    """Start the HTTP server for browser extension."""
    app = create_app()
    runner = web.AppRunner(app)
    await runner.setup()

    site = web.TCPSite(runner, host, port)
    await site.start()

    logger.info(f"Gobbler HTTP server started on http://{host}:{port}")
    logger.info("Browser extension can now connect to extract pages")

    return runner


if __name__ == "__main__":
    # For standalone testing
    import asyncio

    async def main():
        runner = await start_http_server()
        try:
            await asyncio.Event().wait()  # Run forever
        except KeyboardInterrupt:
            await runner.cleanup()

    asyncio.run(main())
