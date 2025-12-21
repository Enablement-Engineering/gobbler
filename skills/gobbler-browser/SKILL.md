---
name: gobbler-browser
description: Control browser via Gobbler extension - navigate pages, execute JavaScript, extract content, and interact with NotebookLM. Use when user wants to interact with their browser, extract current page content, or use NotebookLM.
version: 1.0.0
---

# Gobbler Browser

Control the browser via the Gobbler browser extension. Enables navigation, JavaScript execution, content extraction, and NotebookLM interactions.

**Requires**: Gobbler browser extension connected on port 4625

---

## Step 0: Quick Verification (Try This First!)

Before any setup, check if things are already working:

**Claude Code:**
```bash
curl -s http://localhost:4625/health && echo " ← Relay OK"
uv run skills/gobbler-browser/scripts/browser_api.py tabs
```

**Claude Desktop:**
```bash
osascript -e 'do shell script "curl -s http://localhost:4625/health"'
```

**If both commands work** → Skip to "Step 4: Usage Commands"

**If they fail** → Continue to Step 1 below

---

## Step 1: Detect Your Environment

Run this command to determine which environment you're in:

```bash
echo $HOME
```

| Result | Environment | What to Use |
|--------|-------------|-------------|
| `/Users/...` | **Claude Code** | Direct bash commands |
| `/root` | **Claude Desktop (Sandbox)** | AppleScript wrapper for ALL commands |

**If you're in Claude Desktop (sandbox)**: You CANNOT access `localhost` directly. Every command must be wrapped in `osascript` to execute on the host macOS.

**IMPORTANT**: For commands with user input (like queries), use AppleScript's `quoted form` for reliable escaping:
```applescript
set userInput to "What's the \"key\" concept?"
do shell script "/path/to/command " & quoted form of userInput
```
This automatically handles quotes, apostrophes, and special characters. Never manually escape quotes.

---

## Step 2: Find Your Paths (Claude Desktop Only)

If you're in the sandbox, you need to find the paths on the host:

### Find uv binary:
```bash
osascript -e 'do shell script "which uv 2>/dev/null || echo /opt/homebrew/bin/uv"'
```

Common locations:
- `/opt/homebrew/bin/uv` (Homebrew on Apple Silicon)
- `/usr/local/bin/uv` (Homebrew on Intel)
- `~/.local/bin/uv` (pip/pipx install)
- `~/.cargo/bin/uv` (cargo install)

### Find Gobbler installation:
```bash
osascript -e 'do shell script "find /Users -maxdepth 4 -type d -name gobbler 2>/dev/null | head -3"'
```

---

## Step 3: Start the Relay

The relay server bridges HTTP requests to the browser extension.

### Claude Code:
```bash
cd /path/to/gobbler
uv run src/gobbler_relay/relay.py --daemon
```

### Claude Desktop:
```bash
osascript -e 'do shell script "/opt/homebrew/bin/uv run /Users/USERNAME/Projects/gobbler/src/gobbler_relay/relay.py --daemon"'
```

> **Note**: Replace `/opt/homebrew/bin/uv` and `/Users/USERNAME/Projects/gobbler` with your actual paths from Step 2.

---

## Step 4: Verify Connection

### Claude Code:
```bash
uv run skills/gobbler-browser/scripts/browser_api.py check
```

### Claude Desktop:
```bash
osascript -e 'do shell script "/opt/homebrew/bin/uv run /Users/USERNAME/Projects/gobbler/skills/gobbler-browser/scripts/browser_api.py check"'
```

Expected output: `Browser extension is connected (1 connection(s))`

---

## Step 5: Usage Commands

All commands below show BOTH formats. Use the one matching your environment.

### List Tabs

**Claude Code:**
```bash
uv run skills/gobbler-browser/scripts/browser_api.py tabs
```

**Claude Desktop:**
```bash
osascript -e 'do shell script "/opt/homebrew/bin/uv run /Users/USERNAME/Projects/gobbler/skills/gobbler-browser/scripts/browser_api.py tabs"'
```

### Navigate to URL

**Claude Code:**
```bash
uv run skills/gobbler-browser/scripts/browser_api.py navigate "https://example.com"
```

**Claude Desktop:**
```bash
osascript -e 'do shell script "/opt/homebrew/bin/uv run /Users/USERNAME/Projects/gobbler/skills/gobbler-browser/scripts/browser_api.py navigate \"https://example.com\""'
```

### Extract Current Page

**Claude Code:**
```bash
uv run skills/gobbler-browser/scripts/browser_api.py extract

# With CSS selector
uv run skills/gobbler-browser/scripts/browser_api.py extract --selector "article.content"
```

**Claude Desktop:**
```bash
osascript -e 'do shell script "/opt/homebrew/bin/uv run /Users/USERNAME/Projects/gobbler/skills/gobbler-browser/scripts/browser_api.py extract"'

# With CSS selector
osascript -e 'do shell script "/opt/homebrew/bin/uv run /Users/USERNAME/Projects/gobbler/skills/gobbler-browser/scripts/browser_api.py extract --selector \"article.content\""'
```

### Execute JavaScript

**Claude Code:**
```bash
uv run skills/gobbler-browser/scripts/browser_api.py execute "document.title"
```

**Claude Desktop:**
```bash
osascript -e 'do shell script "/opt/homebrew/bin/uv run /Users/USERNAME/Projects/gobbler/skills/gobbler-browser/scripts/browser_api.py execute \"document.title\""'
```

---

## NotebookLM Commands

For NotebookLM-specific interactions, see the [notebooklm skill](../notebooklm/SKILL.md) or use these commands:

### Query NotebookLM

**Claude Code:**
```bash
uv run skills/gobbler-browser/scripts/notebooklm.py query "What are the key points?"
```

**Claude Desktop:**
```bash
osascript -e 'do shell script "/opt/homebrew/bin/uv run /Users/USERNAME/Projects/gobbler/skills/gobbler-browser/scripts/notebooklm.py query \"What are the key points?\""'
```

### Get Last Response

**Claude Code:**
```bash
uv run skills/gobbler-browser/scripts/notebooklm.py last
```

**Claude Desktop:**
```bash
osascript -e 'do shell script "/opt/homebrew/bin/uv run /Users/USERNAME/Projects/gobbler/skills/gobbler-browser/scripts/notebooklm.py last"'
```

---

## Troubleshooting

### "Cannot connect to localhost:4625"

| If you're in... | Solution |
|-----------------|----------|
| Claude Code | Start relay: `uv run src/gobbler_relay/relay.py --daemon` |
| Claude Desktop | You're in a sandbox! Use osascript for ALL commands |

### "command not found: uv"

Use full path to uv binary:
```bash
# Find it first
osascript -e 'do shell script "which uv || find /opt/homebrew -name uv 2>/dev/null | head -1"'

# Then use full path in commands
osascript -e 'do shell script "/opt/homebrew/bin/uv run ..."'
```

### "No browser extension connected"

1. Ensure Gobbler extension is installed in Chrome/Arc
2. Check extension popup shows "Connected"
3. Verify target tabs are in the "Gobbler" tab group

### Test connectivity directly (fallback)

If Python scripts aren't working, test the relay directly:

**Claude Code:**
```bash
curl -s http://localhost:4625/health
```

**Claude Desktop:**
```bash
osascript -e 'do shell script "curl -s http://localhost:4625/health"'
```

### "Address already in use" on port 4625

This actually means the relay IS already running. Verify with the health check above.

---

## Prerequisites Summary

1. **Gobbler browser extension** installed and showing "Connected"
2. **Relay server** running on port 4625
3. **Target tabs** in the "Gobbler" tab group
4. **For Claude Desktop**: Know your uv and Gobbler paths
