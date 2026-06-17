# NotebookLM Page API Documentation

## Overview

The NotebookLM Page API is a JavaScript library that gets automatically injected into Google NotebookLM pages by the Gobbler browser extension. This API enables programmatic interaction with NotebookLM notebooks, allowing AI assistants like Claude to:

- Send questions and retrieve complete responses
- Extract notebook metadata and sources
- Access chat history
- Trigger features like audio overview generation
- Automate notebook workflows

The API is exposed via the global variable `window.gobblerNotebookLM` and provides both low-level methods (send, wait) and a high-level convenience method (`ask`) for complete interactions.

**Version**: 1.2.0
**File**: `browser-extension/page-apis/notebooklm.js`
**Lines of Code**: 587

## Why This Exists

NotebookLM does not provide an official API for programmatic access. The Gobbler browser extension bridges this gap by:

1. Automatically detecting when you open NotebookLM in your browser
2. Injecting a custom JavaScript API into the page
3. Providing a stable interface that AI assistants can use through `gobbler browser exec`
4. Enabling automated research, data extraction, and notebook management workflows

## How Injection Works

### Automatic Injection System

The Gobbler extension uses a pattern-matching registry to determine which page-specific APIs to inject. The injection happens automatically in three scenarios:

#### 1. When Tabs Are Added to Gobbler Group

When you add a tab to the Gobbler group (via the extension popup or right-click menu), the extension:

1. Checks if the tab's URL matches any registered API patterns
2. If a match is found, immediately injects the corresponding API
3. Confirms injection in the browser console

```javascript
// In background.js - when tab is added
const apiResult = await checkAndInjectApi(tab.id);
if (apiResult.success && apiResult.apiName) {
  console.log(`[Gobbler] Injected ${apiResult.apiName} API for tab ${tab.id}`);
}
```

#### 2. When Tabs Navigate or Refresh

The extension listens for page navigation and refresh events using `chrome.tabs.onUpdated`:

```javascript
// In background.js - auto re-injection
chrome.tabs.onUpdated.addListener(async (tabId, changeInfo, tab) => {
  // Only act when page load is complete
  if (changeInfo.status !== 'complete') return;

  // Check if tab is in Gobbler group
  const isInGroup = await isTabInGobblerGroup(tabId);
  if (!isInGroup) return;

  // Check if there's a matching API for this URL
  const apiEntry = findMatchingApi(tab.url);
  if (!apiEntry) return;

  // Re-inject the API (DOM is new after refresh)
  const result = await injectPageApi(tabId, apiEntry);
});
```

This ensures the API remains available even after:
- Page refreshes (F5, Cmd+R)
- Navigation to different notebooks
- Back/forward browser navigation

#### 3. Manual Injection via Popup UI

Users can manually trigger injection through the extension popup:

1. Click the Gobbler extension icon
2. Select the desired API from the dropdown (e.g., "NotebookLM")
3. Click "Inject" or "Re-inject"

This is useful for:
- Debugging injection issues
- Force re-injection if the API becomes unavailable
- Testing API availability

### Pattern Matching Registry

The extension maintains a registry of available APIs in `background.js`:

```javascript
const PAGE_API_REGISTRY = [
  {
    name: 'NotebookLM',
    pattern: /^https:\/\/notebooklm\.google\.com/,
    apiFile: 'page-apis/notebooklm.js',
    enabled: true
  },
];
```

**Pattern Matching Process**:

1. Extension extracts the URL from the active tab
2. Tests URL against each registry entry's `pattern` (regex or string)
3. If match found, loads and executes the corresponding `apiFile`
4. Prevents double-injection using tracking map: `injectedTabs`

### Injection Prevention

The API includes double-injection protection:

```javascript
// In notebooklm.js - prevents multiple injections
if (window.__gobblerNotebookLMInjected) {
  console.log('[Gobbler] NotebookLM API already injected');
  return;
}
window.__gobblerNotebookLMInjected = true;
```

This flag ensures the API is only injected once per page load, even if injection is triggered multiple times.

## API Reference

All methods are available on the global `window.gobblerNotebookLM` object.

### Core Methods

#### `ask(message, timeout = 90000)`

**Recommended method** - Sends a message to NotebookLM and waits for the complete response.

**Location**: Lines 448-469 in `notebooklm.js`

**Parameters**:
- `message` (string): The question or prompt to send
- `timeout` (number, optional): Maximum wait time in milliseconds (default: 90000 = 90 seconds)

**Returns**: Promise resolving to object:
```javascript
{
  success: true,
  response: "The complete response text from NotebookLM...",
  messageSentVia: "button-click" | "enter-key",
  totalElapsed: 5432,  // milliseconds (total time including send)
  elapsed: 5200        // time waiting for response only
}
```

**Error Response**:
```javascript
{
  success: false,
  error: "Failed to send message: Could not find input field",
  elapsed: 123
}
```

**Timeout Response**:
```javascript
{
  success: false,
  error: "Timeout waiting for response",
  timedOut: true,
  partialResponse: "Partial content received before timeout...",
  elapsed: 90000,
  messageSentVia: "button-click",
  totalElapsed: 90123
}
```

**Usage Example**:
```javascript
const result = await window.gobblerNotebookLM.ask("What are the main themes in the sources?");
if (result.success) {
  console.log("Response:", result.response);
  console.log("Took", result.totalElapsed, "ms");
} else {
  console.error("Error:", result.error);
  if (result.timedOut && result.partialResponse) {
    console.log("Partial response:", result.partialResponse);
  }
}
```

**How It Works**:
1. Finds the chat input field using multiple selectors (lines 223-238)
2. Types the message into the input using `simulateTyping()` helper (lines 86-91)
3. Clicks the send button or presses Enter (lines 258-312)
4. Calls `waitForResponse()` which uses `MutationObserver` to detect streaming
5. Waits for content to stabilize (no changes for 1.5 seconds + no loading indicators)
6. Returns the complete response text with timing metadata

---

#### `sendMessage(message)`

Sends a message to NotebookLM without waiting for a response. Use this if you want to manually wait or don't need the response.

**Location**: Lines 217-317 in `notebooklm.js`

**Parameters**:
- `message` (string): The message to send

**Returns**: Promise resolving to:
```javascript
{
  success: true,
  method: "button-click" | "enter-key"
}
```

**Error Response**:
```javascript
{
  success: false,
  error: "Could not find chat input field. Make sure you are on a NotebookLM notebook page."
}
```

**Usage Example**:
```javascript
const result = await window.gobblerNotebookLM.sendMessage("Summarize the sources");
if (result.success) {
  console.log("Message sent via", result.method);
  // Do something else while NotebookLM processes...
}
```

**How It Works**:
1. Searches for input field using 6 selectors (lines 223-238):
   - `textarea.query-box-input` (primary)
   - `textarea[placeholder*="Start typing"]`
   - `textarea[placeholder*="typing"]`
   - `textarea[placeholder*="Ask"]`
   - `textarea[placeholder*="message"]`
   - `[contenteditable="true"]`
2. Types message using `simulateTyping()` or sets textContent (lines 245-252)
3. Waits 100ms for UI to update (line 254)
4. Searches for send button using 6 selectors (lines 258-276)
5. Waits additional 200ms if button disabled (lines 287-297)
6. Clicks button or presses Enter as fallback (lines 301-312)

---

#### `waitForResponse(timeout = 60000)`

Waits for a response to complete after sending a message. Uses efficient `MutationObserver` instead of polling.

**Location**: Lines 321-438 in `notebooklm.js`

**Parameters**:
- `timeout` (number, optional): Maximum wait time in milliseconds (default: 60000 = 60 seconds)

**Returns**: Promise resolving to:
```javascript
{
  success: true,
  response: "The complete response...",
  elapsed: 4523  // milliseconds
}
```

**Timeout Response**:
```javascript
{
  success: false,
  error: "Timeout waiting for response",
  timedOut: true,
  partialResponse: "Whatever was received before timeout...",
  elapsed: 60000
}
```

**Usage Example**:
```javascript
// Send message
await window.gobblerNotebookLM.sendMessage("List all sources");

// Wait for response
const result = await window.gobblerNotebookLM.waitForResponse(30000);
console.log(result.response);
```

**How It Works**:
1. Counts initial messages using `messageSelector` (lines 325-326)
2. Sets up a `MutationObserver` on chat container (lines 416-431)
3. Polls every 500ms via `checkInterval` to check completion (line 434)
4. Response is considered complete when:
   - New message appears (message count increased, line 342)
   - Content stops changing for 1.5 seconds (3 consecutive 500ms checks, lines 398-409)
   - No loading/streaming indicators visible (line 401)
5. Returns latest message text from `.message-content` or `.message-text-content` (lines 340-348)

**Streaming Detection**: Checks 10 CSS selectors to determine if response is still streaming (lines 351-370):
- `.loading` - Generic loading indicator
- `[data-loading="true"]` - Data attribute
- `.typing-indicator` - Typing animation
- `.streaming` - Streaming class
- `[aria-busy="true"]` - ARIA accessibility attribute
- `.cursor-blink` - Cursor animation
- `.thinking` - Thinking state
- `.generating` - Generating state
- `mat-spinner` - Material design spinner
- `.mat-progress-spinner` - Material progress spinner

**Stability Window**: Content must remain unchanged for 3 consecutive checks at 500ms intervals (1.5 seconds total) to be considered stable (lines 398-409).

---

### Information Extraction Methods

#### `getNotebookInfo()`

Get metadata about the current notebook.

**Returns**: Object:
```javascript
{
  title: "My Research Notebook",
  url: "https://notebooklm.google.com/notebook/abc123",
  notebookId: "abc123",
  isNotebook: true
}
```

**Usage Example**:
```javascript
const info = window.gobblerNotebookLM.getNotebookInfo();
console.log("Working in notebook:", info.title);
console.log("ID:", info.notebookId);
```

---

#### `getSources()`

Get a list of all sources in the current notebook.

**Returns**: Promise resolving to:
```javascript
{
  success: true,
  sources: [
    { id: "source-0", title: "Research Paper.pdf" },
    { id: "source-1", title: "Interview Notes" },
    { id: "source-2", title: "Dataset.csv" }
  ],
  count: 3
}
```

**Error Response**:
```javascript
{
  success: false,
  error: "Error message..."
}
```

**Usage Example**:
```javascript
const result = await window.gobblerNotebookLM.getSources();
if (result.success) {
  console.log(`Found ${result.count} sources:`);
  result.sources.forEach(s => console.log(`- ${s.title}`));
}
```

**Note**: Source detection uses heuristic selectors (`[data-source-id]`, `.source-item`, `[role="listitem"]`) and may need updates if NotebookLM's DOM structure changes.

---

#### `getChatContent()`

Get all messages from the current chat/conversation.

**Returns**: Promise resolving to:
```javascript
{
  success: true,
  messages: [
    {
      index: 0,
      role: "user",
      content: "What are the main themes?"
    },
    {
      index: 1,
      role: "assistant",
      content: "Based on the sources, the main themes are..."
    }
  ],
  count: 2
}
```

**Error Response**:
```javascript
{
  success: false,
  error: "Error message..."
}
```

**Usage Example**:
```javascript
const result = await window.gobblerNotebookLM.getChatContent();
if (result.success) {
  console.log(`Chat history (${result.count} messages):`);
  result.messages.forEach(msg => {
    console.log(`[${msg.role}]:`, msg.content.substring(0, 100));
  });
}
```

**Note**: Message content is limited to 5000 characters per message to prevent memory issues.

---

### Action Methods

#### `generateAudioOverview()`

Trigger the Audio Overview generation feature (if available in the current notebook).

**Returns**: Promise resolving to:
```javascript
{
  success: true,
  message: "Audio Overview generation initiated"
}
```

**Error Response**:
```javascript
{
  success: false,
  error: "Audio Overview button not found"
}
```

**Usage Example**:
```javascript
const result = await window.gobblerNotebookLM.generateAudioOverview();
if (result.success) {
  console.log("Audio overview started!");
}
```

**How It Works**: Searches for buttons containing "audio" or "overview" in their text or aria-label, then clicks the button.

---

#### `getSelectedText()`

Get the currently selected text on the page (useful for extracting highlighted content from sources).

**Returns**: Object:
```javascript
{
  success: true,
  text: "The selected text content...",
  rangeCount: 1
}
```

**No Selection Response**:
```javascript
{
  success: false,
  error: "No text selected"
}
```

**Usage Example**:
```javascript
const result = window.gobblerNotebookLM.getSelectedText();
if (result.success) {
  console.log("Selected text:", result.text);
}
```

---

### Debug Methods

#### `getPageStructure()`

Get a structural overview of the page for debugging and selector development.

**Returns**: Object:
```javascript
{
  title: "My Notebook - NotebookLM",
  url: "https://notebooklm.google.com/notebook/abc123",
  mainContent: {
    tag: "MAIN",
    classes: "main-content",
    childCount: 5
  },
  sidebar: {
    tag: "ASIDE",
    classes: "sidebar"
  },
  chatArea: {
    tag: "DIV",
    classes: "chat-container",
    messageCount: 12
  },
  inputs: [
    {
      tag: "TEXTAREA",
      type: "textarea",
      placeholder: "Ask about your sources...",
      classes: "chat-input"
    }
  ],
  buttons: [
    { text: "Send", ariaLabel: "Send message", disabled: false },
    { text: "Audio Overview", ariaLabel: "", disabled: false }
  ]
}
```

**Usage Example**:
```javascript
const structure = window.gobblerNotebookLM.getPageStructure();
console.log("Page structure:", JSON.stringify(structure, null, 2));
console.log("Found", structure.inputs.length, "input fields");
console.log("Found", structure.buttons.length, "buttons");
```

**Use Cases**:
- Debugging why methods can't find elements
- Developing new methods
- Understanding NotebookLM's DOM structure
- Reporting issues to Gobbler developers

---

#### `isNotebookPage()`

Check if the current page is a notebook page (vs. home page, list page, etc.).

**Returns**: boolean
```javascript
true  // if URL contains '/notebook/'
false // otherwise
```

**Usage Example**:
```javascript
if (window.gobblerNotebookLM.isNotebookPage()) {
  console.log("We're on a notebook page, API methods should work");
} else {
  console.log("Not on a notebook page, navigate to one first");
}
```

---

#### `version`

API version string.

**Usage**:
```javascript
console.log("API Version:", window.gobblerNotebookLM.version);
// Output: "API Version: 1.1.0"
```

---

## Timeout Hierarchy and Configuration

### Timeout Defaults and Rationale

NotebookLM responses can take significant time depending on:
- Source complexity and size
- Number of sources to analyze
- Question complexity
- Network latency
- Server processing load

**Default Timeouts**:
- `ask()`: **90,000ms (90 seconds)** - Recommended for most operations
  - Rationale: Covers typical questions plus buffer for complex analysis
  - Includes time for both sending (~500ms) and waiting for response
- `waitForResponse()`: **60,000ms (60 seconds)** - Lower-level waiting only
  - Rationale: Assumes message already sent, only waiting for completion
  - Shorter because send overhead not included

**Why the Mismatch?**

The 30-second difference (90s vs 60s) accounts for:
1. Message sending time (100-500ms typically)
2. Additional safety buffer for `ask()` since it's the primary method
3. UI interaction delays (button enable, form submission, etc.)

### Timeout Behavior Details

**Phase 1: Sending** (handled by `sendMessage`)
- Input field detection: Tries 6 selectors sequentially
- Button detection: Tries 6 selectors, waits 200ms if disabled
- Fallback to Enter key if button not found
- Total time: Usually 200-500ms, no explicit timeout

**Phase 2: Waiting** (handled by `waitForResponse`)
- Initial detection delay: 1 second before first check (line 437)
- Poll interval: 500ms (line 434)
- Stability window: 1.5 seconds (3 consecutive unchanged checks, lines 398-409)
- Minimum response time: ~2 seconds (1s initial + 1.5s stability)
- Maximum response time: `timeout` parameter

**Timeout Reached Behavior**:

1. **During streaming** (partial content exists):
   ```javascript
   {
     success: false,
     error: "Timeout waiting for response",
     timedOut: true,
     partialResponse: "Content received so far...",
     elapsed: 60000
   }
   ```

2. **No response yet** (no content):
   ```javascript
   {
     success: false,
     error: "Timeout waiting for response",
     timedOut: true,
     partialResponse: null,
     elapsed: 60000
   }
   ```

### Timeout Recommendations by Use Case

| Use Case | Recommended Timeout | Rationale |
|----------|-------------------|-----------|
| Simple fact lookup | 15,000-30,000ms | Quick source scan |
| Standard question | 60,000-90,000ms | Default - covers most cases |
| Complex analysis | 120,000-180,000ms | Multiple source synthesis |
| Cross-source comparison | 180,000-300,000ms | Extensive processing |
| Audio Overview generation | 300,000-600,000ms | Long-running generation |

### Timeout Configuration Examples

```javascript
// Quick lookup - 30 seconds
const result = await window.gobblerNotebookLM.ask(
  "What is the title of the first source?",
  30000
);

// Standard question - use default 90 seconds
const result = await window.gobblerNotebookLM.ask(
  "What are the main themes?"
);

// Complex analysis - 3 minutes
const result = await window.gobblerNotebookLM.ask(
  "Compare the methodologies across all sources and identify commonalities",
  180000
);

// Very complex - 5 minutes
const result = await window.gobblerNotebookLM.ask(
  "Synthesize findings from all sources and create a comprehensive timeline",
  300000
);
```

---

## Selector Fallback Strategy

### Design Philosophy

NotebookLM uses custom web components (`<chat-message>`) and frequently changing class names. The API uses a **multi-level fallback strategy** to maintain compatibility across UI updates:

1. **Specific selectors first**: Target known NotebookLM-specific classes
2. **Generic selectors second**: Fall back to common patterns
3. **Data attributes third**: Use semantic attributes when available
4. **Multiple attempts**: Try all selectors before failing

### Input Field Detection Strategy

**Priority Order** (lines 223-238):

| Priority | Selector | Purpose | Why It Matters |
|----------|----------|---------|----------------|
| 1 | `textarea.query-box-input` | Primary NotebookLM chat input | Most specific, least likely to match wrong element |
| 2 | `textarea[placeholder*="Start typing"]` | Exact placeholder match | Semantic match based on visible text |
| 3 | `textarea[placeholder*="typing"]` | Partial placeholder | More flexible, catches variations |
| 4 | `textarea[placeholder*="Ask"]` | Generic ask pattern | Catches "Ask about your sources" etc. |
| 5 | `textarea[placeholder*="message"]` | Generic message pattern | Broad fallback |
| 6 | `[contenteditable="true"]` | Contenteditable element | Last resort for rich text inputs |

**Why This Order?**

1. Specificity prevents false matches (e.g., won't match "Search for sources" textarea)
2. Semantic matching based on user-visible text is more stable than internal class names
3. Contenteditable is last because it's too broad (many elements might match)

**What To Avoid**:

- ❌ Single selector: `document.querySelector('textarea')` - Too broad, might match wrong element
- ❌ Index-based: `document.querySelectorAll('textarea')[0]` - Fragile, breaks if element order changes
- ✅ Multiple specific selectors with fallbacks - Robust and maintainable

### Send Button Detection Strategy

**Priority Order** (lines 258-276):

| Priority | Selector | Purpose | Notes |
|----------|----------|---------|-------|
| 1 | `button[aria-label="Submit"]` | NotebookLM uses "Submit" not "Send" | Accessibility-based match |
| 2 | `button[aria-label*="Submit"]` | Partial aria-label match | Catches "Submit message" etc. |
| 3 | `button[aria-label*="Send"]` | Alternative aria-label | Generic send button |
| 4 | `button[aria-label*="send"]` | Lowercase variant | Case-insensitive catch |
| 5 | `button[type="submit"]` | Form submit button | Semantic HTML |
| 6 | `button.send-button` | Class-based fallback | Generic class name |

**Fallback Strategy** (lines 279-284):
- If all button selectors fail, find the form containing the input
- Look for `button[type="submit"]` or any button within the form
- Final fallback: Press Enter key (lines 301-308)

### Message Detection Strategy

**Priority Order** (lines 171-182):

| Priority | Selector | Purpose | Detected By |
|----------|----------|---------|-------------|
| 1 | `chat-message.individual-message` | NotebookLM custom web component | Specific class combination |
| 2 | `.chat-message-pair` | Message pair container | Container element |
| 3 | `[data-message-id]` | Data attribute-based | Semantic attribute |
| 4 | `.chat-message` | Generic message class | Broad fallback |

**Role Detection Logic** (lines 186-191):

1. Check for `.from-user-message-card-content` → User message
2. Check for `classList.contains('from-user')` → User message
3. Check for `data-role="user"` attribute → User message
4. Default: Assistant message

**Content Extraction** (lines 193-195):

1. Try `.message-content` selector
2. Try `.message-text-content` selector
3. Fallback: `textContent` from entire message element

### Chat Container Detection

**Priority Order** (line 424):

| Priority | Selector | Purpose |
|----------|----------|---------|
| 1 | `section.chat-panel` | NotebookLM-specific section |
| 2 | `[role="log"]` | ARIA role for message log |
| 3 | `.chat-container` | Generic container class |
| 4 | `.messages` | Alternative container class |
| 5 | `main` | Main content element fallback |

**Why Multiple Selectors?**

- NotebookLM's UI has changed multiple times (custom elements, Material Design, etc.)
- Works across different NotebookLM features (chat, sources, audio overview)

### Selector Maintenance Guide

**When selectors break**:

1. Open browser DevTools on NotebookLM page
2. Inspect the element that should be targeted
3. Note the current class names, attributes, and structure
4. Add new selector to the **beginning** of the array (highest priority)
5. Keep old selectors as fallbacks
6. Update this documentation

**Example PR for selector update**:

```javascript
// Old (stopped working in NotebookLM update 2025-02)
const inputSelectors = [
  'textarea.query-box-input',
  // ... other selectors
];

// New (add new selector at top)
const inputSelectors = [
  'textarea.chat-input-v2',  // NEW: NotebookLM 2025-02 update
  'textarea.query-box-input', // Keep as fallback
  // ... other selectors
];
```

---

## Usage Examples

### Example 1: Ask a Question (Recommended)

The simplest and most reliable way to interact with NotebookLM:

```javascript
// From gobbler browser exec
const result = await (async () => {
  const r = await window.gobblerNotebookLM.ask("What are the key themes in the sources?");
  return JSON.stringify(r);
})();

// Parse the result
const data = JSON.parse(result);
console.log(data.response);
```

**Expected Response**:
```json
{
  "success": true,
  "response": "Based on the sources provided, the key themes are:\n\n1. Climate change adaptation\n2. Sustainable agriculture practices\n3. Water resource management\n...",
  "messageSentVia": "button-click",
  "totalElapsed": 7234,
  "elapsed": 7100
}
```

---

### Example 2: Multiple Questions in Sequence

```javascript
const questions = [
  "What is the main argument of the paper?",
  "What evidence supports this argument?",
  "What are the counterarguments mentioned?"
];

const results = [];

for (const question of questions) {
  const result = await window.gobblerNotebookLM.ask(question, 60000);
  if (result.success) {
    results.push({
      question: question,
      answer: result.response,
      timeMs: result.totalElapsed
    });
    // Wait 2 seconds between questions to be polite
    await new Promise(r => setTimeout(r, 2000));
  } else {
    console.error(`Failed for "${question}":`, result.error);
  }
}

return JSON.stringify(results, null, 2);
```

---

### Example 3: Extract Notebook Metadata

```javascript
const metadata = {
  info: window.gobblerNotebookLM.getNotebookInfo(),
  sources: await window.gobblerNotebookLM.getSources(),
  chatHistory: await window.gobblerNotebookLM.getChatContent()
};

return JSON.stringify(metadata, null, 2);
```

**Expected Response**:
```json
{
  "info": {
    "title": "Climate Research Notes",
    "url": "https://notebooklm.google.com/notebook/xyz789",
    "notebookId": "xyz789",
    "isNotebook": true
  },
  "sources": {
    "success": true,
    "sources": [
      { "id": "source-0", "title": "IPCC Report 2023.pdf" },
      { "id": "source-1", "title": "Field Notes.docx" }
    ],
    "count": 2
  },
  "chatHistory": {
    "success": true,
    "messages": [...],
    "count": 8
  }
}
```

---

### Example 4: CLI Browser Exec Integration

Use `gobbler browser exec` to call the page API from the CLI:

```bash
# Step 1: Check if we're on a notebook page
gobbler browser exec "window.gobblerNotebookLM?.isNotebookPage() || false"

# Step 2: Get notebook info
gobbler browser exec "JSON.stringify(window.gobblerNotebookLM.getNotebookInfo())"

# Step 3: Ask a question
gobbler browser exec "(async () => {
  const result = await window.gobblerNotebookLM.ask('Summarize the key findings from all sources', 90000);
  return JSON.stringify(result);
})()"
```

---

### Example 5: Debug Page Structure

If methods aren't working, inspect the page structure:

```javascript
const structure = window.gobblerNotebookLM.getPageStructure();
console.log("=== Page Structure Debug ===");
console.log("Title:", structure.title);
console.log("URL:", structure.url);

console.log("\nInputs found:");
structure.inputs.forEach((input, i) => {
  console.log(`  ${i+1}. ${input.tag} - placeholder: "${input.placeholder}"`);
});

console.log("\nButtons found:");
structure.buttons.forEach((btn, i) => {
  console.log(`  ${i+1}. "${btn.text}" (aria: "${btn.ariaLabel}")`);
});

console.log("\nChat area:", structure.chatArea);
```

---

## Response Formats

### Success Response Format

All async methods follow this pattern:

```javascript
{
  success: true,
  // ... method-specific data
}
```

### Error Response Format

```javascript
{
  success: false,
  error: "Human-readable error message"
}
```

### Timeout Response Format

For methods with timeout (like `waitForResponse`, `ask`):

```javascript
{
  success: false,
  error: "Timeout waiting for response",
  timedOut: true,
  partialResponse: "Any content received before timeout",
  elapsed: 60000
}
```

---

## Adding New Page APIs

Want to create APIs for other sites like YouTube, Google Docs, or Wikipedia? Here's how:

### Step 1: Create the API File

Create a new file: `browser-extension/page-apis/yoursite.js`

```javascript
(function() {
  'use strict';

  // Prevent double-injection
  if (window.__gobblerYourSiteInjected) {
    return;
  }
  window.__gobblerYourSiteInjected = true;

  // Your API object
  const YourSiteAPI = {
    version: '1.0.0',

    // Add your methods here
    async doSomething() {
      // Implementation
      return { success: true, data: "..." };
    }
  };

  // Expose globally
  window.gobblerYourSite = YourSiteAPI;

  console.log('[Gobbler] YourSite API v' + YourSiteAPI.version + ' injected');
})();
```

### Step 2: Register in registry.js (Single Source of Truth)

Add your entry to `browser-extension/page-apis/registry.js`:

```javascript
const PAGE_API_REGISTRY = [
  {
    name: 'NotebookLM',
    pattern: /^https:\/\/notebooklm\.google\.com/,
    apiFile: 'page-apis/notebooklm.js',
    enabled: true,
    injectionMarker: '__gobblerNotebookLMInjected',
    // UI metadata
    domain: 'notebooklm.google.com',
    description: 'Interact with NotebookLM notebooks',
    globalVar: 'window.gobblerNotebookLM',
    methods: ['ask', 'sendMessage', 'getSources', 'getChatContent']
  },
  // Add your new API:
  {
    name: 'YourSite',
    pattern: /^https:\/\/(www\.)?yoursite\.com/,
    apiFile: 'page-apis/yoursite.js',
    enabled: true,
    injectionMarker: '__gobblerYourSiteInjected',  // Must match marker in yoursite.js
    domain: 'yoursite.com',
    description: 'Description of what your API does',
    globalVar: 'window.gobblerYourSite',
    methods: ['doSomething', 'anotherMethod']
  }
];
```

**Note**: This is the only file you need to edit. Both `background.js` and `popup.js` load the registry automatically.

### Step 3: Test

1. Reload the Gobbler extension in `chrome://extensions/`
2. Navigate to the target site (e.g., yoursite.com)
3. Add the tab to the Gobbler group
4. Check browser console for injection confirmation
5. Test the API: `window.gobblerYourSite.doSomething()`

### Example: YouTube API

Here's a simple YouTube API example:

```javascript
// page-apis/youtube.js
(function() {
  'use strict';

  if (window.__gobblerYouTubeInjected) return;
  window.__gobblerYouTubeInjected = true;

  const YouTubeAPI = {
    version: '1.0.0',

    getVideoInfo() {
      const player = document.querySelector('#movie_player');
      const titleEl = document.querySelector('h1.ytd-video-primary-info-renderer');

      return {
        success: true,
        videoId: new URLSearchParams(window.location.search).get('v'),
        title: titleEl?.textContent?.trim() || 'Unknown',
        currentTime: player?.getCurrentTime() || 0,
        duration: player?.getDuration() || 0,
        isPlaying: player?.getPlayerState() === 1
      };
    },

    play() {
      document.querySelector('#movie_player')?.playVideo();
      return { success: true };
    },

    pause() {
      document.querySelector('#movie_player')?.pauseVideo();
      return { success: true };
    }
  };

  window.gobblerYouTube = YouTubeAPI;
  console.log('[Gobbler] YouTube API injected');
})();
```

---

## Best Practices

### 1. Always Check for API Availability

```javascript
if (typeof window.gobblerNotebookLM === 'undefined') {
  throw new Error('NotebookLM API not available. Is the extension injected?');
}
```

### 2. Use try-catch for Robustness

```javascript
try {
  const result = await window.gobblerNotebookLM.ask("Question?");
  return result;
} catch (error) {
  console.error("API call failed:", error);
  return { success: false, error: error.message };
}
```

### 3. Set Appropriate Timeouts

```javascript
// Short timeout for simple queries
const quick = await window.gobblerNotebookLM.ask("What's the title?", 15000);

// Long timeout for complex analysis
const detailed = await window.gobblerNotebookLM.ask(
  "Analyze all sources and compare their methodologies",
  120000  // 2 minutes
);
```

### 4. Handle Partial Results on Timeout

```javascript
const result = await window.gobblerNotebookLM.ask(question, 60000);

if (result.timedOut) {
  console.log("Got partial response before timeout:");
  console.log(result.partialResponse);
  // Decide whether to retry, use partial, or fail
}
```

### 5. Be Polite with Rate Limiting

```javascript
// Wait between requests to avoid overwhelming NotebookLM
for (const question of questions) {
  const result = await window.gobblerNotebookLM.ask(question);
  // Wait 2-3 seconds between questions
  await new Promise(r => setTimeout(r, 2000));
}
```

### 6. Return Stringified JSON for Claude

When returning structured values through `gobbler browser exec`, stringify JSON:

```javascript
// Good - Claude can parse this
return JSON.stringify(result);

// Bad - Claude receives "[object Object]"
return result;
```

---

## Troubleshooting

### API Not Available

**Symptom**: `window.gobblerNotebookLM` is `undefined`

**Solutions**:
1. Check that the tab is in the Gobbler group (extension popup should show "In Gobbler group")
2. Verify you're on a NotebookLM page (`notebooklm.google.com`)
3. Check browser console for injection errors
4. Manually inject via extension popup
5. Reload the page (API re-injects automatically)

### sendMessage Fails

**Symptom**: `{ success: false, error: "Could not find input field" }`

**Solutions**:
1. Make sure you're on a notebook page with chat interface
2. Run `window.gobblerNotebookLM.getPageStructure()` to inspect inputs
3. NotebookLM may have changed their DOM - report issue to Gobbler developers

### waitForResponse Times Out

**Symptom**: Response doesn't complete within timeout

**Solutions**:
1. Increase timeout: `ask(message, 120000)` for complex questions
2. Check if NotebookLM is actually processing (look for loading indicator)
3. Use `getPageStructure()` to check for `chatArea.messageCount`
4. Try asking a simpler question first to verify API is working

### Response Truncated or Incomplete

**Symptom**: Response ends mid-sentence

**Possible Causes**:
1. Timeout occurred (check `result.timedOut`)
2. NotebookLM's response was actually incomplete (rare)
3. Streaming detection failed (content stabilized too early)

**Solutions**:
1. Increase timeout
2. Manually verify the response in NotebookLM UI
3. Report to Gobbler developers if consistently happening

---

## Limitations

### 1. DOM Structure Dependency

The API relies on CSS selectors that may change when Google updates NotebookLM. If methods stop working:

- Use `getPageStructure()` to inspect current DOM
- Report the issue to Gobbler developers
- Check for API updates

### 2. Rate Limiting

NotebookLM may rate-limit requests. Be respectful:

- Wait 2-3 seconds between questions
- Avoid sending 100+ questions in quick succession
- Monitor for error responses

### 3. No Source Upload

The current API cannot upload new sources to notebooks. This requires file system access which browser extensions don't have from content scripts.

**Workaround**: Manually upload sources, then use the API to interact with them.

### 4. No Authentication Management

The API assumes you're already logged into NotebookLM. It cannot:

- Log you in
- Switch accounts
- Create new notebooks (must be done manually)

### 5. Selector Fragility

Methods like `getSources()` and `getChatContent()` use heuristic selectors (guessing based on common patterns) since NotebookLM doesn't use stable data attributes.

These may break if Google changes their HTML structure.

---

## Security Considerations

### 1. Injection Scope

The API only injects into tabs in the **Gobbler group**. This prevents:

- Accidental injection into sensitive pages
- Unauthorized access to other tabs

### 2. Same-Origin Policy

The API runs in the page context and is subject to browser same-origin policy. It cannot:

- Access other domains
- Read cookies from other sites
- Bypass CORS

### 3. No Credential Storage

The API does not store, transmit, or access:

- Login credentials
- API keys
- Personal data (beyond what's visible on the page)

### 4. Code Execution

The `gobbler browser exec` command executes arbitrary JavaScript. Only use with:

- Trusted code
- Your own scripts
- AI assistants you trust (like Claude)

**Never** execute untrusted scripts on pages containing sensitive data.

---

## Changelog

### Version 1.1.0 (2025-01-10)

- Added `ask()` method as recommended high-level API
- Improved response completion detection with `MutationObserver`
- Added streaming indicator detection
- Added `totalElapsed` to `ask()` response
- Added `messageSentVia` to track how message was sent
- Improved timeout handling with `partialResponse`
- Better selector fallbacks for input fields and buttons

### Version 1.0.0 (2025-01-05)

- Initial release
- Basic methods: `sendMessage`, `waitForResponse`
- Info methods: `getNotebookInfo`, `getSources`, `getChatContent`
- Action methods: `generateAudioOverview`, `getSelectedText`
- Debug methods: `getPageStructure`, `isNotebookPage`
- Automatic injection on tab add and page navigation
- Manual injection via extension popup

---

## Contributing

Found a bug or want to improve the API?

1. **Test thoroughly**: Use `getPageStructure()` to verify selectors
2. **Document changes**: Update this documentation
3. **Update version**: Increment version in `notebooklm.js`
4. **Submit PR**: Create a pull request with clear description

---

## Support

- **GitHub Issues**: Report bugs and request features
- **Documentation**: This file (keep it updated!)
- **Example Code**: See usage examples above
- **Developer Console**: Browser console shows injection logs and errors

---

## License

Part of the Gobbler project. See main project LICENSE.
