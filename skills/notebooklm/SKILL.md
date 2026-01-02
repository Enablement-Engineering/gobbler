---
name: notebooklm
description: "Query Google NotebookLM notebooks via browser automation. Use when user wants to ask NotebookLM questions, get chat history, or interact with their research notebooks."
version: 2.1.0
---

# NotebookLM Integration

Query NotebookLM notebooks through the Gobbler CLI. The browser extension connects to NotebookLM tabs and allows sending queries and retrieving responses.

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
gobbler notebooklm query "Your question here"

# 4. If response was truncated, get full last response
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

When querying NotebookLM, follow this pattern:

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

### Step 3: Send Query

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

### Step 5: Follow-up Questions

Wait 2-3 seconds between queries to avoid rate limiting:

```bash
gobbler notebooklm query "Follow-up question" --timeout 90
gobbler notebooklm last
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

1. **Be specific** - "What does source X say about Y?" works better than vague questions
2. **Reference sources** - NotebookLM responds better when you mention specific sources
3. **Ask for citations** - Add "with citations" to get source references
4. **One topic per query** - Break complex questions into focused queries
5. **Use follow-ups** - Build on previous responses rather than asking everything at once

---

## Troubleshooting Checklist

| Issue | Check | Fix |
|-------|-------|-----|
| No tabs found | Tab in "Gobbler" group? | Right-click tab → Add to group → "Gobbler" |
| Not connected | Extension loaded? | chrome://extensions → Load unpacked |
| Relay error | Relay running? | `gobbler relay start` |
| Timeout | Question too complex? | Increase `--timeout` or simplify query |
| Truncated | Terminal limit | Run `gobbler notebooklm last` |
