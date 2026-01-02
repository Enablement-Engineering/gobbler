---
name: notebooklm
description: "Query Google NotebookLM notebooks via browser automation. Use when user wants to ask NotebookLM questions, get chat history, or interact with their research notebooks."
version: 2.2.0
---

# NotebookLM Integration

Query NotebookLM notebooks through the Gobbler CLI. The browser extension connects to NotebookLM tabs and allows sending queries and retrieving responses.

## CRITICAL: One Query at a Time

**NotebookLM can only process ONE query at a time per notebook.** 

- NEVER send multiple queries in parallel to the same notebook
- ALWAYS wait for a response before sending the next query
- If you need to query multiple topics, send them SEQUENTIALLY with 3-second delays

**For parallel research:** Open multiple notebooks in separate tabs, then query each tab by its ID:
```bash
gobbler notebooklm query "Question for notebook 1" --tab 123456
gobbler notebooklm query "Question for notebook 2" --tab 789012
```

## Prerequisites

Before using NotebookLM commands:

1. **Browser extension installed** - Load `browser-extension/` folder in Chrome
2. **NotebookLM tab in "Gobbler" tab group** - Right-click tab → "Add to group" → name it "Gobbler"
3. **Relay server running** - Auto-starts, or run `gobbler relay start`

## Quick Workflow

```bash
# 1. Check connection (extension must be connected)
gobbler relay status

# 2. List available NotebookLM tabs
gobbler notebooklm list

# 3. Send a query and wait for response
gobbler notebooklm query "Your question here" --timeout 120

# 4. Get the complete response (always do this)
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

Send a question to NotebookLM and wait for the response.

```bash
# Basic query
gobbler notebooklm query "What are the main themes?"

# With longer timeout for complex questions
gobbler notebooklm query "Analyze all sources in detail" --timeout 180

# Target specific notebook by tab ID
gobbler notebooklm query "Summarize" --tab 1700453262
```

**Options**:
- `--timeout SECONDS` - Max wait time (default: 90, increase for complex queries)
- `--tab TAB_ID` - Target specific tab instead of first NotebookLM tab

**Important**: The query command may truncate long responses in the terminal. Always use `gobbler notebooklm last` to get the complete response.

### `gobbler notebooklm last`

Get the last/most recent response from the chat. **Use this after every query** to ensure you have the complete response.

```bash
gobbler notebooklm last
```

### `gobbler notebooklm history`

Get chat history from the notebook.

```bash
# Get last 5 messages
gobbler notebooklm history --count 5

# Get all messages
gobbler notebooklm history --all
```

### `gobbler notebooklm info`

Get notebook metadata (title, ID, source count).

```bash
gobbler notebooklm info
```

---

## Recommended Workflow for AI Agents

**IMPORTANT: Execute these steps SEQUENTIALLY, never in parallel.**

### Step 1: Verify Connection

```bash
gobbler relay status
```

Expected: "1 browser extension(s) connected"

If not connected:
- Check extension is loaded in browser
- Ensure a tab is in "Gobbler" tab group
- Reload extension if needed

### Step 2: Identify Target Notebook

```bash
gobbler notebooklm list
```

Note the Tab ID if you have multiple notebooks open.

### Step 3: Send Query (ONE AT A TIME)

```bash
gobbler notebooklm query "Your question" --timeout 120
```

**Timeout guidelines**:
- Simple questions: 60 seconds
- Standard analysis: 90-120 seconds  
- Complex multi-source analysis: 180 seconds

### Step 4: Get Full Response

```bash
gobbler notebooklm last
```

**Always run this** after a query to ensure you capture the complete response.

### Step 5: Follow-up Questions (SEQUENTIAL ONLY)

Wait 3 seconds, then send the next query:

```bash
# Wait 3 seconds before next query
gobbler notebooklm query "Follow-up question" --timeout 120
gobbler notebooklm last
```

### Multiple Notebooks Pattern

If you need to query multiple topics in parallel, use DIFFERENT notebooks:

```bash
# First, list all notebooks
gobbler notebooklm list

# Query different notebooks by tab ID (these CAN be parallel)
gobbler notebooklm query "Question A" --tab 111111 --timeout 120
gobbler notebooklm query "Question B" --tab 222222 --timeout 120

# Then get responses
gobbler notebooklm last --tab 111111
gobbler notebooklm last --tab 222222
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
