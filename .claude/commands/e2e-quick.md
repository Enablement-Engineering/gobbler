# E2E Quick - Fast Smoke Tests

Run quick smoke tests for core Gobbler MCP endpoints without Docker dependencies.

**Time**: ~2-3 minutes
**Requirements**: None (no Docker needed)
**Coverage**: YouTube, audio, basic batch operations

---

## Phase 1: Pre-flight Checks

### Verify Test Infrastructure
1. Check fixtures directory exists: `tests/fixtures/`
2. Verify test data files:
   - `test_audio.wav` exists
   - `youtube_urls.txt` exists
   - `batch_audio/` directory has files
3. Check test config: `tests/fixtures/test_config.json` is valid JSON
4. Verify output directory writable: `/tmp/gobbler_e2e_tests/`

### Report Pre-flight Status
```
# E2E Quick Test - Pre-flight

✅ Test fixtures: [present/missing]
✅ Test data files: [X/Y found]
✅ Test config valid: [yes/no]
✅ Output directory: [writable/not writable]

Ready to proceed: [YES/NO]
```

**If any checks fail**: STOP and report missing items

---

## Phase 2: Test Execution

### Test Suite: Core Endpoints (No Docker)

Run these tests in order, tracking progress:

#### 1. YouTube Transcription
```python
transcribe_youtube(
    video_url="https://www.youtube.com/watch?v=GvYYFloV0aA",
    include_timestamps=False,
    output_file="/tmp/gobbler_e2e_tests/youtube/quick_test.md"
)
```

**Validate**:
- File created with YAML frontmatter
- Contains transcript text
- Video metadata present (title, channel, etc.)

#### 2. YouTube with Timestamps
```python
transcribe_youtube(
    video_url="https://www.youtube.com/watch?v=dQw4w9WgXcQ",
    include_timestamps=True,
    output_file="/tmp/gobbler_e2e_tests/youtube/quick_timestamps.md"
)
```

**Validate**:
- Timestamps included in output
- Format: `[HH:MM:SS]` or similar

#### 3. Audio Transcription
```python
transcribe_audio(
    file_path="/Users/dylanisaac/Projects/gobbler/tests/fixtures/test_audio.wav",
    model="tiny",
    output_file="/tmp/gobbler_e2e_tests/audio/quick_test.md"
)
```

**Validate**:
- Transcription completed
- Audio metadata present
- Model info in frontmatter

#### 4. Batch Audio Directory
```python
batch_transcribe_directory(
    input_dir="/Users/dylanisaac/Projects/gobbler/tests/fixtures/batch_audio",
    output_dir="/tmp/gobbler_e2e_tests/batch/audio_quick",
    model="tiny",
    concurrency=2,
    skip_existing=True
)
```

**Validate**:
- Batch summary returned
- 3/3 files processed
- All output files created

---

## Phase 3: Validation

### Output Quality Checks

For each generated file:

**1. YAML Frontmatter Structure**
- [ ] Frontmatter block present (`---` delimiters)
- [ ] Required fields present (title, source, timestamp)
- [ ] Valid YAML syntax

**2. Content Quality**
- [ ] Non-empty content after frontmatter
- [ ] Reasonable content length (not truncated)
- [ ] No error messages in output

**3. File System**
- [ ] All expected files created
- [ ] File sizes reasonable (not 0 bytes)
- [ ] Proper directory structure

### Test Results Matrix

```
Endpoint                    Status    Time     Output
-------------------------   -------   ------   ------
transcribe_youtube          [✅/❌]   [Xs]     [path]
transcribe_youtube (ts)     [✅/❌]   [Xs]     [path]
transcribe_audio            [✅/❌]   [Xs]     [path]
batch_transcribe_directory  [✅/❌]   [Xs]     [path]
```

---

## Phase 4: Report

### Summary Report

```
# E2E Quick Test Results

## Execution Summary
- **Total Tests**: 4
- **Passed**: X/4
- **Failed**: Y/4
- **Duration**: XX seconds

## Test Details

### ✅ Passed Tests
1. [Test name] - [duration]
2. ...

### ❌ Failed Tests
1. [Test name] - [error message]
2. ...

## Output Location
All test outputs: `/tmp/gobbler_e2e_tests/`

## Validation Results
- Frontmatter structure: [X/Y valid]
- Content quality: [X/Y good]
- File integrity: [X/Y complete]

## Next Steps
[If all passed]: ✅ Core endpoints working correctly
[If failures]: ⚠️ Review failed tests above
```

---

## Important Rules

### ⚠️ Blocking Conditions
**STOP and report if**:
- Test fixtures directory missing
- Required test files not found
- Output directory not writable
- Test config JSON invalid

### ✅ Execution Rules
- Run tests sequentially (don't parallelize)
- Track timing for each test
- Save all outputs to `/tmp/gobbler_e2e_tests/`
- Don't delete previous test outputs
- Use "tiny" model for speed

### 📝 Validation Rules
- Check every output file created
- Validate YAML frontmatter syntax
- Verify content is not empty
- Compare file count vs expected

---

## Test Data Sources

From `tests/fixtures/test_config.json`:
- YouTube URLs: First 2 videos from youtube_urls.txt
- Audio file: test_audio.wav (4 second sample)
- Batch directory: batch_audio/ (3 files)

---

## Success Criteria

**Quick test passes if**:
1. All 4 tests execute without exceptions
2. All output files created with valid frontmatter
3. Content quality checks pass
4. Total duration < 5 minutes

**Quick test fails if**:
- Any test raises exception
- Output files missing or empty
- Invalid YAML frontmatter
- Content appears truncated or corrupted
