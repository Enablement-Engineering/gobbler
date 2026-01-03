# ChatGPT Integration

Send messages to and receive responses from ChatGPT through the Gobbler CLI.

**Requires**: Browser extension, ChatGPT tab in "Gobbler" group

## Critical: One Message at a Time

!!! warning "Sequential Messages Only"
    **Send only ONE message at a time to each conversation, then WAIT for the response.**
    
    If you send multiple messages in parallel, you will get mismatched message/response pairs.

## Quick Workflow

```bash
# 1. List available ChatGPT tabs
gobbler chatgpt list

# 2. Send message and get response
gobbler chatgpt query "Your message here"

# 3. If response looks incomplete
gobbler chatgpt last
```

## CLI Commands

### List Conversations

```bash
gobbler chatgpt list
```

### Send Message

```bash
# Basic message
gobbler chatgpt query "Explain quantum computing in simple terms"

# With longer timeout
gobbler chatgpt query "Write a detailed analysis" --timeout 300

# Target specific tab
gobbler chatgpt query "Continue our discussion" --tab 1234567
```

**Options**:

- `--timeout SECONDS` - Max wait time (default: 150)
- `--tab TAB_ID` - Target specific tab

### Get Last Response

```bash
gobbler chatgpt last
```

### Get Chat History

```bash
gobbler chatgpt history --count 10
gobbler chatgpt history --all
```

### Get Conversation Info

```bash
gobbler chatgpt info
```

## Prerequisites

1. Browser extension installed
2. ChatGPT tab open at `chatgpt.com` or `chat.openai.com`
3. Tab in a group named exactly "Gobbler"

## Example Session

```bash
# Check connection
$ gobbler relay status
Relay daemon is running (PID 10007)
1 browser extension(s) connected

# Find the conversation
$ gobbler chatgpt list
| Tab ID     | Title                   |
| 1234567890 | ChatGPT - Research Help |

# Send a message
$ gobbler chatgpt query "What is machine learning?"
Sending to: ChatGPT - Research Help

Response:
Machine learning is a subset of artificial intelligence...
```

## Troubleshooting

| Issue | Check | Fix |
|-------|-------|-----|
| No tabs found | Tab in "Gobbler" group? | Right-click → Add to group → "Gobbler" |
| API not injected | Extension reloaded? | Reload extension, refresh ChatGPT |
| Relay error | Relay running? | `gobbler relay start` |
| Timeout | Response too long? | Increase `--timeout` |
| Truncated | Terminal limit | Run `gobbler chatgpt last` |

## Tips

1. **One message at a time** - NEVER send parallel messages
2. **Wait for completion** - The command waits for ChatGPT to finish
3. **Check last response** - Use `gobbler chatgpt last` if truncated
4. **Refresh if stuck** - If unresponsive, refresh and retry
