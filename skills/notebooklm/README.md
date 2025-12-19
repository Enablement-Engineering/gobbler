# NotebookLM Integration Skill

A Claude Code skill that enables programmatic interaction with Google NotebookLM through browser automation.

## What This Skill Does

This skill allows Claude to:
- Send queries to your open NotebookLM chat
- Retrieve responses from NotebookLM's AI
- Access conversation history
- Extract insights from your notebooks programmatically

## Files

- **SKILL.md** - Main skill definition with YAML frontmatter and instructions
- **technical-reference.md** - Deep technical details about the API and DOM structure
- **usage-examples.md** - Concrete examples of common usage patterns

## Prerequisites

1. **Gobbler MCP Server** must be installed and configured in your Claude Code setup
2. **Gobbler Browser Extension** must be installed and connected
3. **NotebookLM** tab must be open with an active notebook

## Installation

This skill is already installed in your project at `.claude/skills/notebooklm/`.

To use it:
1. Restart Claude Code (skills are loaded at startup)
2. Open NotebookLM in your browser
3. Simply ask Claude to "query my NotebookLM about [topic]"

## How It Works

### Automatic Invocation

Claude automatically detects when to use this skill based on the description in the frontmatter. Keywords that trigger it:
- "NotebookLM"
- "query my notebook"
- "ask my notebook"
- "what does NotebookLM say about"

### Two-Phase Operation

1. **Initialization Phase**: Injects a JavaScript API (`window.NotebookLMAPI`) into the NotebookLM page
2. **Interaction Phase**: Uses the API to send messages and retrieve responses

### Browser Automation

The skill uses the Gobbler MCP server's browser automation tools:
- `mcp__gobbler-mcp__browser_check_connection` - Verify extension is ready
- `mcp__gobbler-mcp__browser_execute_script` - Execute JavaScript in the NotebookLM page

## Example Usage

### Simple Query
```
You: "Ask my NotebookLM what the main themes in the documents are"
```

Claude will:
1. Check browser connection
2. Initialize the NotebookLM API (if needed)
3. Send your question to NotebookLM
4. Wait for the response
5. Present the answer to you

### Follow-up Questions
```
You: "Ask it to explain that in more detail"
```

Claude reuses the existing API and sends a follow-up query.

### Conversation History
```
You: "What have I asked NotebookLM so far?"
```

Claude retrieves and summarizes the chat history.

## API Reference

The skill creates a `window.NotebookLMAPI` object with these methods:

| Method | Description |
|--------|-------------|
| `getChatInput()` | Get the chat textarea element |
| `getChatMessages()` | Get all messages with metadata |
| `getLatestAIResponse()` | Get most recent NotebookLM response |
| `getLatestUserMessage()` | Get most recent user message |
| `sendMessage(text)` | Send a message (don't wait for response) |
| `waitForResponse(count, timeout)` | Poll for new message |
| `chat(message, timeout)` | Send and wait for response (main method) |

## Workflow

```
User Request
    ↓
Claude detects "NotebookLM" keyword
    ↓
Skill activated
    ↓
Check browser connection
    ↓
Initialize API (if needed)
    ↓
Execute query via chat()
    ↓
Wait for response (polling)
    ↓
Return response to user
```

## Troubleshooting

| Problem | Solution |
|---------|----------|
| Skill not activating | Restart Claude Code to reload skills |
| "Browser extension not connected" | Check Gobbler extension is installed and active |
| "Chat input not found" | Ensure NotebookLM tab is open |
| Timeout errors | Increase timeout or check NotebookLM is responding |
| Partial responses | Wait longer before retrieving |

## Use Cases with Puter

This skill demonstrates several Puter architecture concepts:

1. **Component Interface** - Skill acts as a component with defined capabilities
2. **Tool Integration** - Uses MCP tools (Gobbler) as dependencies
3. **Async Operations** - Manages message send/receive lifecycle
4. **State Management** - Tracks conversation state via DOM queries

Potential integrations:
- Use NotebookLM as a RAG service for Puter's knowledge base
- Extract NotebookLM insights into Puter's inbox for processing
- Query NotebookLM to clarify specs when building components
- Cross-reference NotebookLM knowledge with Puter's local documents

## Security & Privacy

- All operations run in your browser with your credentials
- No data is transmitted outside your browser session
- The API is temporary and exists only while the page is loaded
- No persistent storage or logging

## Version History

- **v1.0** (2024-12-05) - Initial release
  - Core chat API implementation
  - User/AI message detection
  - Async response handling
  - Comprehensive documentation

## Related Documentation

- [Gobbler MCP Documentation](https://github.com/dylanisaac/gobbler-mcp)
- [Claude Code Skills Guide](https://docs.anthropic.com/claude-code/skills)
- [NotebookLM](https://notebooklm.google.com)

## Contributing

To extend this skill:

1. Modify `SKILL.md` for new instructions or capabilities
2. Update `technical-reference.md` with implementation details
3. Add examples to `usage-examples.md`
4. Test thoroughly with your NotebookLM setup
5. Restart Claude Code to reload changes

## License

Part of the Puter project. See project root for license information.
