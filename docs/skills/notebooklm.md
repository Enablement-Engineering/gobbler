---
icon: material/notebook
---

# NotebookLM Integration

Query Google NotebookLM notebooks through the Gobbler CLI.

**Requires**: Browser extension, NotebookLM tab in "Gobbler" group

## Critical: One Query at a Time

!!! warning "Sequential Queries Only"
    **Send only ONE query at a time to each notebook, then WAIT for the response.**
    
    If you send multiple queries in parallel, you will get mismatched question/answer pairs.

```bash
# Correct - Sequential
gobbler notebooklm query "Question 1" --timeout 120
# Wait for response, then:
gobbler notebooklm query "Question 2" --timeout 120

# Wrong - Parallel (will fail)
gobbler notebooklm query "Question 1" &
gobbler notebooklm query "Question 2" &
```

## Quick Workflow

```bash
# 1. List available NotebookLM tabs
gobbler notebooklm list

# 2. Send query and get response
gobbler notebooklm query "Your question here" --timeout 120

# 3. If response looks incomplete, get full last response
gobbler notebooklm last
```

## CLI Commands

### List Notebooks

```bash
gobbler notebooklm list
```

Shows all NotebookLM tabs in the Gobbler group with Tab ID and title.

### Send Query

```bash
# Basic query (waits for full response)
gobbler notebooklm query "What are the main themes?"

# With longer timeout for complex questions
gobbler notebooklm query "Analyze all sources in detail" --timeout 180

# Target specific notebook by tab ID
gobbler notebooklm query "Summarize" --tab 1700453262
```

**Options**:

- `--timeout SECONDS` - Max wait time (default: 150)
- `--tab TAB_ID` - Target specific tab

### Get Last Response

```bash
gobbler notebooklm last
```

Use as a backup if the query response looks incomplete.

### Get Chat History

```bash
# Get last 5 messages
gobbler notebooklm history --count 5

# Get all messages
gobbler notebooklm history --all
```

### Get Notebook Info

```bash
gobbler notebooklm info
```

Returns notebook title, ID, and source count.

## Prerequisites

1. Browser extension installed
2. NotebookLM tab open at `notebooklm.google.com/notebook/...`
3. Tab in a group named exactly "Gobbler"
4. Relay running (auto-starts)

## Tips for Effective Queries

1. **One query at a time** - NEVER send parallel queries
2. **Be specific** - "What does source X say about Y?"
3. **Reference sources** - NotebookLM responds better when you mention sources
4. **Ask for citations** - Add "with citations" to get source references
5. **One topic per query** - Break complex questions into focused queries
6. **Always get full response** - Run `gobbler notebooklm last` after every query

## Troubleshooting

| Issue | Check | Fix |
|-------|-------|-----|
| No tabs found | Tab in "Gobbler" group? | Right-click tab → Add to group → "Gobbler" |
| Not connected | Extension loaded? | chrome://extensions → Load unpacked |
| Relay error | Relay running? | `gobbler relay start` |
| Timeout | Question too complex? | Increase `--timeout` or simplify query |
| Truncated | Terminal limit | Run `gobbler notebooklm last` |
| Garbled response | Parallel queries? | Query ONE at a time |
