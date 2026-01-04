---
icon: material/google-chrome
---

# Browser Control

Control the browser via the Gobbler CLI and browser extension.

**Requires**: 

- Gobbler browser extension installed
- Target tabs in "Gobbler" tab group
- Relay server (auto-starts when needed)

## Quick Start

```bash
# Check browser connection
gobbler browser status

# List tabs in Gobbler group
gobbler browser list

# Extract current page to markdown
gobbler browser extract -o page.md
```

## CLI Commands

### Check Status

```bash
gobbler browser status
```

Shows relay status and number of connected extensions.

### List Tabs

```bash
# All tabs in Gobbler group
gobbler browser list

# Filter by site
gobbler browser list --filter notebooklm
gobbler browser list --filter claude
```

### Open URLs

```bash
# Open one or more URLs in Gobbler tab group
gobbler browser open "https://example.com"
gobbler browser open "https://example.com" "https://google.com"
```

### Navigate Current Tab

```bash
gobbler browser navigate "https://example.com"
```

### Extract Page Content

```bash
# Full page as markdown
gobbler browser extract

# Save to file
gobbler browser extract -o page.md

# With CSS selector
gobbler browser extract --selector "article.content"

# From specific tab
gobbler browser extract --tab 1234567890

# JSON output
gobbler browser extract --json
```

### Execute JavaScript

```bash
# In active tab
gobbler browser exec "document.title"

# In specific tab
gobbler browser exec "document.title" --tab 1234567890

# JSON output
gobbler browser exec "document.title" --json

# With timeout
gobbler browser exec "await fetch('/api').then(r => r.json())" --timeout 30
```

## Prerequisites

1. **Browser extension** - Load `browser-extension/` folder in Chrome
2. **Target tabs** in a tab group named "Gobbler"
3. **Relay server** - Auto-starts with commands

### Installing the Extension

1. Open Chrome and go to `chrome://extensions/`
2. Enable "Developer mode" (toggle in top right)
3. Click "Load unpacked"
4. Select the `browser-extension` directory

### Adding Tabs to Gobbler Group

1. Right-click any tab
2. Select "Add to group" → "Gobbler"
3. If "Gobbler" doesn't exist, create a new group and name it "Gobbler"

## Troubleshooting

### "Relay not running"

```bash
gobbler relay start
gobbler relay status
```

### "No browser extension connected"

1. Ensure Gobbler extension is installed in Chrome/Edge
2. Check extension popup shows "Connected" 
3. Verify target tabs are in the "Gobbler" tab group

### "No tabs found"

1. Open the page you want to control
2. Right-click the tab → "Add to group" → "Gobbler"
3. Run `gobbler browser list` again

## Related Integrations

For site-specific automation:

- [NotebookLM](notebooklm.md) - Query NotebookLM notebooks
- [Claude.ai](claude.md) - Chat with Claude.ai
- [ChatGPT](chatgpt.md) - Chat with ChatGPT
- [Gemini](gemini.md) - Chat with Google Gemini
