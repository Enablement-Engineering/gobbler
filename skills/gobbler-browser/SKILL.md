---
name: gobbler-browser
description: Control browser via Gobbler extension - navigate pages, execute JavaScript, extract content, open tabs. Use when user wants to interact with their browser or extract current page content.
version: 2.1.0
---

# Gobbler Browser

Control the browser via the Gobbler CLI and browser extension.

**Requires**: 
- Gobbler browser extension installed
- Target tabs in "Gobbler" tab group
- Relay server (auto-starts when needed)

---

## Quick Start

```bash
# Inject APIs into all Gobbler tabs (required for ChatGPT/Claude/Gemini/NotebookLM)
gobbler browser inject

# Check browser connection
gobbler browser status

# List tabs in Gobbler group
gobbler browser list

# Extract current page to markdown
gobbler browser extract -o page.md
```

---

## CLI Commands

### Inject APIs

Inject page-specific APIs into all tabs in the Gobbler group. **Required** before using ChatGPT, Claude, Gemini, or NotebookLM commands (especially after page refresh or extension reload).

```bash
# Inject APIs into all Gobbler tabs
gobbler browser inject
```

This command:
- Scans all tabs in the Gobbler group
- Injects the appropriate API (ChatGPT, Claude, Gemini, NotebookLM) based on URL
- Shows which APIs were injected or already present

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

# JSON output
gobbler browser list --json
```

### Open URLs

```bash
# Open one or more URLs in Gobbler tab group
gobbler browser open "https://example.com"
gobbler browser open "https://example.com" "https://google.com"

# Read URLs from file
gobbler browser open -f urls.txt

# Read from stdin
cat urls.txt | gobbler browser open -f -

# JSON output
gobbler browser open "https://example.com" --json
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

---

## Related Integrations

For site-specific automation, see:
- [gobbler-notebooklm skill](../gobbler-notebooklm/SKILL.md) - Query NotebookLM notebooks
- [gobbler-claude skill](../gobbler-claude/SKILL.md) - Chat with Claude.ai

---

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

---

## Prerequisites

1. **Browser extension** installed (load `browser-extension/` folder)
2. **Target tabs** in a tab group named "Gobbler"
3. **Relay server** running (auto-starts with commands)
