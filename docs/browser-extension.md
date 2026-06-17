---
icon: material/puzzle
---

# Browser Extension

The Gobbler browser extension enables bidirectional communication between Gobbler and your browser, allowing extraction of authenticated content and browser automation.

## Features

- Extract current page content (works with authenticated sessions)
- Extract with CSS selectors
- Navigate pages programmatically
- Execute JavaScript in browser tabs
- Control AI chat interfaces (NotebookLM, Claude.ai, ChatGPT, Gemini)

## Installation

### 1. Load Extension in Chrome

1. Open Chrome and go to `chrome://extensions/`
2. Enable **Developer mode** (toggle in top right)
3. Click **Load unpacked**
4. Select the `browser-extension` directory from the Gobbler repo

### 2. Create Gobbler Tab Group

1. Right-click any tab you want to control
2. Select **Add to group** → **New group**
3. Name the group exactly **"Gobbler"**

Only tabs in the "Gobbler" group can be controlled by Gobbler (security feature).

### 3. Verify Connection

```bash
gobbler browser status
```

With the extension loaded and connected, this should show `1 browser extension(s) connected`. Without the extension connected, expect `No browser extension connected`.

## How It Works

```
Your Browser (with real sessions)
        ↓
Gobbler Extension (extracts HTML)
        ↓
WebSocket to Relay Server (localhost:4625)
        ↓
Gobbler CLI / Relay Server
        ↓
Response with markdown
```

## Advantages

- Uses your real browser session (no cookie copying)
- Uses your real browser session without copying cookies
- Can access pages you are already authenticated to when those tabs are intentionally placed in the Gobbler tab group
- Full JavaScript execution capability

Sites may still rate-limit, block, or detect automated behavior. Use browser automation only on pages the user explicitly asks to use.

## Security Model

**Tab Group Isolation**: Only tabs in the "Gobbler" tab group are accessible. This prevents accidental access to sensitive tabs (banking, email, etc.).

To add a tab to the group:
1. Right-click the tab
2. Select "Add to group" → "Gobbler"

To remove a tab:
1. Right-click the tab
2. Select "Remove from group"

## CLI Commands

### Check Status

```bash
gobbler browser status
```

### List Controlled Tabs

```bash
gobbler browser list

# Filter by page type
gobbler browser list --filter notebooklm
gobbler browser list --filter claude

# JSON output for scripting
gobbler browser list --json
```

### Open URLs in Gobbler Tab Group

```bash
# Open URLs in Gobbler tab group
gobbler browser open "https://example.com"
gobbler browser open "url1" "url2" "url3"
```

### Extract Page

```bash
# Full page
gobbler browser extract -o page.md

# With selector (experimental)
gobbler browser extract --selector "article.content" -o article.md
```

### Navigate

```bash
gobbler browser navigate "https://example.com"
```

### Execute JavaScript

```bash
gobbler browser exec "document.title"
gobbler browser exec "document.querySelectorAll('h1').length"
```

## Troubleshooting

### Extension won't load

- Make sure icon files exist in `icons/` directory
- Check Chrome extension errors at `chrome://extensions/`

### "No browser extension connected"

1. Verify extension is installed and enabled
2. Check extension popup shows "Connected"
3. Restart the relay: `gobbler relay restart`

### "No tabs found"

1. Open the page you want to control
2. Right-click tab → "Add to group" → "Gobbler"
3. Run `gobbler browser list`

### Commands timeout

- Increase timeout: `--timeout 60`
- Check browser tab is active
- Verify page has loaded completely

## Development

The extension consists of:

| File | Purpose |
|------|---------|
| `manifest.json` | Extension configuration |
| `popup.html/js` | Extension popup UI |
| `content.js` | Content script for page interaction |
| `background.js` | Service worker for WebSocket |
| `page-apis/*.js` | Site-specific APIs (NotebookLM, Claude, etc.) |
