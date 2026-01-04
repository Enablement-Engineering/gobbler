---
icon: material/google
---

# Gemini Integration

Send messages to and receive responses from Google Gemini through the Gobbler CLI.

**Requires**: Browser extension, Gemini tab in "Gobbler" group, Google account

## Critical: One Message at a Time

!!! warning "Sequential Messages Only"
    **Send only ONE message at a time to each conversation, then WAIT for the response.**
    
    If you send multiple messages in parallel, you will get mismatched message/response pairs.

## Quick Workflow

```bash
# 1. List available Gemini tabs
gobbler gemini list

# 2. Send message and get response
gobbler gemini query "Your message here"

# 3. If response looks incomplete
gobbler gemini last
```

## CLI Commands

### List Conversations

```bash
gobbler gemini list
```

### Send Message

```bash
# Basic message
gobbler gemini query "Explain quantum computing in simple terms"

# With longer timeout
gobbler gemini query "Write a detailed analysis" --timeout 300

# Target specific tab
gobbler gemini query "Continue our discussion" --tab 1234567
```

**Options**:

- `--timeout SECONDS` - Max wait time (default: 150)
- `--tab TAB_ID` - Target specific tab

### Get Last Response

```bash
gobbler gemini last
```

### Get Chat History

```bash
gobbler gemini history --count 10
gobbler gemini history --all
```

### Get Conversation Info

```bash
gobbler gemini info
```

## Prerequisites

1. Browser extension installed
2. Gemini tab open at `gemini.google.com`
3. Tab in a group named exactly "Gobbler"
4. Signed into Google account

## Example Session

```bash
# Check connection
$ gobbler relay status
Relay daemon is running (PID 10007)
1 browser extension(s) connected

# Find the conversation
$ gobbler gemini list
| Tab ID     | Title         |
| 1234567890 | Google Gemini |

# Send a message
$ gobbler gemini query "What is machine learning?"
Sending to: Google Gemini

Response:
Machine learning is a subset of artificial intelligence...
```

## Troubleshooting

| Issue | Check | Fix |
|-------|-------|-----|
| No tabs found | Tab in "Gobbler" group? | Right-click → Add to group → "Gobbler" |
| API not injected | Extension reloaded? | Reload extension, refresh Gemini |
| Relay error | Relay running? | `gobbler relay start` |
| Timeout | Response too long? | Increase `--timeout` |
| Truncated | Terminal limit | Run `gobbler gemini last` |
| Regional block | Gemini available? | Check Google Gemini availability |

## Tips

1. **One message at a time** - NEVER send parallel messages
2. **Wait for completion** - The command waits for Gemini to finish
3. **Check last response** - Use `gobbler gemini last` if truncated
4. **Google account required** - Make sure you're signed in
