---
name: notebooklm
description: "Interact with Google NotebookLM via browser automation. Use when user wants to query NotebookLM, extract chat history, list sources, or automate notebook interactions. The API provides methods like ask(), getChatContent(), getSources(), and getNotebookInfo()."
version: 1.2.0
allowed-tools:
  - mcp__gobbler-mcp__browser_execute_script
  - mcp__gobbler-mcp__browser_check_connection
  - mcp__gobbler-mcp__browser_list_tabs
  - mcp__gobbler-mcp__browser_execute_script_in_tab
---

# NotebookLM Automation Skill

Interact with Google NotebookLM through the Gobbler browser extension's JavaScript API. The NotebookLM API is automatically injected into NotebookLM pages when they are added to the "Gobbler" tab group.

**API Version**: 1.2.0

**Prerequisites**:
- Gobbler browser extension installed
- NotebookLM tab in "Gobbler" tab group
- Page-specific API auto-injected at `window.gobblerNotebookLM`

---

## Quick Start

The simplest way to interact with NotebookLM:

```javascript
// Ask a question and get complete response
const result = await window.gobblerNotebookLM.ask("What are the main themes?");
if (result.success) {
  console.log(result.response);
}
```

---

## Complete API Reference

### Core Methods

#### `ask(message, timeout?)`

**Recommended method** - Sends a message and waits for the complete response.

**Parameters**:
- `message` (string, required): The question or prompt to send
- `timeout` (number, optional): Maximum wait time in milliseconds (default: 90000 = 90s)

**Returns**: Promise<Object>
```javascript
{
  success: true,
  response: "Complete response text...",
  messageSentVia: "button-click" | "enter-key",
  totalElapsed: 7234,  // total time in milliseconds
  elapsed: 7100        // response wait time in milliseconds
}
```

**Error Response**:
```javascript
{
  success: false,
  error: "Error description",
  elapsed: 123
}
```

**Example**:
```javascript
const result = await window.gobblerNotebookLM.ask(
  "Summarize the key findings from all sources",
  90000  // 90 second timeout
);
```

---

#### `sendMessage(message)`

Sends a message without waiting for response. Use when you need manual control over waiting.

**Parameters**:
- `message` (string, required): The message to send

**Returns**: Promise<Object>
```javascript
{
  success: true,
  method: "button-click" | "enter-key"
}
```

**Example**:
```javascript
const result = await window.gobblerNotebookLM.sendMessage("What are the themes?");
// Message sent, but not waiting for response
```

---

#### `waitForResponse(timeout?)`

Waits for a response to complete using efficient MutationObserver pattern.

**Parameters**:
- `timeout` (number, optional): Maximum wait time in milliseconds (default: 60000 = 60s)

**Returns**: Promise<Object>
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
  partialResponse: "Partial content received...",
  elapsed: 60000
}
```

**Example**:
```javascript
// Send then wait separately
await window.gobblerNotebookLM.sendMessage("List sources");
const result = await window.gobblerNotebookLM.waitForResponse(30000);
```

---

### Information Extraction

#### `getNotebookInfo()`

Get metadata about the current notebook.

**Returns**: Object
```javascript
{
  title: "My Research Notebook",
  url: "https://notebooklm.google.com/notebook/abc123",
  notebookId: "abc123",
  isNotebook: true
}
```

**Example**:
```javascript
const info = window.gobblerNotebookLM.getNotebookInfo();
console.log(`Working in: ${info.title}`);
```

---

#### `getSources()`

Get list of all sources in the notebook.

**Returns**: Promise<Object>
```javascript
{
  success: true,
  sources: [
    { id: "source-0", title: "Research Paper.pdf" },
    { id: "source-1", title: "Interview Notes" }
  ],
  count: 2
}
```

**Example**:
```javascript
const result = await window.gobblerNotebookLM.getSources();
if (result.success) {
  result.sources.forEach(s => console.log(`- ${s.title}`));
}
```

---

#### `getChatContent()`

Get all messages from the current conversation.

**Returns**: Promise<Object>
```javascript
{
  success: true,
  messages: [
    { index: 0, role: "user", content: "What are the themes?" },
    { index: 1, role: "assistant", content: "Based on sources..." }
  ],
  count: 2
}
```

**Note**: Message content is limited to 5000 characters per message.

**Example**:
```javascript
const result = await window.gobblerNotebookLM.getChatContent();
result.messages.forEach(msg => {
  console.log(`[${msg.role}]: ${msg.content.substring(0, 100)}...`);
});
```

---

### Action Methods

#### `generateAudioOverview()`

Trigger Audio Overview generation (if available).

**Returns**: Promise<Object>
```javascript
{
  success: true,
  message: "Audio Overview generation initiated"
}
```

---

#### `getSelectedText()`

Get currently selected text on the page.

**Returns**: Object
```javascript
{
  success: true,
  text: "Selected text content...",
  rangeCount: 1
}
```

---

### Debug Methods

#### `getPageStructure()`

Get structural overview of the page for debugging selector issues.

**Returns**: Object with page structure information including inputs, buttons, chat area, etc.

**Example**:
```javascript
const structure = window.gobblerNotebookLM.getPageStructure();
console.log(`Found ${structure.inputs.length} inputs`);
console.log(`Found ${structure.buttons.length} buttons`);
```

---

#### `isNotebookPage()`

Check if current page is a notebook page.

**Returns**: boolean (true if URL contains '/notebook/')

---

#### `version`

API version string.

**Example**:
```javascript
console.log(window.gobblerNotebookLM.version); // "1.2.0"
```

---

## Timeout Behavior

NotebookLM responses can take significant time for complex operations:

### Default Timeouts
- `ask()`: **90 seconds** (recommended for most operations)
- `waitForResponse()`: **60 seconds** (lower-level, manual control)

### Timeout Strategy
1. If timeout reached **during streaming**: Returns partial response with warning
2. If timeout reached **with no response**: Throws TimeoutError
3. **Streaming detection**: Uses 1.5s stability window (3 consecutive checks at 500ms intervals)

### Timeout Examples

```javascript
// Standard question - use default 90s
const result = await window.gobblerNotebookLM.ask("Summarize the themes");

// Complex analysis - increase timeout
const result = await window.gobblerNotebookLM.ask(
  "Compare methodologies across all sources",
  180000  // 3 minutes
);

// Simple lookup - shorter timeout
const result = await window.gobblerNotebookLM.ask(
  "What is the notebook title?",
  30000  // 30 seconds
);
```

---

## Selector Fallback Strategy

The API uses multiple CSS selectors with priority ordering to ensure robustness across NotebookLM UI updates.

### Input Field Detection (Priority Order)

1. `textarea.query-box-input` - Primary NotebookLM chat input
2. `textarea[placeholder*="Start typing"]` - Placeholder-based match
3. `textarea[placeholder*="typing"]` - Partial placeholder match
4. `textarea[placeholder*="Ask"]` - Generic ask input
5. `textarea[placeholder*="message"]` - Generic message input
6. `[contenteditable="true"]` - Contenteditable fallback

### Message Detection (Priority Order)

1. `chat-message.individual-message` - Custom web component (primary)
2. `.chat-message-pair` - Message pair container
3. `[data-message-id]` - ID-based fallback
4. `.chat-message` - Generic message class

### Role Detection

- `.from-user-message-card-content` → role: "user"
- `.to-user-message-inner-content` → role: "assistant"
- Fallback: Check parent element classes

**Why Multiple Selectors?**

NotebookLM uses custom web components that may change between versions. The fallback chain ensures the API continues working across UI updates.

---

## Streaming Detection Heuristics

The API checks **10 indicators** to determine if a response is still streaming:

| Indicator | Selector/Method | Priority |
|-----------|----------------|----------|
| Loading indicator | `.loading` | High |
| Data attribute | `[data-loading="true"]` | High |
| Typing indicator | `.typing-indicator` | High |
| Streaming class | `.streaming` | Medium |
| ARIA busy | `[aria-busy="true"]` | Medium |
| Cursor blink | `.cursor-blink` | Low |
| Thinking state | `.thinking` | Low |
| Generating state | `.generating` | Low |
| Material spinner | `mat-spinner` | Low |
| Progress spinner | `.mat-progress-spinner` | Low |

### Completion Confirmation

Response is considered **complete** when:

1. **No streaming indicators active** AND
2. **Content stable** for 3 consecutive 500ms checks (1.5 seconds total) AND
3. **New message appeared** (message count increased)

### Edge Cases

- **Very short responses**: May complete before first check
- **Network issues**: Timeout returns partial response
- **Audio Overview**: Requires separate indicator check

---

## Error Handling Patterns

### Timeout Recovery

```javascript
try {
  const result = await window.gobblerNotebookLM.ask("Question?", 60000);
} catch (error) {
  if (error.message.includes("timeout")) {
    // Check for partial response
    const chatContent = await window.gobblerNotebookLM.getChatContent();
    const lastMsg = chatContent.messages[chatContent.messages.length - 1];
    if (lastMsg?.role === "assistant") {
      console.log("Partial response:", lastMsg.content);
    }
  }
}
```

### Input Field Not Found

If `sendMessage()` returns `{ success: false, error: "Could not find input field" }`:

1. Check if NotebookLM UI has updated
2. Verify tab is on correct notebook page
3. Try page refresh and re-injection
4. Use `getPageStructure()` to inspect current DOM

### Message Send Failure

If `sendMessage()` returns false:

1. Input field may be disabled
2. NotebookLM may be processing previous request
3. Check for rate limiting indicators

---

## Usage Examples

### Example 1: Simple Question

```javascript
const result = await window.gobblerNotebookLM.ask(
  "What are the key themes in the sources?"
);

if (result.success) {
  console.log("Response:", result.response);
  console.log(`Completed in ${result.totalElapsed}ms`);
}
```

### Example 2: Extract Full Context

```javascript
// Get notebook metadata
const info = window.gobblerNotebookLM.getNotebookInfo();
const sources = await window.gobblerNotebookLM.getSources();
const chat = await window.gobblerNotebookLM.getChatContent();

const context = {
  notebook: info.title,
  notebookId: info.notebookId,
  sourceCount: sources.count,
  sources: sources.sources,
  messageCount: chat.count,
  messages: chat.messages
};

console.log(JSON.stringify(context, null, 2));
```

### Example 3: Sequential Questions

```javascript
const questions = [
  "What is the main argument?",
  "What evidence supports this?",
  "What are the counterarguments?"
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

    // Polite delay between requests
    await new Promise(r => setTimeout(r, 2000));
  }
}

return JSON.stringify(results, null, 2);
```

### Example 4: Handle Partial Results

```javascript
const result = await window.gobblerNotebookLM.ask(
  "Analyze all sources in detail",
  120000  // 2 minute timeout
);

if (result.timedOut) {
  console.log("Operation timed out");
  console.log("Partial response received:", result.partialResponse);
  // Decide whether to use partial result or retry
} else if (result.success) {
  console.log("Complete response:", result.response);
}
```

---

## Best Practices

1. **Always check API availability**:
   ```javascript
   if (typeof window.gobblerNotebookLM === 'undefined') {
     throw new Error('NotebookLM API not available');
   }
   ```

2. **Use appropriate timeouts**:
   - Simple queries: 15-30 seconds
   - Standard questions: 60-90 seconds (default)
   - Complex analysis: 120-180 seconds

3. **Handle errors gracefully**:
   ```javascript
   try {
     const result = await window.gobblerNotebookLM.ask(question);
     return result;
   } catch (error) {
     console.error("API call failed:", error);
     return { success: false, error: error.message };
   }
   ```

4. **Be polite with rate limiting**:
   - Wait 2-3 seconds between requests
   - Avoid rapid-fire questions
   - Monitor for error responses

5. **Return stringified JSON for Claude**:
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
1. Check tab is in "Gobbler" tab group
2. Verify you're on a NotebookLM page (notebooklm.google.com)
3. Check browser console for injection errors
4. Manually inject via extension popup
5. Reload page (API re-injects automatically)

### sendMessage Fails

**Symptom**: `{ success: false, error: "Could not find input field" }`

**Solutions**:
1. Ensure you're on a notebook page with chat interface
2. Run `getPageStructure()` to inspect current DOM
3. NotebookLM may have changed - report to Gobbler developers

### Response Times Out

**Symptom**: Timeout before response completes

**Solutions**:
1. Increase timeout for complex questions
2. Check if NotebookLM is actually processing
3. Try simpler question to verify API works
4. Check `getPageStructure()` for `chatArea.messageCount`

---

## Multi-Instance Support

When multiple NotebookLM notebooks are open:

1. **List tabs**: Use `browser_list_tabs(filter='notebooklm')`
2. **Execute in specific tab**: Use `browser_execute_script_in_tab(tab_id=123, script=...)`
3. **Each tab has its own API instance**: `window.gobblerNotebookLM` is tab-specific

---

## Technical Documentation

For detailed technical documentation including:
- Injection mechanism
- Timeout hierarchy
- Selector strategies
- Error recovery patterns
- API internals

See: `/Users/dylanisaac/Projects/gobbler/docs/notebooklm-api.md`

---

## Security Notes

- Operations run in user's browser context with their credentials
- Only tabs in "Gobbler" tab group are accessible
- API is temporary - cleared on page reload
- No data stored outside browser session
- No credentials or sensitive data accessed beyond visible page content
