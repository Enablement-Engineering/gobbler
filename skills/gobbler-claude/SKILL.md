---
name: gobbler-claude
description: "Interact with Claude.ai conversations via browser automation. Use when user wants to send messages to Claude.ai, get chat history, or automate Claude interactions in the browser."
version: 1.0.0
---

# Claude.ai Integration

Send messages to and receive responses from Claude.ai through the Gobbler CLI. The browser extension connects to Claude.ai tabs and enables automation.

## CRITICAL: One Message at a Time Per Conversation

**Send only ONE message at a time to each conversation, then WAIT for the response.**

Why? The query command waits for the "last message" in the chat. If you send multiple messages in parallel:
- All messages get submitted to Claude
- The first message's script may return the WRONG answer (from a later message)
- You get mismatched message/response pairs

## Prerequisites

1. **Browser extension installed** - Load `browser-extension/` folder in Chrome
2. **Claude.ai tab in "Gobbler" group** - Right-click tab → "Add to group" → name it "Gobbler"
3. **Relay running** - Auto-starts when you run commands

## Quick Workflow

```bash
# 1. List available Claude.ai tabs
gobbler claude list

# 2. Send message and get response (waits for complete answer)
gobbler claude query "Your message here"

# 3. If response looks incomplete, get full last response
gobbler claude last
```

---

## CLI Commands

### `gobbler claude list`

List all Claude.ai tabs in the Gobbler tab group.

```bash
gobbler claude list
```

### `gobbler claude query`

Send a message to Claude.ai and wait for the complete response.

```bash
# Basic message (waits for full response)
gobbler claude query "Explain quantum computing in simple terms"

# With longer timeout for complex responses
gobbler claude query "Write a detailed analysis" --timeout 300

# Target specific tab by ID
gobbler claude query "Continue our discussion" --tab 1234567
```

**Options**:
- `--timeout SECONDS` - Max wait time (default: 150 / 2.5 min)
- `--tab TAB_ID` - Target specific tab instead of first Claude tab

The command waits until the response text is stable for 3 seconds before returning.

### `gobbler claude last`

Get the last/most recent response from Claude. Use as a backup if the query response looks incomplete.

```bash
gobbler claude last
```

### `gobbler claude history`

Get chat history from the conversation.

```bash
# Get last 10 messages
gobbler claude history --count 10

# Get all messages
gobbler claude history --all
```

### `gobbler claude info`

Get conversation metadata.

```bash
gobbler claude info
```

---

## Recommended Workflow for AI Agents

### Step 1: List Conversations

```bash
gobbler claude list
```

Note the Tab ID if you have multiple Claude tabs.

### Step 2: Send Message and Wait

```bash
gobbler claude query "Your message" --timeout 150
```

The command returns the complete response. **Wait for it to finish before sending another message.**

### Step 3: Verify Response (if needed)

If the response looks cut off:

```bash
gobbler claude last
```

### Step 4: Follow-up Messages

Send the next message only AFTER the previous one completes:

```bash
gobbler claude query "Follow-up message"
```

---

## Error Handling

### "No Claude.ai tabs found"

The tab must be:
1. Open in the browser at claude.ai
2. In a tab group named exactly "Gobbler"

### "Could not find Claude input field"

- Make sure you're on a conversation page (claude.ai/chat/...)
- The page may have changed - try refreshing

### Timeout errors

Increase the timeout for long responses:

```bash
gobbler claude query "Complex question" --timeout 300
```

---

## Example Session

```bash
# Find the conversation
$ gobbler claude list
┃ Tab ID     ┃ Title                    ┃
│ 1234567890 │ Claude - Research Help   │

# Send a message
$ gobbler claude query "What is machine learning?"
Sending to: Claude - Research Help
Message: What is machine learning?

Response:
Machine learning is a subset of artificial intelligence...

# Get chat history
$ gobbler claude history --count 4
[Shows last 4 messages in conversation]
```

---

## Tips

1. **One message at a time** - NEVER send parallel messages to the same conversation
2. **Wait for completion** - The command waits for Claude to finish responding
3. **Use appropriate timeouts** - Default 150s works for most cases, increase for long responses
4. **Check last response** - Use `gobbler claude last` if output looks truncated
