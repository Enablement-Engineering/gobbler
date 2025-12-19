# NotebookLM Skill - Usage Examples

## Example 1: First-Time Setup and Query

**User Request:** "Can you ask my NotebookLM what the Puter project is about?"

**Claude's Actions:**

1. **Check connection:**
```
Tool: mcp__gobbler-mcp__browser_check_connection
Result: "Browser extension is connected and ready."
```

2. **Initialize API:**
```javascript
Tool: mcp__gobbler-mcp__browser_execute_script
Script: [Full initialization script from SKILL.md]
Result: { success: true, message: "NotebookLM API initialized" }
```

3. **Send query:**
```javascript
Tool: mcp__gobbler-mcp__browser_execute_script
Script:
(async () => {
  const result = await window.NotebookLMAPI.chat(
    "What is the Puter project? Provide a high-level overview of its purpose and architecture.",
    60000
  );
  return {
    success: true,
    response: result.aiResponse.text
  };
})()
Result: { success: true, response: "Puter is a personal computing automation system..." }
```

4. **Claude's response to user:**
"According to NotebookLM, Puter is a personal computing automation system..."

---

## Example 2: Follow-up Questions (API Already Initialized)

**User Request:** "Ask it about the component manifest schema"

**Claude's Actions:**

1. **Check if API exists (optional check):**
```javascript
Tool: mcp__gobbler-mcp__browser_execute_script
Script:
(() => {
  return {
    apiExists: typeof window.NotebookLMAPI !== 'undefined',
    methods: window.NotebookLMAPI ? Object.keys(window.NotebookLMAPI) : []
  };
})()
Result: { apiExists: true, methods: [...] }
```

2. **Send follow-up query:**
```javascript
Tool: mcp__gobbler-mcp__browser_execute_script
Script:
(async () => {
  const result = await window.NotebookLMAPI.chat(
    "Explain the component manifest schema. What are the required fields and what do they define?",
    60000
  );
  return { response: result.aiResponse.text };
})()
```

---

## Example 3: Retrieving Conversation History

**User Request:** "What have I already asked NotebookLM about?"

**Claude's Actions:**

1. **Get all messages:**
```javascript
Tool: mcp__gobbler-mcp__browser_execute_script
Script:
(() => {
  if (typeof window.NotebookLMAPI === 'undefined') {
    return { error: "API not initialized" };
  }

  const messages = window.NotebookLMAPI.getChatMessages();

  return {
    totalMessages: messages.length,
    conversation: messages.map(m => ({
      role: m.isUser ? 'User' : 'NotebookLM',
      text: m.text
    }))
  };
})()
Result: {
  totalMessages: 10,
  conversation: [
    { role: "User", text: "What is the Puter project?" },
    { role: "NotebookLM", text: "Puter is a personal computing..." },
    ...
  ]
}
```

2. **Claude's response:**
"Here's your conversation history with NotebookLM:
1. You asked: 'What is the Puter project?'
   NotebookLM responded: 'Puter is a personal computing...'
2. You asked: 'Explain the component manifest schema'
   ..."

---

## Example 4: Complex Multi-Part Query

**User Request:** "Ask NotebookLM to explain the difference between the digester and router components, and how they communicate via the event system"

**Claude's Actions:**

1. **Send detailed query:**
```javascript
Tool: mcp__gobbler-mcp__browser_execute_script
Script:
(async () => {
  const question = `Based on the Puter planning documents:

1. What is the difference between the digester component and the router component?
2. What are their specific responsibilities in the GTD pipeline?
3. How do they communicate with each other via the event system?
4. What event types do they emit and consume?

Please provide specific examples from the architecture docs.`;

  const result = await window.NotebookLMAPI.chat(question, 90000); // 90s timeout

  return {
    success: true,
    question: question,
    response: result.aiResponse.text,
    responseLength: result.aiResponse.text.length
  };
})()
```

---

## Example 5: Handling Long Responses with Progress Check

**User Request:** "Ask NotebookLM for a comprehensive guide on implementing the component registry"

**Claude's Actions:**

1. **Send query:**
```javascript
Tool: mcp__gobbler-mcp__browser_execute_script
Script:
(async () => {
  const sendResult = await window.NotebookLMAPI.sendMessage(
    "Provide a comprehensive, step-by-step guide for implementing the Puter component registry. Include code examples, architecture decisions, and integration points."
  );
  return {
    sent: true,
    initialMessageCount: sendResult.initialMessageCount
  };
})()
Result: { sent: true, initialMessageCount: 10 }
```

2. **Wait and check progress:**
```javascript
Tool: mcp__gobbler-mcp__browser_execute_script
Script:
(async () => {
  // Wait 5 seconds
  await new Promise(resolve => setTimeout(resolve, 5000));

  const latest = window.NotebookLMAPI.getLatestAIResponse();
  const isStillProcessing = latest?.text?.includes("Gathering") ||
                           latest?.text?.includes("Scanning");

  return {
    currentText: latest?.text?.substring(0, 200) + "...",
    isStillProcessing: isStillProcessing,
    textLength: latest?.text?.length || 0
  };
})()
Result: { currentText: "Scanning your sources...", isStillProcessing: true }
```

3. **Wait longer and retrieve full response:**
```javascript
Tool: mcp__gobbler-mcp__browser_execute_script
Script:
(async () => {
  // Wait another 10 seconds
  await new Promise(resolve => setTimeout(resolve, 10000));

  const latest = window.NotebookLMAPI.getLatestAIResponse();

  return {
    fullResponse: latest?.text,
    responseLength: latest?.text?.length || 0
  };
})()
```

---

## Example 6: Error Recovery

**User Request:** "Query my notebook about event sourcing"

**Claude's Actions:**

1. **Attempt query (but API not initialized):**
```javascript
Tool: mcp__gobbler-mcp__browser_execute_script
Script:
(async () => {
  try {
    const result = await window.NotebookLMAPI.chat(
      "Explain event sourcing in Puter",
      60000
    );
    return { success: true, response: result.aiResponse.text };
  } catch (error) {
    return { success: false, error: error.message };
  }
})()
Result: { success: false, error: "Cannot read property 'chat' of undefined" }
```

2. **Detect error and reinitialize:**
```javascript
Tool: mcp__gobbler-mcp__browser_execute_script
Script: [Full initialization script]
Result: { success: true, message: "NotebookLM API initialized" }
```

3. **Retry query:**
```javascript
Tool: mcp__gobbler-mcp__browser_execute_script
Script: [Same chat query as step 1]
Result: { success: true, response: "Event sourcing in Puter..." }
```

---

## Example 7: Extracting Specific Information

**User Request:** "What does NotebookLM say about the Redux-style state management pattern in Puter?"

**Claude's Actions:**

1. **Targeted query:**
```javascript
Tool: mcp__gobbler-mcp__browser_execute_script
Script:
(async () => {
  const result = await window.NotebookLMAPI.chat(
    "Focus specifically on the Redux-style state management pattern in Puter. How does it work? What are the key components (store, reducers, actions)? Provide code examples if available in the docs.",
    60000
  );
  return { response: result.aiResponse.text };
})()
```

2. **Parse and present focused answer to user**

---

## Example 8: Comparing Information Sources

**User Request:** "Ask NotebookLM how the planning docs describe component interfaces, and compare that to what we learned from the earlier Claude SDK query"

**Claude's Actions:**

1. **Query NotebookLM:**
```javascript
Tool: mcp__gobbler-mcp__browser_execute_script
Script:
(async () => {
  const result = await window.NotebookLMAPI.chat(
    "According to the planning documents, how are component interfaces defined? What interface types are supported (REST, CLI, MCP, etc.) and how do they work?",
    60000
  );
  return { notebookLMView: result.aiResponse.text };
})()
```

2. **Claude synthesizes comparison:**
"Based on NotebookLM's analysis of the planning docs and the earlier Claude SDK documentation:

**From Planning Docs (via NotebookLM):**
- Components declare multiple interfaces: REST, CLI, MCP, message bus, Python SDK, TypeScript SDK
- Interfaces are defined in component.yaml manifest
- Each component can expose all interfaces simultaneously

**From Claude SDK Documentation:**
- Use @tool decorator and createSdkMcpServer to expose MCP tools
- Subagents via Task tool for complex operations
- Skills provide orchestration layer

**Synthesis:**
The planning docs envision a more comprehensive multi-interface system than what's built into the base Claude SDK..."

---

## Example 9: Iterative Refinement

**User Request:** "Ask NotebookLM about hot folders, then based on its answer, ask a follow-up about RAG integration"

**Claude's Actions:**

1. **Initial query:**
```javascript
Tool: mcp__gobbler-mcp__browser_execute_script
Script:
(async () => {
  const result = await window.NotebookLMAPI.chat(
    "What are hot folders in the Puter architecture? How do they work?",
    60000
  );
  return { response: result.aiResponse.text };
})()
```

2. **Present to user and formulate follow-up based on response:**

3. **Follow-up query:**
```javascript
Tool: mcp__gobbler-mcp__browser_execute_script
Script:
(async () => {
  const result = await window.NotebookLMAPI.chat(
    "Based on the hot folder concept you just explained, how specifically is RAG (Retrieval-Augmented Generation) integrated as a hot folder service? What happens when files are added to a RAG-indexed folder?",
    60000
  );
  return { response: result.aiResponse.text };
})()
```

---

## Example 10: Validation and Cross-Reference

**User Request:** "I think the planning docs mention using LanceDB for vectors. Can you verify this with NotebookLM?"

**Claude's Actions:**

1. **Verification query:**
```javascript
Tool: mcp__gobbler-mcp__browser_execute_script
Script:
(async () => {
  const result = await window.NotebookLMAPI.chat(
    "What vector database options are mentioned in the planning documents? Specifically, is LanceDB mentioned as an option? What are the other alternatives discussed?",
    60000
  );
  return { response: result.aiResponse.text };
})()
```

2. **Claude's response:**
"According to NotebookLM, the planning docs mention several vector database options:
- SQLite + sqlite-vss
- ChromaDB
- LanceDB

Yes, LanceDB is indeed mentioned as one of the options! The docs specifically list it alongside SQLite and ChromaDB as embeddable, file-based vector database choices for the RAG service."

---

## Tips for Effective Usage

### Best Practices

1. **Initialize once per session:** The API persists, no need to reinitialize unless page reloads
2. **Use appropriate timeouts:** 30s for simple queries, 60-90s for complex analysis
3. **Check for loading states:** "Gathering the facts..." means response not ready yet
4. **Retrieve conversation context first:** Before sending queries, check what's already been discussed
5. **Handle errors gracefully:** Wrap async operations in try-catch

### Common Patterns

- **Quick fact lookup:** Single `chat()` call with 30s timeout
- **Deep analysis:** Use longer timeout (60-90s) and check progress
- **Context building:** Retrieve messages first, then ask targeted follow-ups
- **Iterative exploration:** Chain queries based on previous responses

### Anti-Patterns to Avoid

- ❌ Reinitializing API on every query (wasteful)
- ❌ Using timeout < 30s (NotebookLM needs processing time)
- ❌ Not checking connection before operations
- ❌ Ignoring error responses
- ❌ Sending queries when no notebook is open

---

## Multi-Notebook Examples

### Example 11: Query Multiple Notebooks

**User Request:** "I have two notebooks open - Research and Meetings. What does each say about the component architecture?"

**Claude's Actions:**

1. **List available NotebookLM tabs:**
```
Tool: mcp__gobbler-mcp__browser_list_tabs
Parameters: filter="notebooklm"
Result:
Found 2 tab(s) in Gobbler group:
  [123] Research Notes (active)
       https://notebooklm.google.com/notebook/ABC123
  [456] Meeting Minutes
       https://notebooklm.google.com/notebook/XYZ789
```

2. **Initialize API in Research notebook (tab 123):**
```javascript
Tool: mcp__gobbler-mcp__browser_execute_script_in_tab
Parameters:
  tab_id: 123
  script: [Full initialization script]
Result: { success: true, message: "NotebookLM API initialized" }
```

3. **Query Research notebook:**
```javascript
Tool: mcp__gobbler-mcp__browser_execute_script_in_tab
Parameters:
  tab_id: 123
  script:
(async () => {
  const result = await window.NotebookLMAPI.chat(
    "What does the documentation say about the component architecture?",
    60000
  );
  return { response: result.aiResponse.text };
})()
Result: { response: "The component architecture uses a manifest-based system..." }
```

4. **Initialize API in Meetings notebook (tab 456):**
```javascript
Tool: mcp__gobbler-mcp__browser_execute_script_in_tab
Parameters:
  tab_id: 456
  script: [Full initialization script]
Result: { success: true, message: "NotebookLM API initialized" }
```

5. **Query Meetings notebook:**
```javascript
Tool: mcp__gobbler-mcp__browser_execute_script_in_tab
Parameters:
  tab_id: 456
  script:
(async () => {
  const result = await window.NotebookLMAPI.chat(
    "What was discussed about the component architecture in meetings?",
    60000
  );
  return { response: result.aiResponse.text };
})()
Result: { response: "In the planning meeting, the team discussed..." }
```

6. **Claude's response:**
"Based on both notebooks:

**From Research Notes:**
The component architecture uses a manifest-based system...

**From Meeting Minutes:**
In the planning meeting, the team discussed..."

---

### Example 12: Target Notebook by Title

**User Request:** "Ask the 'Project Planning' notebook about deadlines"

**Claude's Actions:**

1. **List tabs to find the one with matching title:**
```
Tool: mcp__gobbler-mcp__browser_list_tabs
Parameters: filter="notebooklm"
Result:
Found 3 tab(s) in Gobbler group:
  [111] Research Notes
       https://notebooklm.google.com/notebook/...
  [222] Project Planning
       https://notebooklm.google.com/notebook/...
  [333] Team Resources
       https://notebooklm.google.com/notebook/...
```

2. **Identify tab 222 as "Project Planning", then query it:**
```javascript
Tool: mcp__gobbler-mcp__browser_execute_script_in_tab
Parameters:
  tab_id: 222
  script: [Initialize + query script]
```

---

### Example 13: Cross-Reference Between Notebooks

**User Request:** "Compare what the research docs say about authentication vs what was decided in meetings"

**Claude's Actions:**

1. **List tabs and identify both notebooks**
2. **Query Research notebook about authentication**
3. **Query Meetings notebook about authentication decisions**
4. **Synthesize comparison:**

"**Research Documentation (from 'Research Notes'):**
- OAuth 2.0 recommended
- JWT tokens for session management
- Refresh token rotation every 24h

**Meeting Decisions (from 'Meeting Minutes'):**
- Team chose OAuth 2.0 (aligns with docs)
- Added requirement: Support SSO for enterprise
- Decided against refresh rotation due to UX concerns

**Analysis:**
The team largely followed the documented recommendations but diverged on refresh token handling..."

---

### Example 14: Handling Tab Not Found

**User Request:** "Query my finance notebook"

**Claude's Actions:**

1. **List tabs:**
```
Tool: mcp__gobbler-mcp__browser_list_tabs
Parameters: filter="notebooklm"
Result:
Found 1 tab(s) in Gobbler group:
  [123] Research Notes (active)
       https://notebooklm.google.com/notebook/...
```

2. **Claude's response:**
"I can see one NotebookLM tab open: 'Research Notes'. I don't see a finance notebook. Could you:
1. Open the finance notebook in a new tab
2. Add it to the Gobbler tab group (right-click → 'Add tab to Gobbler group')
3. Let me know when it's ready"

---

### Multi-Notebook Best Practices

1. **Always list tabs first** - Tab IDs change between sessions
2. **Match by title** - Use notebook titles to identify the right tab
3. **Initialize per-tab** - Each tab needs its own API initialization
4. **Report source** - Always tell the user which notebook a response came from
5. **Handle missing tabs gracefully** - Guide user to add tabs to Gobbler group
