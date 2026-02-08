# Gobbler Improvements — Clawd's Working List

*Last updated: 2026-02-07*

## 🔴 Critical Bugs

- [x] **YouTube `--format json` hangs** — ✅ Works fine on retest. May have been a timing/race condition in subagent test.
- [~] **Webpage `--selector` partially implemented** — CLI now routes to `convert_webpage_with_selector`, but Crawl4AI extraction strategy returns 500 errors. Needs investigation of Crawl4AI API.

## 🟠 High-Value Improvements

### Webpage (biggest pain point for AI consumption)
- [ ] **Auto-detect main content** — Use `<main>`, `<article>`, or `[role="main"]` as primary content source
- [ ] **Strip boilerplate** — Remove nav, footer, sidebar automatically (currently ~60% of output is cruft)
- [ ] **Implement `--selector`** — High-value for targeted extraction

### YouTube
- [ ] **Add `--clean` flag** — Merge choppy caption lines into flowing paragraphs
- [ ] **Quieter errors** — GitHub issue template dump is noisy; simplify for common cases

### Audio
- [ ] **Document `-l en` speedup** — 7x faster when language specified (14s → 2s). Make prominent in SKILL.md

### All Converters
- [x] **Add `duration_human`** — ✅ Human-readable duration ("13:54") now in YouTube and audio frontmatter
- [ ] **Better error messages** — Include file paths in "not found" errors

## 🟢 Polish Items

- [ ] Document `--skip-if-exists` as batch-friendly feature
- [ ] Checkbox rendering in documents (`[ ] /Off` → `☐`)
- [ ] Auto-detect OCR need for PDFs
- [ ] Add `--verbose` flag for debugging

## 📝 Session Notes

### 2026-02-07 — Initial Assessment
Spawned 4 subagents to test YouTube, webpage, document, and audio features.

**Key findings:**
- Foundation is solid: fast, consistent frontmatter, good format support
- Main gap: *cleaning output for AI consumption* — boilerplate stripping, paragraph merging
- YouTube JSON bug is blocking
- Webpage selector being advertised but broken is confusing

**Priority order:**
1. Fix YouTube JSON bug (critical, blocking)
2. Webpage content detection (high value, biggest pain point)
3. YouTube `--clean` flag (nice to have)
4. Documentation improvements

### 2026-02-07 (continued) — First Fixes
- ✅ Verified YouTube JSON format works (was timing issue in test)
- ✅ Added `duration_human` to YouTube and audio frontmatter
- 🔧 Connected `--selector` to selector converter (Crawl4AI extraction strategy needs debugging)
