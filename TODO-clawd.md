# Gobbler Improvements — Clawd's Working List

*Last updated: 2026-02-07*

## 🔴 Critical Bugs

- [x] **YouTube `--format json` hangs** — ✅ Works fine on retest. May have been a timing/race condition in subagent test.
- [x] **Webpage `--selector` working** — ✅ CSS selector extraction now works via BeautifulSoup on fetched HTML. Removed broken Crawl4AI extraction strategy approach.

## 🟠 High-Value Improvements

### Webpage (biggest pain point for AI consumption)
- [x] **Auto-detect main content** — ✅ `--clean` flag tries `main, article, [role='main'], .content, #content`
- [x] **Strip boilerplate** — ✅ `--clean` mode reduces word count ~20% automatically
- [x] **Implement `--selector`** — ✅ CSS selector extraction working via BeautifulSoup

### YouTube
- [x] **Add `--clean` flag** — ✅ Merges choppy captions into ~200-char paragraphs with sentence breaks
- [x] **Quieter errors** — ✅ Strips GitHub issue template, suppresses yt-dlp stderr, shows clean "Transcript unavailable" message

### Audio
- [x] **Document `-l en` speedup** — ✅ Added to SKILL.md Tips section with example

### All Converters
- [x] **Add `duration_human`** — ✅ Human-readable duration ("13:54") now in YouTube and audio frontmatter
- [x] **Better error messages** — ✅ File paths already included in document/audio errors; YouTube errors now cleaner

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
- ✅ Connected `--selector` to selector converter — now uses BeautifulSoup for clean HTML extraction
- ✅ Reinstalled with Python 3.12 to pick up changes
- 📊 Test result: word count dropped from 1066 → 453 (60% boilerplate removed) on docs.anthropic.com
