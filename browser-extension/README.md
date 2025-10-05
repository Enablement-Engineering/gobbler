# Gobbler Browser Extension

Extract authenticated web content directly from your browser and send it to Gobbler for markdown conversion.

## Features

- ✅ Extract current page content (works with authenticated sessions)
- ✅ Extract with CSS selectors
- ✅ Send to Gobbler MCP for markdown conversion
- ✅ Copy markdown to clipboard
- 🚧 Send to Claude Code (coming soon)

## Installation

### 1. Create Icon Files

The extension needs icon files. Create simple 16x16, 48x48, and 128x128 PNG files or use these commands to create placeholders:

```bash
# On macOS with ImageMagick
convert -size 16x16 xc:#0066cc icons/icon16.png
convert -size 48x48 xc:#0066cc icons/icon48.png
convert -size 128x128 xc:#0066cc icons/icon128.png
```

Or just create any PNG files and name them appropriately.

### 2. Load Extension in Chrome

1. Open Chrome and go to `chrome://extensions/`
2. Enable "Developer mode" (toggle in top right)
3. Click "Load unpacked"
4. Select the `browser-extension` directory

### 3. Start Gobbler Server

Make sure Gobbler MCP is running:

```bash
cd /Users/dylanisaac/Projects/gobbler
uv run gobbler-mcp
```

The HTTP server will start on `http://localhost:8080` by default.

## Usage

### Basic Page Extraction

1. Navigate to any webpage (e.g., YouTube Watch Later)
2. Click the Gobbler extension icon
3. Click "Extract Current Page"
4. Content will be converted to markdown
5. Click "Copy" to copy to clipboard

### Extract with Selector

1. Navigate to the page
2. Click the Gobbler extension icon
3. Click "Extract with Selector"
4. Enter a CSS selector (e.g., `ytd-playlist-video-renderer`, `article`, `.main-content`)
5. Content will be extracted and converted

### Extract YouTube Watch Later

1. Open YouTube and make sure you're logged in
2. Go to https://www.youtube.com/playlist?list=WL
3. Click Gobbler extension
4. Use selector: `ytd-playlist-video-renderer` to get video titles
5. Or extract the full page

## Configuration

- **Server URL**: Change in extension popup if Gobbler is running on a different port

## How It Works

```
Your Browser (with real sessions)
        ↓
Gobbler Extension (extracts HTML)
        ↓
HTTP POST to localhost:8080/extract
        ↓
Gobbler HTTP Server (converts to markdown)
        ↓
Response with markdown
        ↓
Display in extension popup
```

## Advantages Over Cookie Export

- ✅ Uses your real browser session (no cookie copying)
- ✅ No bot detection (it's your actual browser)
- ✅ Works with 2FA, private content, etc.
- ✅ Simple and fast

## Development

The extension consists of:

- `manifest.json` - Extension configuration
- `popup.html` - Extension popup UI
- `popup.js` - Popup logic and API calls
- `content.js` - Content script (minimal)
- `background.js` - Service worker

## Troubleshooting

**Extension won't load:**
- Make sure icon files exist in `icons/` directory
- Check Chrome extension errors in `chrome://extensions/`

**"Failed to fetch" error:**
- Make sure Gobbler MCP server is running
- Check server URL in extension popup (default: http://localhost:8080)
- Check browser console for CORS errors

**No content extracted:**
- Try using a more specific CSS selector
- Check if page has loaded completely
- Some dynamic content may require waiting

## Future Features

- [ ] Batch extraction (multiple tabs)
- [ ] Auto-extract on page load
- [ ] Direct integration with Claude Code
- [ ] Save extractions to files
- [ ] Custom extraction templates
