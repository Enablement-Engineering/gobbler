---
name: gobbler-browser
description: Controls browser via Gobbler extension for navigation, JavaScript execution, and content extraction. Includes NotebookLM, Claude.ai, ChatGPT, Gemini integrations. Triggers on browser extract, grab from tab, control browser, or AI chat service queries.
metadata:
  openclaw:
    emoji: 🔌
    requires:
      bins: [gobbler]
    install:
      - id: gobbler
        kind: script
        label: Install Gobbler (git clone + uv)
        script: |
          git clone https://github.com/Enablement-Engineering/gobbler.git ~/Projects/gobbler
          cd ~/Projects/gobbler && uv sync && uv tool install .
          echo "Load browser extension from ~/Projects/gobbler/browser-extension in Chrome"
    homepage: https://github.com/Enablement-Engineering/gobbler
---

# Gobbler Browser

Control the browser via the Gobbler CLI and browser extension. Includes integrations for AI chat services.

**Requires**: 
- Gobbler browser extension installed
- Target tabs in the specific extension-managed group ID
- Local relay; most browser operations auto-start it, but `browser status` does not

> **Note**: AI chat integrations (NotebookLM, Claude, ChatGPT, Gemini) use DOM automation and may break when sites update their UI.

---

## Quick Start

```bash
# Check browser connection
gobbler relay start
gobbler browser status

# List tabs in Gobbler group
gobbler browser list

# Re-inject page APIs if automatic injection did not occur
gobbler browser inject

# Extract current page to markdown
gobbler browser extract -o page.md
```

---

## Core Browser Commands

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
gobbler browser list --filter chatgpt
gobbler browser list --filter gemini

# JSON output
gobbler browser list --json
```

### Inject APIs

Inject page-specific APIs into matching tabs in the Gobbler group. The extension normally injects on matching grouped tabs and navigation; use this command after browser/extension reload or when automatic injection did not occur.

```bash
gobbler browser inject
```

### Open URLs

```bash
# Open one or more URLs in Gobbler tab group
gobbler browser open "https://example.com"
gobbler browser open "https://example.com" "https://google.com"

# Read URLs from file
gobbler browser open -f urls.txt
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
```

### Execute JavaScript

```bash
# In active tab
gobbler browser exec "document.title"

# In specific tab
gobbler browser exec "document.title" --tab 1234567890

# With timeout
gobbler browser exec "fetch('/api').then(r => r.json())" --timeout 30
```

---

# AI Chat Integrations

These integrations use browser DOM automation to interact with AI chat services. They share common patterns and prerequisites.

> **Fragility Warning**: These integrations depend on CSS selectors and DOM structure that may change when sites update. If commands stop working, check for extension/skill updates.

## Common Prerequisites

1. **Browser extension installed** - Load `browser-extension/` folder in Chrome
2. **Tab authorized by extension** - Open the popup and click **Allow & Add** or **Add Tab**
3. **Relay available** - Start it before `browser status`; other operations normally auto-start it
4. **APIs injected** - Usually automatic; run `gobbler browser inject` as recovery

## CRITICAL: One Query at a Time

**Send only ONE query at a time to each conversation, then WAIT for the response.**

Why? The query command waits for the "last message" in the chat. If you send multiple queries in parallel:
- All questions get submitted
- The first query's script may return the WRONG answer (from a later question)
- You get mismatched question/answer pairs

```bash
# CORRECT - Sequential
gobbler notebooklm query "Question 1" --timeout 120
# Wait for response, then:
gobbler notebooklm query "Question 2" --timeout 120

# WRONG - Parallel (will get mismatched answers)
gobbler notebooklm query "Question 1" &
gobbler notebooklm query "Question 2" &
```

## Common Workflow

All AI chat integrations follow this pattern:

```bash
# 1. Ensure APIs are present; manually inject after extension/browser reload if needed
gobbler browser inject

# 2. List available tabs
gobbler <service> list

# 3. Send query and get response (waits for complete answer)
gobbler <service> query "Your question here" --timeout 120

# 4. If response looks incomplete, get full last response
gobbler <service> last
```

---

## NotebookLM Integration

Query Google NotebookLM notebooks through browser automation.

### Commands

```bash
# List NotebookLM tabs
gobbler notebooklm list

# Send query and wait for response
gobbler notebooklm query "What are the main themes?" --timeout 120

# Target specific notebook by tab ID
gobbler notebooklm query "Summarize" --tab 1700453262

# Get last response (use if output looks truncated)
gobbler notebooklm last

# Get chat history
gobbler notebooklm history           # Last 5 messages
gobbler notebooklm history -n 10     # Last 10 messages
gobbler notebooklm history --all     # All messages

# Get notebook metadata
gobbler notebooklm info
```

### Options
- `--timeout SECONDS` - Max wait time (default: 150)
- `-t/--tab TAB_ID` - Target specific tab

### Tips
- Be specific: "What does source X say about Y?" works better than vague questions
- Ask for citations: Add "with citations" to get source references
- One topic per query: Break complex questions into focused queries

---

## Claude.ai Integration

Send messages to Claude.ai conversations through browser automation.

### Commands

```bash
# List Claude.ai tabs
gobbler claude list

# Send message and wait for response
gobbler claude query "Explain quantum computing" --timeout 150

# Target specific conversation by tab ID
gobbler claude query "Continue our discussion" -t 1234567

# Get last response
gobbler claude last

# Get chat history
gobbler claude history           # Last 10 messages
gobbler claude history -n 20     # Last 20 messages
gobbler claude history --all     # All messages

# Get conversation metadata
gobbler claude info
```

### Options
- `--timeout SECONDS` - Max wait time (default: 150)
- `-t/--tab TAB_ID` - Target specific tab
- `-n/--count NUMBER` - Number of messages for history

---

## ChatGPT Integration

Send messages to ChatGPT conversations through browser automation.

### Commands

```bash
# List ChatGPT tabs
gobbler chatgpt list

# Send message and wait for response
gobbler chatgpt query "Explain machine learning" --timeout 150

# Target specific conversation by tab ID
gobbler chatgpt query "Continue" -t 1234567

# Get last response
gobbler chatgpt last

# Get chat history
gobbler chatgpt history           # Last 10 messages
gobbler chatgpt history -n 20     # Last 20 messages
gobbler chatgpt history --all     # All messages

# Get conversation metadata
gobbler chatgpt info

# Download DALL-E images from last response
gobbler chatgpt download -o ./images
```

### Options
- `--timeout SECONDS` - Max wait time (default: 150)
- `-t/--tab TAB_ID` - Target specific tab
- `-n/--count NUMBER` - Number of messages for history
- `-o/--output DIR` - Output directory for image downloads

---

## Gemini Integration

Send messages to Google Gemini conversations through browser automation.

### Commands

```bash
# List Gemini tabs
gobbler gemini list

# Send message and wait for response
gobbler gemini query "Explain neural networks" --timeout 150

# Target specific conversation by tab ID
gobbler gemini query "Continue" -t 1234567

# Get last response
gobbler gemini last

# Get chat history
gobbler gemini history           # Last 10 messages
gobbler gemini history -n 20     # Last 20 messages
gobbler gemini history --all     # All messages

# Get conversation metadata
gobbler gemini info

# Download images from last response
gobbler gemini download -o ./images
```

### Options
- `--timeout SECONDS` - Max wait time (default: 150)
- `-t/--tab TAB_ID` - Target specific tab
- `-n/--count NUMBER` - Number of messages for history
- `-o/--output DIR` - Output directory for image downloads

### Notes
- Gemini requires a Google account
- Check regional availability if you get errors

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
2. Use **Allow & Add** or **Add Tab** in the extension popup
3. Run `gobbler browser list` again

### "API not injected" / Commands not working

1. Run `gobbler browser inject`
2. If still failing, reload the extension in chrome://extensions
3. Refresh the target page
4. Run `gobbler browser inject` again

### Timeout errors

Increase the timeout for complex responses:

```bash
gobbler <service> query "Complex question" --timeout 300
```

### Truncated responses

Use the `last` command to get the full response:

```bash
gobbler <service> last
```

### Garbled/wrong responses

You probably sent parallel queries. STOP. Wait for each query to complete before sending the next.

---

## Troubleshooting Checklist

| Issue | Check | Fix |
|-------|-------|-----|
| No tabs found | Tab added through the extension? | Use **Allow & Add** or **Add Tab** in the popup |
| API not injected | Extension reloaded? | Reload extension, refresh page, `gobbler browser inject` |
| Not connected | Extension loaded? | chrome://extensions → Load unpacked |
| Relay error | Relay running? | `gobbler relay start` |
| Timeout | Response too long? | Increase `--timeout` |
| Truncated | Terminal limit | Run `gobbler <service> last` |
| Garbled response | Parallel queries? | Query ONE at a time, wait for response |

---

## Prerequisites

1. **Browser extension** installed (load `browser-extension/` folder)
2. **Target tabs** in the extension-managed group; use the popup for first-time origin permission
3. **Relay server** running; start with `gobbler relay start` if needed
