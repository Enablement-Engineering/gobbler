# NotebookLM integration

Gobbler controls an already open NotebookLM page through the Chromium extension and local relay. NotebookLM does not expose an official public API for this workflow; Gobbler uses DOM automation, so selectors can break when the site changes.

Prefer the CLI unless you are developing or debugging the injected page script.

## Requirements

1. Load `browser-extension/` as an unpacked Chromium extension.
2. Open a NotebookLM notebook.
3. Open the extension popup and click **Allow & Add** or **Add Tab** so the extension places it in its stored group.
4. Verify the relay and tab:

```bash
gobbler relay start
gobbler browser status
gobbler notebooklm list
```

NotebookLM operations normally auto-start the relay. `browser status` is read-only, so the explicit `relay start` above makes the verification sequence deterministic.

## CLI commands

```bash
# List NotebookLM tabs in the Gobbler group
gobbler notebooklm list

# Metadata for the active/matching notebook
gobbler notebooklm info

# Ask and wait for a response; default timeout is 150 seconds
gobbler notebooklm query "What are the main themes?"
gobbler notebooklm query "Summarize the sources" --timeout 240

# Read the latest response or chat history
gobbler notebooklm last
gobbler notebooklm history --count 10
gobbler notebooklm history --all
```

When several matching tabs exist, select one with `--tab TAB_ID` on commands that expose that option. Get IDs from `gobbler notebooklm list` or `gobbler browser list --json`.

## Injection

The extension maintains a registry of page APIs and automatically injects `browser-extension/page-apis/notebooklm.js` into matching authorized tabs on add, connection, startup, and page navigation. Manual injection is a recovery/developer step for direct `window.gobblerNotebookLM` use:

```bash
gobbler browser inject
gobbler browser inject --tab TAB_ID --json
```

The injected global is:

```javascript
window.gobblerNotebookLM
```

Its implementation version is currently `1.2.0`. Query it at runtime instead of copying the version into automation:

```bash
gobbler browser exec "window.gobblerNotebookLM?.version" --json
```

## Page API reference

The current object exposes these methods:

| Method | Purpose |
| --- | --- |
| `isNotebookPage()` | Check whether the URL contains a notebook route |
| `getNotebookInfo()` | Return title, URL, notebook ID, and route status |
| `getSources()` | Best-effort extraction of visible source entries |
| `getChatContent()` | Best-effort extraction of visible chat messages |
| `sendMessage(message)` | Fill the current chat input and submit without waiting |
| `waitForResponse(timeoutMs)` | Wait for a new response to stabilize |
| `ask(message, timeoutMs)` | Send and wait in one call; default 90 seconds in the page API |
| `generateAudioOverview()` | Best-effort click of an Audio Overview control |
| `getSelectedText()` | Return current page selection |
| `getPageStructure()` | Return debugging metadata about visible inputs, buttons, and regions |

Example direct call:

```bash
gobbler browser exec \
  "window.gobblerNotebookLM.ask('List the key claims', 120000)" \
  --timeout 130 --json
```

`browser exec` awaits a returned Promise. Do not prefix the expression with bare top-level `await`; Chrome evaluates it as a normal script rather than an ES module.

The CLI's `notebooklm query` timeout is expressed in **seconds**. The injected JavaScript API timeout is expressed in **milliseconds**.

## Response shapes

Page API methods return plain JavaScript objects. Successful `ask()` results normally include:

```json
{
  "success": true,
  "response": "...",
  "elapsed": 5200,
  "messageSentVia": "button-click",
  "totalElapsed": 5432
}
```

Timeouts can include `timedOut: true` and `partialResponse`. Treat all fields beyond `success`, `response`, and `error` as best-effort UI-automation metadata rather than a permanent public protocol.

## Limitations

- The selectors target NotebookLM's current DOM and can become stale.
- `getSources()` and `getChatContent()` inspect visible DOM; virtualized or collapsed content may be absent.
- Response completion uses new-message detection, DOM mutation observation, a 500 ms check interval, and a short stability window. A quiet partial response can occasionally look complete.
- `generateAudioOverview()` searches button text/labels heuristically and can click the wrong control if NotebookLM changes its UI.
- The extension does not bypass authentication, access controls, usage limits, or bot detection.

## Troubleshooting

### No NotebookLM tabs

```bash
gobbler browser list --filter notebooklm --json
```

Confirm the tab is in the **Gobbler** group and is on `https://notebooklm.google.com/...`.

### API missing after reload

```bash
gobbler browser inject
gobbler browser exec "Boolean(window.gobblerNotebookLM)" --json
```

### Query cannot find the input or response

1. Confirm `gobbler browser exec "document.title"` works.
2. Inspect the extension service-worker console and page console.
3. Use `getPageStructure()` for debugging:

```bash
gobbler browser exec \
  "window.gobblerNotebookLM?.getPageStructure()" \
  --json
```

4. Compare the live DOM with selectors in `browser-extension/page-apis/notebooklm.js`.

Do not submit prompts, generate audio, or perform other account-changing actions unless the user explicitly requested them.
