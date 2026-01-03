# Claude.ai Integration

Send messages to and receive responses from Claude.ai through the Gobbler CLI.

**Requires**: Browser extension, Claude.ai tab in "Gobbler" group

## Critical: One Message at a Time

!!! warning "Sequential Messages Only"
    **Send only ONE message at a time to each conversation, then WAIT for the response.**
    
    If you send multiple messages in parallel, you will get mismatched message/response pairs.

## Quick Workflow

```bash
# 1. List available Claude.ai tabs
gobbler claude list

# 2. Send message and get response
gobbler claude query "Your message here"

# 3. If response looks incomplete
gobbler claude last
```

## CLI Commands

### List Conversations

```bash
gobbler claude list
```

### Send Message

```bash
# Basic message
gobbler claude query "Explain quantum computing in simple terms"

# With longer timeout
gobbler claude query "Write a detailed analysis" --timeout 300

# Target specific tab
gobbler claude query "Continue our discussion" --tab 1234567
```

**Options**:

- `--timeout SECONDS` - Max wait time (default: 150)
- `--tab TAB_ID` - Target specific tab

### Get Last Response

```bash
gobbler claude last
```

### Get Chat History

```bash
gobbler claude history --count 10
gobbler claude history --all
```

### Get Conversation Info

```bash
gobbler claude info
```

## Prerequisites

1. Browser extension installed
2. Claude.ai tab open at `claude.ai/chat/...`
3. Tab in a group named exactly "Gobbler"

## Example Session

```bash
# Find the conversation
$ gobbler claude list
| Tab ID     | Title                  |
| 1234567890 | Claude - Research Help |

# Send a message
$ gobbler claude query "What is machine learning?"
Sending to: Claude - Research Help

Response:
Machine learning is a subset of artificial intelligence...

# Get chat history
$ gobbler claude history --count 4
```

## Troubleshooting

| Issue | Fix |
|-------|-----|
| No tabs found | Add Claude.ai tab to "Gobbler" group |
| Input field not found | Refresh the Claude.ai page |
| Timeout | Increase `--timeout` for long responses |
| Truncated response | Run `gobbler claude last` |
