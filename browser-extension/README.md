# Gobbler browser extension

This unpacked Chromium extension connects intentionally selected tabs to Gobbler's local relay. It supports generic extraction/navigation/JavaScript commands and page-specific automation for NotebookLM, Claude.ai, ChatGPT, and Gemini.

## Install

1. Install Gobbler from the repository root and verify `gobbler --version`.
2. Open `chrome://extensions/` in Chrome, Brave, Edge, or another Chromium browser.
3. Enable **Developer mode**.
4. Select **Load unpacked** and choose this `browser-extension/` directory.
5. Open a harmless page such as `https://example.com`.
6. Open the extension popup and click **Allow & Add** or **Add Tab**.
7. Verify:

```bash
gobbler relay start
gobbler browser status
gobbler browser list
```

Use the popup for first-time access to an origin because Chrome only permits the permission prompt from that user gesture. The context-menu add action works only after that origin permission already exists.

The icon assets are already committed under `icons/`; no generation step is required.

## Relay lifecycle

Most browser operations auto-start the relay on `127.0.0.1:4625`; `browser status` deliberately does not.

```bash
gobbler relay status
gobbler relay start
gobbler relay restart
```

Use `gobbler browser --no-auto-start status` only when debugging lifecycle behavior.

## CLI examples

```bash
# Generic grouped-tab operations
gobbler browser list --json
gobbler browser open "https://example.com"
gobbler browser navigate "https://example.org"
gobbler browser extract --selector article -o article.md
gobbler browser exec "document.title" --json

# Inject matching page APIs after browser/extension reload
gobbler browser inject
gobbler browser inject --tab TAB_ID --json

# Site-specific integrations
gobbler notebooklm list
gobbler notebooklm query "Summarize the notebook"
gobbler claude query "Draft a concise answer"
gobbler chatgpt query "Describe the current conversation"
gobbler gemini query "Compare the visible sources"
```

## Security model

Extension command guards compare each tab's group ID with the stored `gobblerGroupId`. A different group with the same title does not match, but manually moving a tab into the existing managed group makes it eligible. Site-origin permissions gate scripting-based extraction and page-API injection; debugger-based `browser exec` only checks group eligibility. This is a scope boundary, not a permission bypass:

- The extension uses the browser's existing authenticated session.
- It does not copy cookies into Gobbler.
- It does not bypass authentication, access controls, rate limits, or bot detection.
- `browser exec` runs arbitrary JavaScript in a selected grouped tab.
- `browser exec` uses Chrome's debugger permission; Chrome may show a debugging banner and the attachment can persist until tab close or relay disconnect.
- Do not read private content or submit forms/messages unless the user explicitly requested that action.
- Remove sensitive tabs from the Gobbler group when they are no longer needed.

## Architecture

```text
Gobbler CLI
    ↕ HTTP/WebSocket on 127.0.0.1:4625
Gobbler relay
    ↕ WebSocket
extension service worker (background.js)
    ↕ Chrome extension APIs
content.js and page-apis/*.js in grouped tabs
```

The popup POSTs extraction requests to its configurable Server URL. CLI automation uses the extension WebSocket, currently fixed to `ws://localhost:4625/ws`; changing the popup URL or starting the relay on another port does not change that WebSocket endpoint.

## Files

- `manifest.json`: Manifest V3 permissions, content scripts, service worker, and extension assets.
- `background.js`: relay WebSocket, tab-group checks, command dispatch, and page API registry.
- `content.js`: page extraction bridge.
- `popup.html`, `popup.js`, `styles.css`: extension UI.
- `page-apis/*.js`: DOM adapters for supported AI chat sites.
- `vendor/`: extension-local dependencies; no CDN scripts are required at runtime.

## Troubleshooting

### Extension will not load

- Confirm every path in `manifest.json` exists.
- Inspect errors at `chrome://extensions/`.
- Reload the unpacked extension after source changes.

### No extension connected

```bash
gobbler relay restart
gobbler browser status
```

Then inspect the extension service-worker console for WebSocket errors.

### No tabs found

- Confirm the group name is exactly **Gobbler**.
- Confirm the target tab is inside that group.
- Run `gobbler browser list --json`.

### Generic browser command works but AI integration fails

The third-party site's DOM probably changed or the page API was not injected:

```bash
gobbler browser inject
gobbler browser exec "Object.keys(window).filter(k => k.startsWith('gobbler'))" --json
```

Inspect the page API in `page-apis/` and compare its selectors with the live page.

Full guide: <https://enablement-engineering.github.io/gobbler/browser-extension/>
