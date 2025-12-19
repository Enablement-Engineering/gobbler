# NotebookLM Skill - Technical Reference

## DOM Structure

NotebookLM uses Angular-based custom elements. The key selectors are:

### Chat Input
- **Element**: `<textarea>` with placeholder "Start typing..."
- **Parent chain**: `query-box > form > div > textarea`
- **Full path**: `body > labs-tailwind-root > div > notebook > div > section.chat-panel > chat-panel > omnibar > div > div.bottom-container > div > query-box > div > div > form > div > textarea`

### Chat Messages
- **Container**: `<chat-panel>` element with class `.chat-panel-content`
- **Messages**: `<chat-message>` elements
- **Structure**: Parent `div` contains pairs of messages (user, then AI)
- **Detection**: First child in pair = user message, second child = AI response

### Message Pattern
```
div (message container)
  ├── chat-message (user)
  └── chat-message (AI)
```

## API Object Structure

The `window.NotebookLMAPI` object created by this skill has the following interface:

```typescript
interface NotebookLMAPI {
  // Core element accessors
  getChatInput(): HTMLTextAreaElement | undefined;
  getChatMessages(): ChatMessage[];

  // Message utilities
  isUserMessage(element: Element): boolean;
  getLatestAIResponse(): ChatMessage | null;
  getLatestUserMessage(): ChatMessage | null;

  // Interaction methods
  sendMessage(text: string): Promise<SendResult>;
  waitForResponse(initialCount: number, timeoutMs?: number): Promise<ChatMessage>;
  chat(message: string, timeoutMs?: number): Promise<ChatResult>;
}

interface ChatMessage {
  index: number;
  text: string;
  element: Element;
  isUser: boolean;
  isAI: boolean;
}

interface SendResult {
  success: boolean;
  method: 'button' | 'form' | 'enter';
  initialMessageCount: number;
}

interface ChatResult {
  userMessage: string;
  aiResponse: ChatMessage;
  sendMethod: 'button' | 'form' | 'enter';
}
```

## Event Handling

NotebookLM's Angular application listens for these events on the textarea:

1. **`input` event** (bubbles: true) - Triggers change detection
2. **`change` event** (bubbles: true) - Secondary trigger
3. **Submit mechanisms** (in order of preference):
   - Click submit button (`button[type="submit"]`)
   - Dispatch form submit event
   - Simulate Enter keypress

## Timing Considerations

### Response Detection
The skill uses polling (500ms intervals) to detect new messages:
- Compares current message count to initial count
- Retrieves latest AI message when count increases
- Times out after specified duration (default 30s)

### Recommended Timeouts
- Simple queries: 30 seconds
- Complex analysis: 60 seconds
- Document-heavy questions: 90 seconds

### Wait States
NotebookLM shows intermediate states while processing:
- "Gathering the facts..." - Initial processing
- "Scanning your sources..." - Document search
- Partial responses may appear before completion

## Browser Extension Requirements

### Gobbler MCP Server
- Tool: `mcp__gobbler-mcp__browser_execute_script`
- Tool: `mcp__gobbler-mcp__browser_check_connection`
- Requires active WebSocket connection to browser extension
- Extension must have permissions for NotebookLM domain

### Script Execution Context
- Scripts execute in page context (not extension context)
- Full DOM access
- Can persist state on `window` object
- Survives navigation within SPA (single page app)
- Cleared on full page reload

## Error Scenarios

### Common Errors

1. **"Chat input not found"**
   - Cause: NotebookLM not open, or page structure changed
   - Recovery: Ask user to open NotebookLM

2. **"Timeout waiting for AI response"**
   - Cause: Response taking longer than timeout
   - Recovery: Increase timeout or retry

3. **"Detached while handling command"**
   - Cause: Page navigated during script execution
   - Recovery: Reinitialize API

4. **Empty/null responses**
   - Cause: Messages not yet rendered in DOM
   - Recovery: Wait longer before retrieval

### Debugging Strategy

Check each layer:
```javascript
// 1. Verify API exists
typeof window.NotebookLMAPI !== 'undefined'

// 2. Verify elements exist
window.NotebookLMAPI.getChatInput() !== undefined

// 3. Verify message count
document.querySelectorAll('chat-message').length

// 4. Get raw message data
Array.from(document.querySelectorAll('chat-message')).map(m => m.textContent)
```

## Persistence and State

### API Lifecycle
- **Created**: On first initialization script execution
- **Persists**: Throughout SPA navigation within NotebookLM
- **Destroyed**: On page reload, tab close, or navigation away

### State Management
- No persistent storage
- All state in browser memory (`window` object)
- Message history retrieved directly from DOM
- No local caching of responses

## Performance Considerations

### Context Window
- API initialization script: ~3KB
- Each message query: ~1KB
- Full conversation extraction: Scales with message count

### Polling Impact
- 500ms polling interval during `waitForResponse()`
- Stops immediately when new message detected
- Timeout prevents infinite polling

### DOM Query Efficiency
- `querySelectorAll` on every check
- O(n) where n = number of messages
- Negligible for typical conversations (<100 messages)

## Security Model

### Execution Scope
- Scripts run in **user's browser context**
- Uses **user's active NotebookLM session**
- Same permissions as user's browser tab

### Data Flow
1. User (via Claude) → Gobbler MCP → Browser Extension
2. Browser Extension → Page Context (script injection)
3. Page JavaScript → NotebookLM (via DOM/events)
4. NotebookLM → Google's servers (user's credentials)
5. Response → DOM → JavaScript → Extension → MCP → Claude

### No External Storage
- No data transmitted outside browser
- No logs or recordings
- Temporary API object only

## Integration Patterns

### With Puter Architecture

This skill demonstrates key Puter concepts:

1. **Component Interface**: Skill exposes capabilities (query NotebookLM)
2. **Tool Integration**: Uses MCP tools (Gobbler browser automation)
3. **Composability**: Can be invoked by other skills/agents
4. **State Management**: Manages async operations (message send/wait)

### Potential Puter Use Cases

- **Research Component**: Use NotebookLM as RAG service for Puter
- **Knowledge Integration**: Extract insights from NotebookLM to Puter inbox
- **Documentation Generation**: Query NotebookLM to clarify specs
- **Team Knowledge**: Shared notebook as component documentation source

## Extension Ideas

Future enhancements to consider:

1. **Citation Extraction**: Parse NotebookLM's source citations
2. **Document Upload**: Programmatically add sources to notebook
3. **Export Integration**: Extract responses to Puter markdown files
4. **Multi-notebook**: Switch between different notebooks
5. **Conversation History**: Save chat logs to Puter archive
6. **Feedback Loop**: Auto-update Puter docs based on NotebookLM insights

## Changelog

### Version 1.0 (Current)
- Initial implementation
- Core chat API (send, receive, retrieve)
- User/AI message detection
- Async response waiting with timeout
- Error handling and recovery
