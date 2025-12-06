# Browser Extension - Bidirectional Communication

## Overview

The Gobbler browser extension now supports **bidirectional communication** with the Gobbler MCP server using WebSockets. This enables:

1. **Extension → MCP**: Extract page content and send to MCP for processing (original functionality)
2. **MCP → Extension**: Send commands to the browser extension from Claude or any MCP client

## Architecture

### System Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                         MCP CLIENT LAYER                             │
│                                                                       │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐              │
│  │ Claude Code  │  │Claude Desktop│  │  Other MCP   │              │
│  │              │  │              │  │   Clients    │              │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘              │
│         │                 │                 │                        │
│         └─────────────────┼─────────────────┘                        │
│                           │                                          │
│                           │ MCP Protocol (stdio/SSE)                │
└───────────────────────────┼──────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────────────┐
│                      GOBBLER MCP SERVER                              │
│                                                                       │
│  ┌───────────────────────────────────────────────────────────────┐ │
│  │                    MCP Tools (FastMCP)                         │ │
│  │                                                                 │ │
│  │  • transcribe_youtube          • browser_check_connection      │ │
│  │  • fetch_webpage               • browser_extract_current_page  │ │
│  │  • convert_document            • browser_navigate_to_url       │ │
│  │  • transcribe_audio            • browser_execute_script        │ │
│  │  • batch_* operations          • browser_get_page_info         │ │
│  │  • crawl_site                                                   │ │
│  └──────────────────────┬──────────────────┬──────────────────────┘ │
│                         │                  │                         │
│  ┌──────────────────────▼────────┐  ┌─────▼──────────────────────┐ │
│  │    Converters & Utils         │  │   HTTP Server (aiohttp)    │ │
│  │                               │  │                             │ │
│  │  • YouTube API                │  │  Port: 4625                │ │
│  │  • Crawl4AI Client            │  │                             │ │
│  │  • Docling Client             │  │  Endpoints:                │ │
│  │  • faster-whisper             │  │  • POST /extract           │ │
│  │                               │  │  • GET  /health            │ │
│  │                               │  │  • WS   /ws                │ │
│  │                               │  │                             │ │
│  └───────────────────────────────┘  │  WebSocket:                │ │
│                                      │  • Connection tracking     │ │
│                                      │  • Command queue          │ │
│                                      │  • Response handling      │ │
│                                      └─────────────┬─────────────┘ │
└────────────────────────────────────────────────────┼─────────────────┘
                                                     │
                                                     │ WebSocket
                                         ws://localhost:4625/ws
                                                     │
┌────────────────────────────────────────────────────┼─────────────────┐
│                    BROWSER EXTENSION                │                 │
│                                                     ▼                 │
│  ┌─────────────────────────────────────────────────────────────────┐ │
│  │                Background Service Worker                         │ │
│  │                                                                  │ │
│  │  ┌────────────────┐      ┌──────────────────────────────────┐  │ │
│  │  │   WebSocket    │      │      Command Handlers            │  │ │
│  │  │    Client      │      │                                  │  │ │
│  │  │                │      │  • extract_page()                │  │ │
│  │  │  • Auto-connect│◄────►│  • navigate()                    │  │ │
│  │  │  • Keep-alive  │      │  • execute_script()              │  │ │
│  │  │  • Reconnect   │      │  • get_page_info()               │  │ │
│  │  └────────────────┘      └──────────────┬───────────────────┘  │ │
│  │                                          │                       │ │
│  └──────────────────────────────────────────┼───────────────────────┘ │
│                                             │                         │
│  ┌──────────────────────────────────────────▼───────────────────────┐ │
│  │                      Chrome APIs                                 │ │
│  │                                                                   │ │
│  │  • chrome.scripting.executeScript()                             │ │
│  │  • chrome.tabs.query()                                          │ │
│  │  • chrome.tabs.update()                                         │ │
│  │  • chrome.storage                                               │ │
│  └───────────────────────────────────────────────────────────────┘ │
│                                             │                         │
└─────────────────────────────────────────────┼─────────────────────────┘
                                              │
                                              ▼
                                    ┌──────────────────┐
                                    │  Browser Tab     │
                                    │  (Web Page DOM)  │
                                    └──────────────────┘
```

### Communication Flow

```
┌─────────────────┐         WebSocket         ┌──────────────────┐
│                 │ ◄────────────────────────► │                  │
│  Browser        │                            │  Gobbler MCP     │
│  Extension      │                            │  Server          │
│                 │                            │                  │
└─────────────────┘                            └──────────────────┘
         │                                              │
         │                                              │
         ▼                                              ▼
  Current Browser Tab                            Claude / MCP Client
```

### WebSocket Protocol

**Connection**: `ws://localhost:4625/ws`

**Message Types**:

1. **Registration** (Extension → Server):
```json
{
  "type": "register",
  "extension_version": "0.1.0"
}
```

2. **Command** (Server → Extension):
```json
{
  "type": "command",
  "command_id": "uuid-v4",
  "command": "extract_page",
  "params": {
    "selector": ".main-content"
  }
}
```

3. **Command Response** (Extension → Server):
```json
{
  "type": "command_response",
  "command_id": "uuid-v4",
  "result": {
    "success": true,
    "markdown": "...",
    "metadata": {}
  }
}
```

4. **Keep-Alive**:
   - Extension sends `{"type": "ping"}` every 30 seconds
   - Server responds with `{"type": "pong"}`

## MCP Tools

### 1. `browser_check_connection()`

Check if a browser extension is connected.

```python
# Returns connection status
"Browser extension is connected and ready."
```

### 2. `browser_extract_current_page(selector=None, timeout=30.0)`

Extract content from the current page in the browser.

**Arguments**:
- `selector` (optional): CSS selector to extract specific content
- `timeout`: Timeout in seconds (default: 30)

**Example**:
```python
# Extract entire page
markdown = await browser_extract_current_page()

# Extract specific content
markdown = await browser_extract_current_page(selector=".article-content")
```

### 3. `browser_navigate_to_url(url, wait_for_load=True, timeout=30.0)`

Navigate the browser to a specific URL.

**Arguments**:
- `url`: URL to navigate to
- `wait_for_load`: Wait for page to fully load (default: True)
- `timeout`: Timeout in seconds (default: 30)

**Example**:
```python
# Navigate and wait for page load
await browser_navigate_to_url("https://example.com")

# Navigate without waiting
await browser_navigate_to_url("https://example.com", wait_for_load=False)
```

### 4. `browser_execute_script(script, timeout=30.0)`

Execute JavaScript in the current browser page.

**Arguments**:
- `script`: JavaScript code to execute
- `timeout`: Timeout in seconds (default: 30)

**Example**:
```python
# Get page title
title = await browser_execute_script("document.title")

# Get all links
links = await browser_execute_script(
    "Array.from(document.querySelectorAll('a')).map(a => a.href)"
)

# Click a button
await browser_execute_script("document.querySelector('#submit-btn').click()")

# Get computed style
color = await browser_execute_script(
    "window.getComputedStyle(document.body).backgroundColor"
)
```

### 5. `browser_get_page_info(timeout=30.0)`

Get metadata about the current page.

**Returns**:
```json
{
  "url": "https://example.com/page",
  "title": "Page Title",
  "hostname": "example.com",
  "pathname": "/page",
  "protocol": "https:",
  "links_count": 42,
  "images_count": 10,
  "forms_count": 2
}
```

## Extension Commands

The background service worker handles these commands from the MCP server:

### 1. `extract_page`

Extract page content and return as markdown.

**Parameters**:
- `selector` (optional): CSS selector

**Response**:
```json
{
  "success": true,
  "markdown": "---\ntitle: Page Title\n---\n\n# Content...",
  "metadata": {
    "url": "...",
    "title": "..."
  }
}
```

### 2. `navigate`

Navigate to a URL.

**Parameters**:
- `url`: Target URL
- `wait_for_load`: Boolean

**Response**:
```json
{
  "success": true
}
```

### 3. `execute_script`

Execute JavaScript in page context.

**Parameters**:
- `script`: JavaScript code

**Response**:
```json
{
  "success": true,
  "result": "execution result"
}
```

### 4. `get_page_info`

Get current page information.

**Response**:
```json
{
  "success": true,
  "info": {
    "url": "...",
    "title": "...",
    ...
  }
}
```

## Installation & Setup

### 1. Install the Browser Extension

**Chrome/Edge**:
1. Open `chrome://extensions/` or `edge://extensions/`
2. Enable "Developer mode"
3. Click "Load unpacked"
4. Select the `/Users/dylanisaac/Projects/gobbler/browser-extension/` folder

**Firefox**:
1. Open `about:debugging#/runtime/this-firefox`
2. Click "Load Temporary Add-on"
3. Select any file in `/Users/dylanisaac/Projects/gobbler/browser-extension/`

### 2. Start Gobbler MCP Server

The HTTP server with WebSocket support starts automatically with the MCP server:

```bash
# Start MCP server (includes HTTP/WebSocket server)
uv run gobbler-mcp
```

Or configure in your MCP client settings.

### 3. Verify Connection

1. Open the browser extension popup
2. Check for "🟢 Connected to Gobbler MCP" status
3. Or use the MCP tool:
   ```python
   await browser_check_connection()
   ```

## Configuration

### Server Configuration

Edit `~/.config/gobbler/config.yaml`:

```yaml
http_server:
  enabled: true
  host: "127.0.0.1"
  port: 4625
```

### Extension Configuration

The extension connects to `ws://localhost:4625/ws` by default. To change:

Edit `/Users/dylanisaac/Projects/gobbler/browser-extension/background.js`:

```javascript
const WS_URL = 'ws://localhost:4625/ws';  // Change this
```

## Usage Examples

### Example 1: Navigate and Extract

```python
# Navigate to a page
await browser_navigate_to_url("https://docs.python.org/3/")

# Extract main content
markdown = await browser_extract_current_page(selector=".body")

# Save to file
await save_markdown_file("/path/to/python-docs.md", markdown)
```

### Example 2: Automated Data Collection

```python
# Navigate to search results
await browser_navigate_to_url("https://example.com/search?q=python")

# Get all result links
links_json = await browser_execute_script("""
  Array.from(document.querySelectorAll('.result-link')).map(a => ({
    url: a.href,
    title: a.textContent.trim()
  }))
""")

# Parse and process links
import json
links = json.loads(links_json)

for link in links:
    await browser_navigate_to_url(link["url"])
    markdown = await browser_extract_current_page()
    # Process markdown...
```

### Example 3: Form Interaction

```python
# Navigate to login page
await browser_navigate_to_url("https://example.com/login")

# Fill form (note: use with caution for security)
await browser_execute_script("""
  document.querySelector('#username').value = 'testuser';
  document.querySelector('#password').value = 'testpass';
  document.querySelector('#login-btn').click();
""")

# Wait for redirect
await asyncio.sleep(2)

# Extract authenticated content
markdown = await browser_extract_current_page()
```

### Example 4: Monitoring Page Changes

```python
# Navigate to dashboard
await browser_navigate_to_url("https://example.com/dashboard")

# Get initial state
initial_data = await browser_execute_script("""
  document.querySelector('.stats').innerText
""")

# Wait and check again
await asyncio.sleep(60)
current_data = await browser_execute_script("""
  document.querySelector('.stats').innerText
""")

if initial_data != current_data:
    print("Dashboard updated!")
```

## Error Handling

### Connection Errors

If the extension isn't connected:

```python
try:
    result = await browser_extract_current_page()
except RuntimeError as e:
    if "No browser extension connected" in str(e):
        print("Please open the browser extension")
    else:
        raise
```

### Timeout Errors

Commands timeout after 30 seconds by default:

```python
try:
    # Increase timeout for slow operations
    result = await browser_navigate_to_url(
        "https://slow-site.com",
        timeout=60.0
    )
except RuntimeError as e:
    if "timed out" in str(e):
        print("Operation took too long")
    else:
        raise
```

### Script Execution Errors

```python
result = await browser_execute_script("invalid.javascript.code()")
# Returns: "Script execution failed: ReferenceError: invalid is not defined"
```

## Troubleshooting

### Extension Not Connecting

1. **Check extension is installed and enabled**
   - Visit `chrome://extensions/` or `edge://extensions/`
   - Ensure Gobbler extension is enabled

2. **Check MCP server is running**
   ```bash
   curl http://localhost:4625/health
   # Should return: {"status": "ok", "websocket_connections": 1}
   ```

3. **Check browser console**
   - Open extension popup
   - Right-click → Inspect
   - Check Console tab for WebSocket errors

4. **Check service worker logs**
   - Visit `chrome://extensions/`
   - Click "Inspect views: service worker" under Gobbler extension
   - Check Console for connection messages

### Commands Not Working

1. **Verify connection**
   ```python
   await browser_check_connection()
   ```

2. **Check command timeout**
   - Increase timeout for slow operations
   - Default is 30 seconds

3. **Verify active tab**
   - Extension operates on the active browser tab
   - Make sure the correct tab is focused

### WebSocket Reconnection

The extension automatically reconnects every 5 seconds if disconnected:

- Check service worker logs: "Attempting to reconnect..."
- Restart MCP server if needed
- Reload extension if reconnection fails

## Security Considerations

1. **Local Only**: WebSocket server only accepts connections from localhost (127.0.0.1)

2. **Script Execution**: The `browser_execute_script` tool uses `eval()` - only use with trusted scripts

3. **Permissions**: Extension requires:
   - `activeTab`: Access current tab content
   - `scripting`: Execute scripts in tabs
   - `storage`: Save configuration

4. **HTTPS**: Extension works with both HTTP and HTTPS pages

5. **Cross-Origin**: Extension can access any page, but respects CORS for fetch requests

## Development

### Adding New Commands

1. **Add command handler in background.js**:
```javascript
case 'my_command':
  result = await myCommandHandler(params);
  break;
```

2. **Implement handler function**:
```javascript
async function myCommandHandler(params) {
  try {
    // Your logic here
    return { success: true, result: ... };
  } catch (error) {
    return { success: false, error: error.message };
  }
}
```

3. **Add MCP tool in server.py**:
```python
@mcp.tool()
async def browser_my_command(param1: str, timeout: float = 30.0) -> str:
    from .http_server import send_command_to_extension

    response = await send_command_to_extension(
        command="my_command",
        params={"param1": param1},
        timeout=timeout
    )

    if response.get("success"):
        return response.get("result")
    else:
        return f"Error: {response.get('error')}"
```

### Testing

**Manual Testing**:
1. Open extension popup
2. Check connection status
3. Use MCP tools from Claude or MCP client

**Console Testing**:
```javascript
// In extension service worker console
chrome.tabs.query({active: true, currentWindow: true}, async (tabs) => {
  const result = await extractPage({selector: '.content'});
  console.log(result);
});
```

## API Reference

### HTTP Server Functions

#### `send_command_to_extension(command, params, timeout)`

Send command to browser extension via WebSocket.

**Arguments**:
- `command` (str): Command name
- `params` (dict): Command parameters
- `timeout` (float): Timeout in seconds

**Returns**: `dict` with command result

**Raises**: `RuntimeError` if no extension connected or timeout

### Global Variables

- `websocket_connections`: Set of active WebSocket connections
- `pending_commands`: Dict mapping command_id to response events

## Changelog

### Version 0.1.0 (2025-01-05)

- ✅ Initial bidirectional communication implementation
- ✅ WebSocket server with automatic reconnection
- ✅ Command queue and response handling
- ✅ Five MCP tools for browser control
- ✅ Extension auto-connects on startup
- ✅ Connection status indicator in popup
- ✅ Support for page extraction with selectors
- ✅ Support for navigation and script execution
- ✅ Comprehensive error handling and timeouts

## Future Enhancements

- [ ] Support for multiple browser tabs
- [ ] Screenshot capture command
- [ ] Cookie and localStorage manipulation
- [ ] Network request interception
- [ ] File upload/download support
- [ ] Browser automation sequences
- [ ] Extension settings UI
- [ ] Command history and logging
- [ ] Rate limiting and queue management
- [ ] Support for Firefox native messaging
