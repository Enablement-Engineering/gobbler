# PRD-008: NotebookLM Context Disclosure

## Overview
**Epic**: AI Context & Documentation
**Phase**: Documentation
**Dependencies**: PRD-007 (Architectural Clarity) - for consistent terminology
**Parallel**: No - depends on PRD-007 completion

## Problem Statement

The NotebookLM integration in the browser extension has sophisticated capabilities (587 lines of JavaScript), but AI context about how to use it is lost because:

1. **API methods undocumented**: `ask()`, `sendMessage()`, `getChatContent()`, `getSources()` etc. not documented
2. **Timeout behavior unclear**: `waitForResponse` default 60s vs `ask` default 90s - mismatch not explained
3. **Selector fallbacks hidden**: 6+ CSS selectors tried for message detection, no priority explanation
4. **Streaming detection opaque**: 8 loading indicators checked, no explanation of why each matters
5. **Error recovery patterns missing**: What happens on timeout? Partial responses?
6. **Skill SKILL.md too brief**: Only high-level overview, no API reference

This causes AI to lose context when users ask about NotebookLM automation, leading to incorrect guidance or failed operations.

## Success Criteria

- [ ] Complete API reference for all NotebookLM JavaScript methods
- [ ] Timeout behavior documented with examples
- [ ] Selector fallback strategy explained
- [ ] Streaming detection heuristics documented
- [ ] Error recovery patterns documented
- [ ] Skill SKILL.md updated with comprehensive guidance
- [ ] CLAUDE.md cross-referenced from skill

## Technical Requirements

### 1. NotebookLM API Reference

Document all methods in `browser-extension/page-apis/notebooklm.js`:

| Method | Parameters | Returns | Description |
|--------|------------|---------|-------------|
| `ask(message, timeout?)` | message: string, timeout?: number (default 90000ms) | Promise<{response, elapsed}> | Send message and wait for complete response |
| `sendMessage(message)` | message: string | Promise<boolean> | Send message without waiting for response |
| `waitForResponse(timeout?)` | timeout?: number (default 60000ms) | Promise<{response, elapsed}> | Wait for current response to complete |
| `getChatContent()` | none | Array<{role, content}> | Extract all chat messages |
| `getSources()` | none | Array<{title, type?}> | List notebook sources |
| `getNotebookInfo()` | none | {title, url, notebookId} | Get notebook metadata |
| `getPageStructure()` | none | object | Debug helper for DOM inspection |

### 2. Timeout Behavior Documentation

```markdown
## Timeout Hierarchy

NotebookLM responses can take significant time, especially for:
- Long source analysis
- Complex questions requiring multi-source synthesis
- Audio Overview generation

### Default Timeouts:
- `ask()`: 90 seconds - recommended for most operations
- `waitForResponse()`: 60 seconds - lower-level, use for custom polling

### Timeout Behavior:
1. If timeout reached during streaming, returns partial response with warning
2. If timeout reached with no response, throws TimeoutError
3. Streaming detection uses 1.5s stability window (3 consecutive identical states)

### Recommended Usage:
```javascript
// For standard questions
const result = await window.gobblerNotebookLM.ask("Summarize the main themes", 90000);

// For complex analysis (increase timeout)
const result = await window.gobblerNotebookLM.ask("Compare all sources", 180000);

// For simple lookups (shorter timeout)
const result = await window.gobblerNotebookLM.ask("What is the title?", 30000);
```
```

### 3. Selector Fallback Documentation

Document the selector priority for each operation:

```markdown
## Message Detection Selectors (Priority Order)

1. `chat-message` - Custom web component (primary)
2. `.from-user-message-card-content` - User message content
3. `.to-user-message-inner-content` - Assistant message content
4. `.message-content` - Generic message wrapper
5. `.message-text-content` - Text content fallback
6. `[data-message-id]` - ID-based fallback

### Why Multiple Selectors?
NotebookLM's UI uses custom web components that may change between versions.
The fallback chain ensures robustness across UI updates.

### Role Detection:
- `.from-user-message-card-content` → role: "user"
- `.to-user-message-inner-content` → role: "assistant"
- Fallback: Check parent element classes
```

### 4. Streaming Detection Heuristics

```markdown
## Streaming Detection Indicators

The API checks 8 indicators to determine if a response is still streaming:

| Indicator | Priority | Description |
|-----------|----------|-------------|
| `.typing-indicator` | High | Explicit typing animation |
| `aria-busy="true"` | High | Accessibility attribute |
| `.loading-spinner` | Medium | Visual spinner element |
| `.streaming` class | Medium | Explicit streaming state |
| Content length change | Medium | Response growing |
| `.cursor-blink` | Low | Cursor animation |
| `[data-streaming]` | Low | Data attribute |
| Timestamp stability | Low | No changes for 1.5s = complete |

### Completion Confirmation:
Response is considered complete when:
1. No streaming indicators active AND
2. Content stable for 3 consecutive 500ms checks (1.5s total)

### Edge Cases:
- Very short responses: May complete before first check
- Network issues: Timeout with partial response returned
- Audio Overview: Separate indicator check needed
```

### 5. Error Recovery Patterns

```markdown
## Error Handling

### Timeout Recovery
```javascript
try {
  const result = await window.gobblerNotebookLM.ask("Question", 60000);
} catch (error) {
  if (error.message.includes("timeout")) {
    // Check for partial response
    const partial = await window.gobblerNotebookLM.getChatContent();
    const lastMessage = partial[partial.length - 1];
    if (lastMessage?.role === "assistant") {
      console.log("Partial response:", lastMessage.content);
    }
  }
}
```

### Input Field Not Found
The API tries multiple input selectors. If all fail:
- Check if NotebookLM UI has updated
- Verify tab is on correct notebook page
- Try page refresh and re-injection

### Message Send Failure
If sendMessage returns false:
- Input field may be disabled
- NotebookLM may be processing previous request
- Check for rate limiting indicators
```

## Implementation Details

### Files to Create/Modify

1. **skills/notebooklm/SKILL.md** - Comprehensive API reference
2. **docs/notebooklm-api.md** - Detailed API documentation
3. **browser-extension/CLAUDE.md** - Cross-reference NotebookLM section

### Updated SKILL.md Structure

```markdown
---
name: notebooklm
description: "Interact with Google NotebookLM via browser automation. Use when user wants to query NotebookLM, extract chat history, list sources, or automate notebook interactions."
version: 1.0.0
allowed-tools:
  - mcp__gobbler-mcp__browser_execute_script
  - mcp__gobbler-mcp__browser_check_connection
  - mcp__gobbler-mcp__browser_list_tabs
  - mcp__gobbler-mcp__browser_execute_script_in_tab
---

# NotebookLM Automation Skill

## Quick Start
[Basic usage examples]

## API Reference
[Full method documentation]

## Timeout Behavior
[Timeout hierarchy and recommendations]

## Selector Strategy
[Fallback chain explanation]

## Streaming Detection
[How completion is determined]

## Error Handling
[Recovery patterns]

## Examples
[Common workflow examples]
```

## Acceptance Criteria

### Documentation Completeness
- [ ] All 7 API methods documented with parameters and return types
- [ ] Timeout behavior explained with code examples
- [ ] Selector fallback priorities listed
- [ ] Streaming detection indicators documented
- [ ] Error recovery patterns with code examples

### Skill Integration
- [ ] SKILL.md updated with full API reference
- [ ] Description field optimized for AI discovery
- [ ] allowed-tools list accurate

### Cross-References
- [ ] CLAUDE.md references NotebookLM API section
- [ ] README.md mentions NotebookLM capability
- [ ] docs/notebooklm-api.md created with full documentation

### Verification
- [ ] AI can correctly answer "how do I ask NotebookLM a question?"
- [ ] AI understands timeout configuration
- [ ] AI can troubleshoot common errors

## Deliverables

### Files to Create/Modify
```
skills/notebooklm/
└── SKILL.md                    # Complete rewrite with API reference

docs/
└── notebooklm-api.md           # Detailed API documentation

browser-extension/
└── CLAUDE.md                   # Add NotebookLM section cross-reference
```

## Definition of Done

- [ ] All API methods fully documented
- [ ] Timeout behavior clearly explained
- [ ] Selector fallback strategy documented
- [ ] Streaming detection heuristics explained
- [ ] Error recovery patterns provided
- [ ] SKILL.md enables AI to guide NotebookLM automation
- [ ] Cross-references in place between docs
- [ ] Tested with Claude Code session to verify context restoration
