# Test Fixtures

Test data for E2E testing of Gobbler's conversion tools.

## Directory Structure

```
fixtures/
├── audio/                    # Audio transcription tests (14 MB)
│   ├── test_short.wav       # 4 sec, synthetic test audio
│   ├── gettysburg_address.mp3  # 2 min, clear speech
│   ├── mlk_dream.mp3        # 3 min, famous speech
│   └── art_of_war.mp3       # 8 min, longer content
│
├── video/                    # Video transcription tests (13 MB)
│   └── ted_chatgpt_language.mp4  # TED talk, ~5 min
│
├── documents/                # Document conversion tests (6.7 MB)
│   ├── pdf/                 # PDF files
│   │   ├── irs_form_w4.pdf  # Fillable form
│   │   ├── irs_form_w9.pdf  # Fillable form
│   │   ├── irs_form_1040.pdf # Complex form
│   │   ├── irs_instructions_w4.pdf   # Flat text PDF
│   │   ├── irs_instructions_1040.pdf # Long text PDF
│   │   └── resume_sample.pdf # Simple PDF
│   ├── docx/                # Word documents
│   │   ├── kitchen_sink.docx # All DOCX features
│   │   └── kitchen_sink_original.docx
│   ├── xlsx/                # Spreadsheets
│   │   ├── sample_100kb.xlsx
│   │   ├── sample_500kb.xlsx
│   │   └── irs_statistics.xls  # Legacy XLS
│   └── pptx/                # Presentations
│       ├── sample_100kb.pptx
│       ├── sample_500kb.pptx
│       └── sample_1mb.pptx
│
├── urls/                     # URL lists for network tests
│   ├── youtube/             # YouTube video/playlist URLs
│   │   ├── ted_talks.txt    # 10 TED talks (varied accents)
│   │   ├── short_videos.txt # 10 videos < 5 min
│   │   ├── long_videos.txt  # 5 videos > 30 min
│   │   ├── playlists.txt    # 5 educational playlists
│   │   └── conference_talks.txt # 10 tech talks
│   └── webpages/            # Webpage URLs
│       ├── documentation.txt # Technical docs
│       ├── government.txt   # .gov (public domain)
│       ├── wikipedia.txt    # Wikipedia articles
│       └── blogs.txt        # CC-licensed blogs
│
└── expected_outputs/         # Golden output files
    └── youtube_transcript.md
```

## Source Attribution

### Audio Files

| File | Duration | Source | License |
|------|----------|--------|---------|
| `test_short.wav` | 4 sec | Project-created | MIT |
| `gettysburg_address.mp3` | ~2 min | LibriVox | Public Domain |
| `mlk_dream.mp3` | ~3 min | Archive.org | Public Domain |
| `art_of_war.mp3` | ~8 min | LibriVox | Public Domain |

### Video Files

| File | Size | Source | License |
|------|------|--------|---------|
| `ted_chatgpt_language.mp4` | 13 MB | [TED Talk](https://www.ted.com/talks/adam_aleksic_why_are_people_starting_to_sound_like_chatgpt) | TED Terms (educational) |

### Documents

| Category | Files | Source | License |
|----------|-------|--------|---------|
| IRS Forms (PDF) | 6 files | irs.gov | Public Domain |
| DOCX Kitchen Sink | 2 files | Project-created | MIT |
| Sample XLSX | 2 files | freetestdata.com | Free for testing |
| IRS Statistics (XLS) | 1 file | irs.gov | Public Domain |
| Sample PPTX | 3 files | freetestdata.com | Free for testing |

### URL Lists

| Category | URLs | Sources | License |
|----------|------|---------|---------|
| TED Talks | 10 | youtube.com | TED Terms (educational) |
| Short Videos | 10 | youtube.com | Various CC/educational |
| Long Videos | 5 | youtube.com | MIT OCW, Stanford |
| Playlists | 5 | youtube.com | CC/educational |
| Conference Talks | 10 | youtube.com | Usually CC |
| Documentation | 10 | Various | Open source |
| Government | 10 | .gov sites | Public Domain |
| Wikipedia | 10 | wikipedia.org | CC BY-SA |
| Blogs | 10 | Various | CC licenses |

## Usage in Tests

### Loading Fixtures

```python
from pathlib import Path

FIXTURES = Path(__file__).parent / "fixtures"

# Audio
audio_file = FIXTURES / "audio" / "test_short.wav"

# Documents
pdf_file = FIXTURES / "documents" / "pdf" / "irs_form_w4.pdf"
docx_file = FIXTURES / "documents" / "docx" / "kitchen_sink.docx"

# URLs
def load_urls(category: str, filename: str) -> list[str]:
    path = FIXTURES / "urls" / category / filename
    return [
        line.strip() 
        for line in path.read_text().splitlines()
        if line.strip() and not line.startswith("#")
    ]

youtube_urls = load_urls("youtube", "ted_talks.txt")
webpage_urls = load_urls("webpages", "documentation.txt")
```

### Test Markers

```python
import pytest

# Skip if service unavailable
@pytest.mark.requires_docling
def test_pdf_conversion():
    ...

@pytest.mark.requires_crawl4ai  
def test_webpage_fetch():
    ...

@pytest.mark.requires_network
def test_youtube_transcribe():
    ...
```

## Test Coverage Matrix

| Fixture Type | Tool/Command | Docker Required |
|--------------|--------------|-----------------|
| Audio (wav/mp3) | `gobbler audio` | No (Whisper local) |
| Video (mp4) | `gobbler audio` | No (Whisper local) |
| PDF | `gobbler document` | Yes (Docling) |
| DOCX | `gobbler document` | Yes (Docling) |
| XLSX/XLS | `gobbler document` | Yes (Docling) |
| PPTX | `gobbler document` | Yes (Docling) |
| YouTube URLs | `gobbler youtube` | No |
| Webpage URLs | `gobbler webpage` | Yes (Crawl4AI) |

## Adding New Fixtures

1. Place file in appropriate subdirectory
2. Update this README with source and license
3. Prefer public domain or CC-licensed content
4. Keep file sizes reasonable (avoid >100MB)

## Notes

- All audio files are public domain speeches
- IRS forms are public domain (US Government)
- Sample XLSX/PPTX from freetestdata.com (free for testing)
- YouTube URLs selected for educational/CC content
- Total fixture size: ~71 MB
