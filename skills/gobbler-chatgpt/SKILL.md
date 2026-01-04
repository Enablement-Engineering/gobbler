---
name: gobbler-chatgpt
description: "Interact with ChatGPT conversations via browser automation. Use when user wants to send messages to ChatGPT, get chat history, or automate ChatGPT interactions in the browser."
version: 1.0.0
---

# ChatGPT Integration

Send messages to and receive responses from ChatGPT through the Gobbler CLI. The browser extension connects to ChatGPT tabs and enables automation.

## CRITICAL: One Message at a Time Per Conversation

**Send only ONE message at a time to each conversation, then WAIT for the response.**

Why? The query command waits for the "last message" in the chat. If you send multiple messages in parallel:
- All messages get submitted to ChatGPT
- The first message's script may return the WRONG answer (from a later message)
- You get mismatched message/response pairs

**Correct pattern:**
```bash
# Sequential - CORRECT
gobbler chatgpt query "Question 1" --timeout 120
# Wait for response, then:
gobbler chatgpt query "Question 2" --timeout 120
```

**Wrong pattern:**
```bash
# Parallel - WRONG (will get mismatched answers)
gobbler chatgpt query "Question 1" &
gobbler chatgpt query "Question 2" &
```

## Prerequisites

1. **Browser extension installed** - Load `browser-extension/` folder in Chrome
2. **ChatGPT tab in "Gobbler" group** - Right-click tab → "Add to group" → name it "Gobbler"
3. **Relay running** - Auto-starts when you run commands

## Quick Workflow

```bash
# 1. List available ChatGPT tabs
gobbler chatgpt list

# 2. Send message and get response (waits for complete answer)
gobbler chatgpt query "Your message here"

# 3. If response looks incomplete, get full last response
gobbler chatgpt last
```

---

## CLI Commands

### `gobbler chatgpt list`

List all ChatGPT tabs in the Gobbler tab group.

```bash
gobbler chatgpt list
```

**Output**: Table with Tab ID and conversation title.

### `gobbler chatgpt query`

Send a message to ChatGPT and wait for the complete response.

```bash
# Basic message (waits for full response)
gobbler chatgpt query "Explain quantum computing in simple terms"

# With longer timeout for complex responses
gobbler chatgpt query "Write a detailed analysis" --timeout 300

# Target specific tab by ID
gobbler chatgpt query "Continue our discussion" -t 1234567
```

**Options**:
- `-t, --tab TAB_ID` - Target specific tab instead of first ChatGPT tab
- `--timeout SECONDS` - Max wait time (default: 150 / 2.5 min)

The command waits until the response text is stable for 3 seconds before returning.

### `gobbler chatgpt last`

Get the last/most recent response from ChatGPT. Use as a backup if the query response looks incomplete.

```bash
# Get last response from first ChatGPT tab
gobbler chatgpt last

# Get last response from specific tab
gobbler chatgpt last -t 1234567
```

**Options**:
- `-t, --tab TAB_ID` - Target specific tab instead of first ChatGPT tab

### `gobbler chatgpt history`

Get chat history from the conversation.

```bash
# Get last 10 messages (default)
gobbler chatgpt history

# Get last N messages
gobbler chatgpt history -n 20

# Get all messages
gobbler chatgpt history -a

# Get history from specific tab
gobbler chatgpt history -t 1234567 -n 5
```

**Options**:
- `-t, --tab TAB_ID` - Target specific tab instead of first ChatGPT tab
- `-n, --count N` - Number of messages to show (default: 10)
- `-a, --all` - Show all messages

### `gobbler chatgpt info`

Get conversation metadata.

```bash
# Get info from first ChatGPT tab
gobbler chatgpt info

# Get info from specific tab
gobbler chatgpt info -t 1234567
```

**Options**:
- `-t, --tab TAB_ID` - Target specific tab instead of first ChatGPT tab

### `gobbler chatgpt download`

Download images from the last ChatGPT response (e.g., DALL-E generated images).

```bash
# Download to current directory
gobbler chatgpt download

# Download to specific directory
gobbler chatgpt download -o ./images

# Download from specific tab
gobbler chatgpt download -t 1234567 -o ./images
```

**Options**:
- `-o, --output DIR` - Output directory for images
- `-t, --tab TAB_ID` - Target specific tab instead of first ChatGPT tab

---

## Recommended Workflow for AI Agents

### Step 1: List Conversations

```bash
gobbler chatgpt list
```

Note the Tab ID if you have multiple ChatGPT tabs.

### Step 2: Send Message and Wait

```bash
gobbler chatgpt query "Your message" --timeout 150
```

The command returns the complete response. **Wait for it to finish before sending another message.**

### Step 3: Verify Response (if needed)

If the response looks cut off:

```bash
gobbler chatgpt last
```

### Step 4: Follow-up Messages

Send the next message only AFTER the previous one completes:

```bash
gobbler chatgpt query "Follow-up message"
```

---

## Error Handling

### "No ChatGPT tabs found"

The tab must be:
1. Open in the browser at chatgpt.com or chat.openai.com
2. In a tab group named exactly "Gobbler"

### "Gobbler ChatGPT API not injected"

- Reload the browser extension in chrome://extensions
- Refresh the ChatGPT page
- Make sure the tab is in the Gobbler group

### "Could not find chat input field"

- Make sure you're on a conversation page (chatgpt.com/c/...)
- The page may have changed - try refreshing

### Timeout errors

Increase the timeout for long responses:

```bash
gobbler chatgpt query "Complex question" --timeout 300
```

---

## Example Session

```bash
# Check everything is connected
$ gobbler relay status
Relay daemon is running (PID 10007)
1 browser extension(s) connected

# Find the conversation
$ gobbler chatgpt list
         ChatGPT Tabs
| Tab ID     | Title                    |
| 1234567890 | ChatGPT - Research Help  |

# Send a message
$ gobbler chatgpt query "What is machine learning?"
Sending to: ChatGPT - Research Help
Message: What is machine learning?

Response:
Machine learning is a subset of artificial intelligence...

# Get chat history
$ gobbler chatgpt history --count 4
[Shows last 4 messages in conversation]
```

---

## Troubleshooting Checklist

| Issue | Check | Fix |
|-------|-------|-----|
| No tabs found | Tab in "Gobbler" group? | Right-click tab → Add to group → "Gobbler" |
| API not injected | Extension reloaded? | Reload extension, then refresh ChatGPT page |
| Not connected | Extension loaded? | chrome://extensions → Load unpacked |
| Relay error | Relay running? | `gobbler relay start` |
| Timeout | Response too long? | Increase `--timeout` or simplify query |
| Truncated | Terminal limit | Run `gobbler chatgpt last` |
| Garbled response | Parallel queries sent? | STOP. Wait. Query ONE at a time. |
| No response | Previous query still running? | Wait for it to complete, then retry |

## Common Mistakes to Avoid

1. **Sending multiple queries in parallel** - This will cause failures or garbled responses
2. **Not waiting for response** - Always wait for query to complete before sending another
3. **Not using `last` command** - Query output may be truncated; always verify with `last`
4. **Short timeouts** - ChatGPT can take time for complex queries

---

## Tips

1. **One message at a time** - NEVER send parallel messages to the same conversation
2. **Wait for completion** - The command waits for ChatGPT to finish responding
3. **Use appropriate timeouts** - Default 150s works for most cases, increase for long responses
4. **Check last response** - Use `gobbler chatgpt last` if output looks truncated
5. **Refresh if stuck** - If the page is unresponsive, refresh and try again
