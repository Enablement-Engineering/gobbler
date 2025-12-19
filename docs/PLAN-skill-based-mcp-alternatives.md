# Plan: Skill-Based Alternatives to MCP Architecture

## Executive Summary

This plan outlines how to expose Gobbler MCP functionality through Claude Code Skills for **progressive disclosure** and **context efficiency**. The goal is to reduce context window consumption by moving from "always-loaded" MCP tool definitions (~3,500 words/21 tools) to "on-demand" Skills that load only when relevant.

**Key Insight from Cloudflare Code Mode**: LLMs are better at writing code against TypeScript APIs than calling tools directly because they've seen millions of real-world code examples but only synthetic tool-calling training data. This validates our approach of wrapping MCP tools in Skills that provide structured, familiar interfaces.

---

## Research Synthesis

### Current State: Gobbler MCP Architecture

**21 MCP Tools** organized into 5 categories:
- **Content Conversion** (5 tools): transcribe_youtube, fetch_webpage, fetch_webpage_with_selector, convert_document, transcribe_audio
- **Batch Processing** (4 tools): batch_transcribe_youtube_playlist, batch_fetch_webpages, batch_transcribe_directory, batch_convert_documents
- **Browser Automation** (6 tools): browser_check_connection, browser_navigate_to_url, browser_execute_script, browser_extract_current_page, browser_list_tabs, browser_execute_script_in_tab
- **Job Management** (3 tools): get_job_status, list_jobs, get_batch_progress
- **Web Crawling** (3 tools): create_crawl_session, crawl_site

**Context Overhead**:
- ~3,500 words total documentation
- ~166 words average per tool
- All 21 tools load into context at session start regardless of usage

### Progressive Disclosure: The Core Pattern

From NotebookLM (Claude Code notebook):

> "Unlike systems that load all definitions (like traditional MCP servers), Skills only load information incrementally:
> 1. **Metadata First** (~100 tokens): Claude only reads the description field
> 2. **SKILL.md Body** (~500-1000 tokens): Loaded only when skill triggers
> 3. **Bundled Resources** (unlimited): Scripts execute without being read into context"

**Context Savings**: 40-70% reduction vs always-loaded MCP tools

### Architectural Patterns from Tactical AI Notebook

1. **Specialized Agents**: "One Agent One Prompt One Purpose" - avoid God Model Fallacy
2. **Conditional Documentation**: Map conditions to skill references; load only when relevant
3. **Meta-Prompts as Orchestrators**: Templates drive skill discovery and loading
4. **Composable Agentic Primitives**: Atomic units that combine to solve problems
5. **Fresh Agent Instances**: Each skill invocation gets isolated context

### Cloudflare Code Mode Insights

**Key Innovation**: Convert MCP tools to TypeScript APIs, ask LLM to write code calling that API

**Why it works**:
- LLMs have seen millions of real TypeScript examples
- Tool-calling training data is synthetic and limited
- Code can chain multiple calls without feeding each result through the LLM

**Applicable Pattern**: Skills can provide TypeScript-like interfaces (the NotebookLMAPI pattern) that wrap MCP tool sequences into familiar coding patterns.

---

## Proposed Skill Architecture

### Skill Category Structure

```
.claude/skills/
├── gobbler-content/           # Content conversion skill
│   ├── SKILL.md               # Core instructions + triggers
│   ├── references/
│   │   ├── youtube.md         # YouTube-specific options
│   │   ├── webpage.md         # Webpage extraction options
│   │   ├── document.md        # Document conversion options
│   │   └── audio.md           # Audio transcription options
│   └── examples/
│       └── common-workflows.md
│
├── gobbler-batch/             # Batch processing skill
│   ├── SKILL.md
│   ├── references/
│   │   ├── playlist.md
│   │   ├── webpages.md
│   │   ├── directory.md
│   │   └── documents.md
│   └── scripts/
│       └── estimate_batch.py  # Estimate batch duration
│
├── gobbler-browser/           # Browser automation skill
│   ├── SKILL.md
│   ├── references/
│   │   ├── tab-management.md
│   │   └── script-patterns.md
│   └── examples/
│       └── automation-workflows.md
│
├── gobbler-crawler/           # Web crawling skill
│   ├── SKILL.md
│   ├── references/
│   │   ├── session-auth.md
│   │   └── pattern-matching.md
│   └── examples/
│       └── crawl-strategies.md
│
└── gobbler-jobs/              # Job management skill
    ├── SKILL.md
    └── references/
        └── queue-types.md
```

### Skill Design: gobbler-content (Example)

**SKILL.md**:
```yaml
---
name: gobbler-content
description: Convert content to markdown from YouTube videos, web pages, documents (PDF/DOCX/PPTX/XLSX), and audio/video files. Use when the user wants to transcribe, extract, convert, or fetch content from any of these sources.
allowed-tools: mcp__gobbler-mcp__transcribe_youtube, mcp__gobbler-mcp__fetch_webpage, mcp__gobbler-mcp__fetch_webpage_with_selector, mcp__gobbler-mcp__convert_document, mcp__gobbler-mcp__transcribe_audio
---

# Gobbler Content Conversion

Convert any content source to clean markdown with YAML frontmatter.

## Quick Start

### YouTube Videos
```
mcp__gobbler-mcp__transcribe_youtube(video_url="...", include_timestamps=False)
```

### Web Pages
```
mcp__gobbler-mcp__fetch_webpage(url="...", include_images=True)
```

### Documents (PDF, DOCX, PPTX, XLSX)
```
mcp__gobbler-mcp__convert_document(file_path="...", enable_ocr=True)
```

### Audio/Video Files
```
mcp__gobbler-mcp__transcribe_audio(file_path="...", model="small")
```

## Detailed Options

- **YouTube options**: See [youtube.md](references/youtube.md)
- **Webpage extraction**: See [webpage.md](references/webpage.md)
- **Document conversion**: See [document.md](references/document.md)
- **Audio transcription**: See [audio.md](references/audio.md)

## Common Workflows

See [common-workflows.md](examples/common-workflows.md) for patterns like:
- Research pipeline (YouTube → transcript → summary)
- Documentation extraction (webpage → selector → specific content)
- Archive workflow (batch URLs → markdown files)
```

### Context Comparison

| Approach | Initial Load | When Used | Total Tokens |
|----------|-------------|-----------|--------------|
| **MCP (current)** | 3,500 words (~4,500 tokens) | 0 additional | 4,500 tokens |
| **Skills (proposed)** | 500 words metadata (~650 tokens) | 800 words per skill (~1,000 tokens) | 1,650 tokens |

**Savings**: ~63% reduction in context usage

---

## Implementation Plan

### Phase 1: Core Content Skill (Priority: High)

**Goal**: Create `gobbler-content` skill wrapping the 5 content conversion tools

**Tasks**:
1. Create skill directory structure at `.claude/skills/gobbler-content/`
2. Write SKILL.md with focused description and quick-start examples
3. Create reference files for each content type (youtube.md, webpage.md, etc.)
4. Add common workflow examples
5. Test skill discovery with various prompts

**Validation**:
- Ask "transcribe this YouTube video" → skill should activate
- Ask "convert this PDF" → skill should activate
- Ask "what's the weather" → skill should NOT activate

### Phase 2: Browser Automation Skill (Priority: High)

**Goal**: Create `gobbler-browser` skill leveraging the NotebookLM pattern

**Tasks**:
1. Create `.claude/skills/gobbler-browser/`
2. Include NotebookLMAPI-style JavaScript patterns
3. Document tab management and script execution patterns
4. Add multi-tab workflow examples

**Key Innovation**: This skill demonstrates the "Code Mode" pattern - providing a JavaScript API (like NotebookLMAPI) that the LLM can code against, rather than just exposing raw tools.

### Phase 3: Batch Processing Skill (Priority: Medium)

**Goal**: Create `gobbler-batch` skill for bulk operations

**Tasks**:
1. Create `.claude/skills/gobbler-batch/`
2. Document batch tool parameters and patterns
3. Add estimation script for predicting batch duration
4. Include rate limiting and queue management guidance

### Phase 4: Crawler and Jobs Skills (Priority: Low)

**Goal**: Complete the skill coverage

**Tasks**:
1. Create `gobbler-crawler` skill with session/auth patterns
2. Create `gobbler-jobs` skill for queue management
3. Cross-link skills where workflows span categories

---

## Advanced Patterns

### Pattern 1: Skill Chaining via Meta-Prompt

From Tactical AI notebook: Use templates that encode when skills are relevant.

**Example**: A `/research` command that:
1. Checks if source is YouTube → loads gobbler-content skill
2. Checks if batch operation → loads gobbler-batch skill
3. Checks if browser needed → loads gobbler-browser skill

### Pattern 2: Conditional Documentation

Create a skill navigation file that Claude consults first:

```markdown
# .claude/skills/gobbler-navigator/SKILL.md

## Skill Router

Given the user's request, determine which Gobbler skill is most appropriate:

| User Intent | Recommended Skill |
|-------------|-------------------|
| Single content conversion | gobbler-content |
| Multiple files/URLs | gobbler-batch |
| Browser interaction | gobbler-browser |
| Website crawling | gobbler-crawler |
| Long-running job status | gobbler-jobs |
```

### Pattern 3: Progressive API Disclosure (Code Mode Inspired)

Provide TypeScript-like interface definitions in skills:

```typescript
// In gobbler-content/references/api-types.md
interface ContentConversionResult {
  success: boolean;
  markdown: string;
  metadata: {
    source: string;
    word_count: number;
    conversion_time_ms: number;
  };
}

// Usage pattern Claude can follow:
const result = await transcribe_youtube({ video_url: "..." });
if (result.success) {
  // Use result.markdown
}
```

---

## Metrics and Success Criteria

### Context Efficiency
- **Target**: 60%+ reduction in baseline context usage
- **Measure**: Compare token counts between MCP-only and Skills approach

### Discovery Accuracy
- **Target**: 90%+ skill activation on relevant prompts
- **Measure**: Test with 20+ prompts per skill category

### User Experience
- **Target**: No degradation in task completion
- **Measure**: Compare task completion rates before/after

### Team Adoption
- **Target**: Skills committed to git and used by team
- **Measure**: Track skill invocations across sessions

---

## Migration Strategy

### Approach: Gradual Transition (Not Replacement)

MCP tools remain available for:
- Direct tool invocation when needed
- Integration with other MCP clients
- Programmatic access

Skills layer on top for:
- Context-efficient Claude Code sessions
- Team-shared workflows
- Progressive disclosure

### Rollout Order

1. **Week 1**: Deploy gobbler-content skill, gather feedback
2. **Week 2**: Deploy gobbler-browser skill (complex, high-value)
3. **Week 3**: Deploy gobbler-batch and remaining skills
4. **Week 4**: Create skill navigator and cross-linking

---

## Open Questions

1. **Skill Granularity**: Should browser tools be one skill or split (tab management vs. scripting)?
2. **Tool Restrictions**: Should skills restrict to only relevant MCP tools via `allowed-tools`?
3. **Versioning**: How to version skills as MCP tools evolve?
4. **Documentation Sync**: How to keep skill docs in sync with MCP tool changes?

---

## Appendix: Research Sources

### Primary Sources
1. **Gobbler MCP Server Analysis** (subagent): 21 tools, ~3,500 words overhead
2. **Claude Code Notebook (NotebookLM)**: Skills architecture, progressive disclosure, allowed-tools
3. **Tactical AI Notebook (NotebookLM)**: Specialized agents, conditional documentation, meta-prompts
4. **Claude Code Skills Guide (subagent)**: Official documentation on skill creation
5. **Cloudflare Code Mode Article**: TypeScript API pattern, isolate-based sandboxing

### Key Insights by Source

**From Claude Code Notebook**:
- "Skills only load information incrementally"
- "Metadata First: Claude only reads the description field"
- "Set Appropriate Degrees of Freedom"

**From Tactical AI Notebook**:
- "One Agent One Prompt One Purpose"
- "Conditional Documentation prevents context pollution"
- "Templates Encoding Knowledge of when a skill is relevant"

**From Cloudflare Code Mode**:
- "LLMs are better at writing code to call MCP, than at calling MCP directly"
- "Convert MCP tools into a TypeScript API"
- "The code can chain multiple calls without feeding each result through the LLM"
