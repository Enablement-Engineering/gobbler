---
name: gobbler-gemini
description: "Interact with Google Gemini conversations via browser automation. Use when user wants to send messages to Gemini, get chat history, or automate Gemini interactions in the browser."
version: 1.0.0
---

# Gemini Integration

Send messages to and receive responses from Google Gemini through the Gobbler CLI. The browser extension connects to Gemini tabs and enables automation.

## CRITICAL: One Message at a Time Per Conversation

**Send only ONE message at a time to each conversation, then WAIT for the response.**

Why? The query command waits for the "last message" in the chat. If you send multiple messages in parallel:
- All messages get submitted to Gemini
- The first message's script may return the WRONG answer (from a later message)
- You get mismatched message/response pairs

**Correct pattern:**
```bash
# Sequential - CORRECT
gobbler gemini query "Question 1" --timeout 120
# Wait for response, then:
gobbler gemini query "Question 2" --timeout 120
```

**Wrong pattern:**
```bash
# Parallel - WRONG (will get mismatched answers)
gobbler gemini query "Question 1" &
gobbler gemini query "Question 2" &
```

## Prerequisites

1. **Browser extension installed** - Load `browser-extension/` folder in Chrome
2. **Gemini tab in "Gobbler" group** - Right-click tab -> "Add to group" -> name it "Gobbler"
3. **Relay running** - Auto-starts when you run commands
4. **Signed into Google** - Gemini requires a Google account

## Quick Workflow

```bash
# 1. List available Gemini tabs
gobbler gemini list

# 2. Send message and get response (waits for complete answer)
gobbler gemini query "Your message here"

# 3. If response looks incomplete, get full last response
gobbler gemini last
```

---

## CLI Commands

### `gobbler gemini list`

List all Gemini tabs in the Gobbler tab group.

```bash
gobbler gemini list
```

**Output**: Table with Tab ID and conversation title.

### `gobbler gemini info`

Get conversation metadata.

```bash
# Use first available Gemini tab
gobbler gemini info

# Target specific tab
gobbler gemini info -t 1234567
gobbler gemini info --tab 1234567
```

**Options**:
- `-t, --tab TAB_ID` - Target specific tab instead of first Gemini tab

### `gobbler gemini query`

Send a message to Gemini and wait for the complete response.

```bash
# Basic message (waits for full response)
gobbler gemini query "Explain quantum computing in simple terms"

# With longer timeout for complex responses
gobbler gemini query "Write a detailed analysis" --timeout 300

# Target specific tab by ID
gobbler gemini query "Continue our discussion" -t 1234567
gobbler gemini query "Continue our discussion" --tab 1234567
```

**Options**:
- `-t, --tab TAB_ID` - Target specific tab instead of first Gemini tab
- `--timeout SECONDS` - Max wait time (default: 150 / 2.5 min)

The command waits until the response text is stable for 3 seconds before returning.

### `gobbler gemini last`

Get the last/most recent response from Gemini. Use as a backup if the query response looks incomplete.

```bash
# Use first available Gemini tab
gobbler gemini last

# Target specific tab
gobbler gemini last -t 1234567
gobbler gemini last --tab 1234567
```

**Options**:
- `-t, --tab TAB_ID` - Target specific tab instead of first Gemini tab

### `gobbler gemini history`

Get chat history from the conversation.

```bash
# Get last 10 messages (default)
gobbler gemini history

# Get last N messages
gobbler gemini history -n 5
gobbler gemini history --count 20

# Get all messages
gobbler gemini history -a
gobbler gemini history --all

# Target specific tab
gobbler gemini history -t 1234567 -n 5
```

**Options**:
- `-t, --tab TAB_ID` - Target specific tab instead of first Gemini tab
- `-n, --count N` - Number of messages to show (default: 10)
- `-a, --all` - Show all messages

### `gobbler gemini download`

Download images from the last Gemini response.

```bash
# Download to current directory
gobbler gemini download

# Download to specific directory
gobbler gemini download -o ./images
gobbler gemini download --output /path/to/folder

# Target specific tab
gobbler gemini download -t 1234567 -o ./images
```

**Options**:
- `-o, --output PATH` - Output directory for images
- `-t, --tab TAB_ID` - Target specific tab instead of first Gemini tab

---

## Recommended Workflow for AI Agents

### Step 1: List Conversations

```bash
gobbler gemini list
```

Note the Tab ID if you have multiple Gemini tabs.

### Step 2: Send Message and Wait

```bash
gobbler gemini query "Your message" --timeout 150
```

The command returns the complete response. **Wait for it to finish before sending another message.**

### Step 3: Verify Response (if needed)

If the response looks cut off:

```bash
gobbler gemini last
```

### Step 4: Follow-up Messages

Send the next message only AFTER the previous one completes:

```bash
gobbler gemini query "Follow-up message"
```

---

## Error Handling

### "No Gemini tabs found"

The tab must be:
1. Open in the browser at gemini.google.com
2. In a tab group named exactly "Gobbler"

### "Gobbler Gemini API not injected"

- Reload the browser extension in chrome://extensions
- Refresh the Gemini page
- Make sure the tab is in the Gobbler group

### "Could not find chat input field"

- Make sure you're on a conversation page (gemini.google.com/app/...)
- The page may have changed - try refreshing

### Timeout errors

Increase the timeout for long responses:

```bash
gobbler gemini query "Complex question" --timeout 300
```

---

## Example Session

```bash
# Check everything is connected
$ gobbler relay status
Relay daemon is running (PID 10007)
1 browser extension(s) connected

# Find the conversation
$ gobbler gemini list
         Gemini Tabs
| Tab ID     | Title                    |
| 1234567890 | Google Gemini            |

# Send a message
$ gobbler gemini query "What is machine learning?"
Sending to: Google Gemini
Message: What is machine learning?

Response:
Machine learning is a subset of artificial intelligence...

# Get chat history
$ gobbler gemini history -n 4
[Shows last 4 messages in conversation]

# Download any images from last response
$ gobbler gemini download -o ./gemini-images
```

---

## Streaming Detection

Gemini streaming is detected by checking the response container's style:
- **Streaming**: `height` is NOT `auto`
- **Complete**: `style="height: auto;"`

The API uses text stability checks (3 consecutive polls with identical content) to ensure the response is complete.

---

## Troubleshooting Checklist

| Issue | Check | Fix |
|-------|-------|-----|
| No tabs found | Tab in "Gobbler" group? | Right-click tab -> Add to group -> "Gobbler" |
| API not injected | Extension reloaded? | Reload extension, then refresh Gemini page |
| Not connected | Extension loaded? | chrome://extensions -> Load unpacked |
| Relay error | Relay running? | `gobbler relay start` |
| Timeout | Response too long? | Increase `--timeout` or simplify query |
| Truncated | Terminal limit | Run `gobbler gemini last` |
| Garbled response | Parallel queries sent? | STOP. Wait. Query ONE at a time. |
| No response | Previous query still running? | Wait for it to complete, then retry |
| Regional block | Gemini available in region? | Check Google Gemini availability |

## Common Mistakes to Avoid

1. **Sending multiple queries in parallel** - This will cause failures or garbled responses
2. **Not waiting for response** - Always wait for query to complete before sending another
3. **Not using `last` command** - Query output may be truncated; always verify with `last`
4. **Short timeouts** - Gemini can take time for complex queries

---

## Technical Notes

### Angular Framework
Gemini is built with Angular and uses custom components:
- `rich-textarea` - Custom textarea component with Quill editor
- `structured-content-container` - Response container
- `message-content` - Message text wrapper

### Quill Editor
The input uses Quill rich text editor:
- Contenteditable div with class `ql-editor`
- Requires dispatching both `input` and `change` events

---

## Tips

1. **One message at a time** - NEVER send parallel messages to the same conversation
2. **Wait for completion** - The command waits for Gemini to finish responding
3. **Use appropriate timeouts** - Default 150s works for most cases, increase for long responses
4. **Check last response** - Use `gobbler gemini last` if output looks truncated
5. **Refresh if stuck** - If the page is unresponsive, refresh and try again
6. **Google account required** - Make sure you're signed into Google
