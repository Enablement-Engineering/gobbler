---
icon: material/puzzle
---

# Browser Extension

The Gobbler browser extension enables bidirectional communication between Gobbler and your
browser for intentionally selected tabs. It can extract authenticated pages when those pages are
already open in the browser and have been added to the Gobbler tab group.

## Features

- Extract current page content (works with authenticated sessions)
- Extract with CSS selectors
- Navigate selected Gobbler tabs programmatically
- Execute JavaScript in selected Gobbler tabs
- Control AI chat interfaces (NotebookLM, Claude.ai, ChatGPT, Gemini)

## Installation

### 1. Load the unpacked extension

1. Open Chrome, Brave, Edge, or another Chromium browser and go to `chrome://extensions/`
2. Enable **Developer mode** (toggle in top right)
3. Click **Load unpacked**
4. Select the `browser-extension` directory from the Gobbler repo

### 2. Authorize and add a tab

1. Open a harmless page such as `https://example.com`.
2. Open the Gobbler extension popup.
3. Click **Allow & Add** (first use for an origin) or **Add Tab**.

The extension creates and remembers its own tab group. Authorization uses the stored group ID, not
the visible group title. Manually creating or renaming another group to "Gobbler" does not authorize
its tabs.

### 3. Verify the connection

```bash
gobbler relay start
gobbler browser status
```

`browser status` is intentionally read-only and does not start the relay. Most other browser operations auto-start it on `127.0.0.1:4625`. With the extension connected, status reports the connection count. Without it, expect `No browser extension connected`.

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
- Can access pages you are already authenticated to when those tabs are intentionally placed in the Gobbler tab group
- JavaScript execution in selected Gobbler tabs

The extension does not bypass site access controls or bot detection. Sites may still rate-limit,
block, or detect automated behavior. Use browser automation only on pages the user explicitly asks
to use.

The popup's configurable **Server URL** applies to its HTTP extraction requests. CLI automation uses
the extension's WebSocket connection, which is currently fixed to `ws://localhost:4625/ws`; custom
relay host/port values do not reconfigure that extension WebSocket.

## Security Model

**Extension-managed group isolation**: Only tabs in the extension's stored group are accessible. This prevents accidental access to unrelated tabs.

Site-origin permissions gate scripting-based extraction and page-API injection. They do not gate debugger-based `browser exec`, which only checks membership in the stored group before attaching the debugger.

For a new origin, use **Allow & Add** in the popup so Chrome can display the permission request. After permission has already been granted for that origin, **Add Tab** or the Gobbler context-menu action can add it to the managed group. The context menu cannot request a new origin permission.

To remove a tab:
1. Right-click the tab
2. Select "Remove from group"

Do not submit forms, send messages, or take account-changing actions unless the user explicitly
requests that action.

`gobbler browser exec` uses Chrome's debugger permission to evaluate JavaScript. Chrome may show a
debugging banner, and the debugger attachment can remain until the tab closes or the relay
disconnects. Treat `browser exec` as arbitrary page-side-effect capability, not read-only extraction.

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

# With selector
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
2. Use **Allow & Add** or **Add Tab** in the extension popup
3. Run `gobbler browser list`

### Commands timeout

- `browser exec` awaits a returned Promise and supports `--timeout`; for example, `gobbler browser exec "slowOperation()" --timeout 60`. Do not use a bare top-level `await`, which is invalid in this evaluation context.
- `browser extract` does not currently expose a timeout option
- Check browser tab is active
- Verify page has loaded completely

## Validation Coverage

Automated tests cover the extension pieces that can run reliably in CI without launching Chrome:

- Manifest wiring, local assets, popup script order, and conservative default host permissions.
- Page API registry metadata and references to extension-local scripts.
- Relay command names shared by `gobbler_relay.client` and `background.js`.
- WebSocket registration, ping/pong, and command response envelope shape.
- Static tab-group guards on commands that read, navigate, inject into, or execute scripts in tabs.
- Extraction payload serialization to the relay `/extract` endpoint.

Manual validation is still required for browser behavior that depends on Chrome and third-party
pages:

- Load `browser-extension/` in Chrome, start `gobbler relay start`, and confirm
  `gobbler browser status` reports one connected extension.
- Add a harmless page such as `https://example.com` to the Gobbler tab group, then run
  `gobbler browser list` and `gobbler browser extract --selector "body" -o example.md`.
- Keep a second tab outside the Gobbler group and verify extraction or script execution is rejected.
- On authenticated pages, only use tabs intentionally added to the Gobbler group. Prefer read-only
  checks first, such as `gobbler browser exec "document.title"`.
- For NotebookLM, Claude.ai, ChatGPT, or Gemini pages, verify API injection only after the relevant
  tab is in the Gobbler group. Do not submit prompts or forms unless that is the explicit test.

## Development

The extension consists of:

| File | Purpose |
|------|---------|
| `manifest.json` | Extension configuration |
| `popup.html/js` | Extension popup UI |
| `content.js` | Content script for page interaction |
| `background.js` | Service worker for WebSocket |
| `page-apis/*.js` | Site-specific APIs (NotebookLM, Claude, etc.) |
