# Gobbler Browser Extension

The browser extension connects controlled tabs to the Gobbler relay server at
`localhost:4625`. The CLI starts and uses that relay for browser commands such
as page extraction, tab listing, navigation, JavaScript execution, and AI chat
integrations.

## Architecture

```
Browser tabs in the "Gobbler" group
        |
        v
Gobbler extension background worker
        |
        v
Relay server (gobbler relay start)
        |
        v
Gobbler CLI commands
```

Only tabs in a tab group named `Gobbler` are exposed to the relay.

## Useful Commands

```bash
gobbler relay start
gobbler relay status
gobbler browser status
gobbler browser list
gobbler browser extract -o page.md
gobbler browser exec "document.title"
```

## Extension Files

- `manifest.json` defines permissions, host access, and service worker wiring.
- `background.js` owns WebSocket relay communication and tab command handling.
- `popup.html` and `popup.js` provide the extension UI.
- `content.js` is the page content script.
- `page-apis/` contains site-specific browser APIs for NotebookLM, Claude.ai,
  ChatGPT, and Gemini.

## Development Notes

- Keep relay command names aligned with `src/gobbler_cli/commands/browser.py`.
- Avoid broad tab access. Preserve the `Gobbler` tab group isolation model.
- Site-specific APIs can break when the target site changes its DOM.
