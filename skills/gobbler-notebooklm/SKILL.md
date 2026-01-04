---
name: gobbler-notebooklm
description: "Query Google NotebookLM notebooks via browser automation. Use when user wants to ask NotebookLM questions, get chat history, or interact with their research notebooks."
version: 2.3.0
---

# NotebookLM Integration

Query NotebookLM notebooks through the Gobbler CLI. The browser extension connects to NotebookLM tabs and allows sending queries and retrieving responses.

## CRITICAL: One Query at a Time Per Notebook

**Send only ONE query at a time to each notebook, then WAIT for the response.**

Why? The query command waits for the "last message" in the chat. If you send multiple queries in parallel:
- All questions get submitted to NotebookLM
- The first query's script may return the WRONG answer (from a later question)
- You get mismatched question/answer pairs

**Correct pattern:**
```bash
# Sequential - CORRECT
gobbler notebooklm query "Question 1" --timeout 120
# Wait for response, then:
gobbler notebooklm query "Question 2" --timeout 120
```

**Wrong pattern:**
```bash
# Parallel - WRONG (will get mismatched answers)
gobbler notebooklm query "Question 1" &
gobbler notebooklm query "Question 2" &
```

## Prerequisites

1. **Browser extension installed** - Load `browser-extension/` folder in Chrome
2. **NotebookLM tab in "Gobbler" group** - Right-click tab → "Add to group" → name it "Gobbler"
3. **Relay running** - Auto-starts when you run commands

## Quick Workflow

```bash
# 1. Inject APIs (required after page refresh or extension reload)
gobbler browser inject

# 2. List available NotebookLM tabs
gobbler notebooklm list

# 3. Send query and get response (waits for complete answer)
gobbler notebooklm query "Your question here" --timeout 120

# 4. If response looks incomplete, get full last response
gobbler notebooklm last
```

---

## CLI Commands

### `gobbler notebooklm list`

List all NotebookLM tabs in the Gobbler tab group.

```bash
gobbler notebooklm list
```

**Output**: Table with Tab ID and notebook title.

### `gobbler notebooklm query`

Send a question to NotebookLM and wait for the complete response.

```bash
# Basic query (waits for full response)
gobbler notebooklm query "What are the main themes?"

# With longer timeout for complex questions
gobbler notebooklm query "Analyze all sources in detail" --timeout 180

# Target specific notebook by tab ID
gobbler notebooklm query "Summarize" --tab 1700453262
```

**Options**:
- `--timeout SECONDS` - Max wait time (default: 150 seconds / 2.5 min)
- `-t/--tab TAB_ID` - Target specific tab instead of first NotebookLM tab

The command waits until the response text is stable for 3 seconds before returning.

### `gobbler notebooklm last`

Get the last/most recent response from the chat. Use as a backup if the query response looks incomplete.

```bash
gobbler notebooklm last

# Target specific notebook by tab ID
gobbler notebooklm last --tab 1700453262
```

**Options**:
- `-t/--tab TAB_ID` - Target specific tab instead of first NotebookLM tab

### `gobbler notebooklm history`

Get chat history from the notebook.

```bash
# Get last 5 messages (default)
gobbler notebooklm history

# Get last 10 messages
gobbler notebooklm history --count 10

# Get all messages
gobbler notebooklm history --all

# Target specific notebook by tab ID
gobbler notebooklm history --tab 1700453262
```

**Options**:
- `-n/--count N` - Number of messages to show (default: 5)
- `-a/--all` - Show all messages
- `-t/--tab TAB_ID` - Target specific tab instead of first NotebookLM tab

### `gobbler notebooklm info`

Get notebook metadata (title, ID, source count).

```bash
gobbler notebooklm info

# Target specific notebook by tab ID
gobbler notebooklm info --tab 1700453262
```

**Options**:
- `-t/--tab TAB_ID` - Target specific tab instead of first NotebookLM tab

---

## Recommended Workflow for AI Agents

### Step 1: Inject APIs

Always inject APIs first to ensure they're available (required after page refresh or extension reload):

```bash
gobbler browser inject
```

### Step 2: List Notebooks

```bash
gobbler notebooklm list
```

Note the Tab ID if you have multiple notebooks.

### Step 3: Send Query and Wait

```bash
gobbler notebooklm query "Your question" --timeout 120
```

The command returns the complete response. **Wait for it to finish before sending another query.**

**Timeout**: Default is 150 seconds (2.5 minutes). For very complex queries, increase with `--timeout 300`.

### Step 4: Verify Response (if needed)

If the response looks cut off:

```bash
gobbler notebooklm last
```

### Step 5: Follow-up Questions

Send the next query only AFTER the previous one completes:

```bash
gobbler notebooklm query "Follow-up question" --timeout 120
```

---

## Error Handling

### "No NotebookLM tabs found"

The notebook must be:
1. Open in the browser
2. In a tab group named exactly "Gobbler"
3. On a notebook page (not the NotebookLM home page)

### "Relay not running" or "No extensions connected"

```bash
gobbler relay start
gobbler relay status
```

Then check the browser extension popup shows "Connected".

### Timeout errors

Increase the timeout:

```bash
gobbler notebooklm query "Complex question" --timeout 180
```

If still timing out, the question may be too complex. Try breaking it into smaller queries.

### Truncated response

The terminal may truncate long responses. Always use:

```bash
gobbler notebooklm last
```

---

## Example Session

```bash
# Check everything is connected
$ gobbler relay status
✓ Relay daemon is running (PID 10007)
✓ 1 browser extension(s) connected

# Find the notebook
$ gobbler notebooklm list
┃ Tab ID     ┃ Title                                    ┃
│ 1700453262 │ Research Notes - NotebookLM              │

# Ask a question
$ gobbler notebooklm query "What are the key findings from the research?"
Sending to: Research Notes - NotebookLM
Query: What are the key findings from the research?
Response: Based on the sources...

# Get complete response (always do this)
$ gobbler notebooklm last
[Full response with citations]
```

---

## Tips for Effective Queries

1. **One query at a time** - NEVER send parallel queries to the same notebook
2. **Be specific** - "What does source X say about Y?" works better than vague questions
3. **Reference sources** - NotebookLM responds better when you mention specific sources
4. **Ask for citations** - Add "with citations" to get source references
5. **One topic per query** - Break complex questions into focused queries
6. **Use follow-ups** - Build on previous responses rather than asking everything at once
7. **Always get full response** - Run `gobbler notebooklm last` after every query

---

## Troubleshooting Checklist

| Issue | Check | Fix |
|-------|-------|-----|
| No tabs found | Tab in "Gobbler" group? | Right-click tab → Add to group → "Gobbler" |
| Not connected | Extension loaded? | chrome://extensions → Load unpacked |
| Relay error | Relay running? | `gobbler relay start` |
| Timeout | Question too complex? | Increase `--timeout` or simplify query |
| Truncated | Terminal limit | Run `gobbler notebooklm last` |
| Garbled response | Parallel queries sent? | STOP. Wait. Query ONE at a time. |
| No response | Previous query still running? | Wait for it to complete, then retry |

## Common Mistakes to Avoid

1. **Sending multiple queries in parallel** - This will cause failures or garbled responses
2. **Not waiting for response** - Always wait for query to complete before sending another
3. **Not using `last` command** - Query output may be truncated; always verify with `last`
4. **Short timeouts** - NotebookLM can take 60-120 seconds for complex queries
