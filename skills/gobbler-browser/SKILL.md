---
name: gobbler-browser
description: Control browser via Gobbler extension - navigate pages, execute JavaScript, extract content, and interact with NotebookLM. Use when user wants to interact with their browser, extract current page content, or use NotebookLM.
version: 2.0.0
---

# Gobbler Browser

Control the browser via the Gobbler browser extension and relay server.

**Requires**: Gobbler browser extension connected, daemon running

---

## Quick Start

```bash
# 1. Start the daemon (includes relay server)
gobbler daemon start

# 2. Check browser connection
curl http://localhost:4625/health
```

---

## Browser Commands

### List Tabs

```bash
curl http://localhost:4625/api/tabs
```

### Navigate to URL

```bash
curl -X POST http://localhost:4625/api/navigate \
  -H "Content-Type: application/json" \
  -d '{"url": "https://example.com"}'
```

### Extract Current Page Content

```bash
# Full page
curl http://localhost:4625/api/extract

# With CSS selector
curl "http://localhost:4625/api/extract?selector=article.content"
```

### Execute JavaScript

```bash
curl -X POST http://localhost:4625/api/execute \
  -H "Content-Type: application/json" \
  -d '{"script": "document.title"}'
```

---

## Python SDK

```python
from gobbler_sdk import GobblerClient

client = GobblerClient()

# List browser tabs
tabs = client.browser.list_tabs()

# Navigate
client.browser.navigate("https://example.com")

# Extract page content
content = client.browser.extract()
content = client.browser.extract(selector="article.content")

# Execute JavaScript
result = client.browser.execute("document.title")
```

---

## NotebookLM Integration

See the [notebooklm skill](../notebooklm/SKILL.md) for NotebookLM-specific commands.

### Quick NotebookLM Commands

```bash
# Query NotebookLM
curl -X POST http://localhost:4625/api/notebooklm/query \
  -H "Content-Type: application/json" \
  -d '{"query": "What are the key points?"}'

# Get last response
curl http://localhost:4625/api/notebooklm/last
```

---

## Troubleshooting

### "Cannot connect to localhost:4625"

```bash
# Check if daemon is running
gobbler daemon status

# Start daemon if not running
gobbler daemon start
```

### "No browser extension connected"

1. Ensure Gobbler extension is installed in Chrome/Arc
2. Check extension popup shows "Connected"
3. Verify target tabs are in the "Gobbler" tab group

### Check relay health

```bash
curl -s http://localhost:4625/health
```

---

## Prerequisites

1. **Gobbler daemon** running (`gobbler daemon start`)
2. **Browser extension** installed and showing "Connected"
3. **Target tabs** in the "Gobbler" tab group
