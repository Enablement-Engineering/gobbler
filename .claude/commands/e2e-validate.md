# E2E Validate - Test Output Validation

Validate existing e2e test outputs without re-running tests.

**Time**: ~1 minute
**Requirements**: None
**Purpose**: Quick validation of test outputs from previous e2e runs

---

## Phase 1: Locate Test Outputs

### Find Test Output Directory

Check for existing test outputs:
```bash
ls -lR /tmp/gobbler_e2e_tests/
```

### Expected Directory Structure

```
/tmp/gobbler_e2e_tests/
├── youtube/           # YouTube transcripts
├── audio/             # Audio transcriptions
├── webpages/          # Web scraping outputs
├── documents/         # Document conversions
├── downloads/         # Downloaded videos
├── crawled/           # Crawled sites
└── batch/
    ├── audio/         # Batch audio results
    ├── documents/     # Batch document results
    ├── webpages/      # Batch webpage results
    └── playlist/      # Playlist batch results
```

### Report Output Inventory

```
# E2E Validate - Output Inventory

## Output Directory: /tmp/gobbler_e2e_tests/

Found directories:
- youtube/: [X files]
- audio/: [X files]
- webpages/: [X files]
- documents/: [X files]
- downloads/: [X files]
- crawled/: [X files/dirs]
- batch/audio/: [X files]
- batch/documents/: [X files]
- batch/webpages/: [X files]
- batch/playlist/: [X files]

Total files found: [X]
```

**If no outputs found**: Report no test outputs to validate

---

## Phase 2: Validation Checks

### For Each Markdown File (.md)

Run comprehensive validation:

#### 1. YAML Frontmatter Validation

**Check structure**:
- [ ] File starts with `---`
- [ ] Contains closing `---`
- [ ] Valid YAML syntax (parse without errors)

**Check required fields**:
- [ ] `title` field present
- [ ] `source` field present
- [ ] `timestamp` or `created_at` field present
- [ ] `tool_used` or similar metadata present

**Parse and validate**:
```python
import yaml

with open(file_path) as f:
    content = f.read()

# Extract frontmatter
if content.startswith('---'):
    parts = content.split('---', 2)
    if len(parts) >= 3:
        frontmatter_text = parts[1]
        try:
            metadata = yaml.safe_load(frontmatter_text)
            # Validate required fields
            assert 'title' in metadata
            assert 'source' in metadata
            # etc.
        except Exception as e:
            # Report parsing error
```

#### 2. Content Quality Validation

**Check content exists**:
- [ ] Content after frontmatter is not empty
- [ ] Content length > 50 characters (not just whitespace)
- [ ] Content contains expected markdown elements

**Check for error indicators**:
- [ ] No "Error:" strings in content
- [ ] No "Exception:" strings in content
- [ ] No "Failed:" strings in content
- [ ] No stack traces

**Content type validation**:
- YouTube/Audio: Should contain transcript text
- Webpages: Should contain markdown from HTML
- Documents: Should contain extracted document content

#### 3. File Integrity Validation

**Check file properties**:
- [ ] File size > 0 bytes
- [ ] File size reasonable (< 50MB for markdown)
- [ ] File readable with UTF-8 encoding
- [ ] File has .md extension (for markdown outputs)

**Check naming conventions**:
- Files named descriptively
- No duplicate filenames
- Batch outputs properly organized

### For Downloaded Videos

**Validate video files**:
- [ ] File size > 0 bytes
- [ ] File extension valid (.mp4, .webm, .mkv)
- [ ] File readable (not corrupted)

### For Crawled Sites

**Validate crawl outputs**:
- [ ] Multiple files created (if max_pages > 1)
- [ ] Files organized in directories
- [ ] Each page has valid markdown

---

## Phase 3: Generate Validation Report

### Validation Results Matrix

For each file, track:

```
File                                    Frontmatter  Content  Integrity  Status
--------------------------------------  -----------  -------  ---------  ------
youtube/test_01_basic.md               [✅/❌]      [✅/❌]  [✅/❌]    [✅/❌]
youtube/test_02_timestamps.md          [✅/❌]      [✅/❌]  [✅/❌]    [✅/❌]
audio/test_01_tiny.md                  [✅/❌]      [✅/❌]  [✅/❌]    [✅/❌]
...
```

### Summary Statistics

```
# E2E Validation Report

## Overall Results
- **Total Files Validated**: X
- **Valid Files**: X (Y%)
- **Invalid Files**: X (Y%)
- **Warnings**: X

## Validation Categories

### YAML Frontmatter
- Valid frontmatter: X/Y (Z%)
- Missing frontmatter: X
- Invalid YAML syntax: X
- Missing required fields: X

### Content Quality
- Non-empty content: X/Y (Z%)
- Sufficient length: X/Y (Z%)
- No error indicators: X/Y (Z%)

### File Integrity
- Valid file sizes: X/Y (Z%)
- Readable files: X/Y (Z%)
- Proper encoding: X/Y (Z%)

## Issues Found

### Critical Issues (❌)
[For each critical issue]:
- **File**: [path]
- **Issue**: [description]
- **Recommendation**: [how to fix]

### Warnings (⚠️)
[For each warning]:
- **File**: [path]
- **Warning**: [description]
- **Recommendation**: [optional improvement]

## Valid Files by Category

### YouTube Transcripts (X files)
✅ [file1] - [size]
✅ [file2] - [size]

### Audio Transcriptions (X files)
✅ [file1] - [size]
✅ [file2] - [size]

### Web Pages (X files)
✅ [file1] - [size]
✅ [file2] - [size]

### Documents (X files)
✅ [file1] - [size]
✅ [file2] - [size]

### Batch Operations (X files)
✅ batch/audio/ - [X files]
✅ batch/documents/ - [X files]
✅ batch/webpages/ - [X files]
✅ batch/playlist/ - [X files]

## Sample Content Validation

[Show first 500 chars of 2-3 sample files to demonstrate quality]

### Sample: youtube/test_01_basic.md
```
---
title: [...]
source: [...]
---

[First 500 chars of content...]
```

## Recommendations

[If all valid]:
✅ **All test outputs are valid!** Quality checks passed.

[If minor issues]:
⚠️ **Minor issues detected**:
- [List specific issues]
- Consider re-running affected tests

[If major issues]:
❌ **Significant issues found**:
- [List critical problems]
- Re-run e2e tests: `/e2e-quick` or `/e2e-full`

## Next Steps
1. Review any invalid files
2. Re-run specific tests if needed
3. Check for service issues if many failures
```

---

## Phase 4: Sample Content Review

### Manual Spot Checks

For 2-3 sample files, perform detailed review:

**1. Read full file**
```bash
cat /tmp/gobbler_e2e_tests/youtube/test_01_basic.md
```

**2. Check metadata quality**
- Is video title correct?
- Is source URL present?
- Is timestamp formatted properly?
- Are additional metadata fields useful?

**3. Check content quality**
- Does transcript look accurate?
- Are timestamps formatted correctly (if applicable)?
- Is markdown formatting clean?
- Are there any formatting artifacts?

### Report Sample Reviews

```
## Sample Content Reviews

### Sample 1: youtube/test_01_basic.md
- **Frontmatter**: ✅ All fields present, well-formatted
- **Content**: ✅ Transcript looks accurate, ~5000 words
- **Formatting**: ✅ Clean markdown, no artifacts
- **Quality Score**: 10/10

### Sample 2: audio/test_01_tiny.md
- **Frontmatter**: ✅ Metadata complete
- **Content**: ✅ Audio transcribed correctly
- **Formatting**: ✅ Clean output
- **Quality Score**: 10/10

### Sample 3: webpages/test_01_basic.md
- **Frontmatter**: ✅ Page metadata extracted
- **Content**: ✅ HTML converted to markdown properly
- **Formatting**: ⚠️ Some extra line breaks
- **Quality Score**: 8/10
```

---

## Important Rules

### ⚠️ Validation Rules
- Check every .md file in output directory
- Validate YAML syntax strictly
- Check for common error patterns
- Verify file integrity (size, encoding)

### ✅ Reporting Rules
- Clear distinction: Critical (❌) vs Warning (⚠️)
- Provide specific file paths for issues
- Give actionable recommendations
- Show percentage-based statistics

### 📝 Quality Standards

**Frontmatter must have**:
- Valid YAML syntax
- Required fields (title, source, timestamp)
- Proper formatting

**Content must be**:
- Non-empty (> 50 chars)
- No error messages
- Properly encoded UTF-8
- Reasonable length

**Files must be**:
- Readable
- Non-zero size
- Correct extensions
- Properly organized

---

## Success Criteria

**Validation passes if**:
1. 95%+ files have valid frontmatter
2. 95%+ files have quality content
3. 100% files have proper integrity
4. No critical errors found

**Validation acceptable if**:
- Some warnings (formatting issues)
- Missing optional metadata fields
- Minor content formatting quirks

**Validation fails if**:
- Invalid YAML in multiple files
- Empty or error content
- Corrupted files
- Missing required metadata
