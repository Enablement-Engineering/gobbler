# Document Conversion

Convert documents to markdown using the Docling service.

**Requires**: Docling Docker container running

## Quick Start

```bash
# Start the service
docker compose up -d docling

# Basic conversion (OCR enabled by default)
gobbler document /path/to/document.pdf -o output.md

# Disable OCR for faster processing on digital PDFs
gobbler document /path/to/document.pdf --no-ocr -o output.md
```

## Supported Formats

| Format | Extension | Notes |
|--------|-----------|-------|
| PDF | `.pdf` | With optional OCR for scanned pages |
| Word | `.docx` | Microsoft Word documents |
| PowerPoint | `.pptx` | Microsoft PowerPoint presentations |
| Excel | `.xlsx` | Microsoft Excel spreadsheets |

## OCR Guidance

OCR is **enabled by default** for maximum compatibility with scanned documents.

| Document Type | Recommendation | Notes |
|--------------|----------------|-------|
| Digital PDF | Use `--no-ocr` | Faster - text is already embedded |
| Scanned PDF | Default (OCR on) | Required - images need OCR |
| DOCX/PPTX/XLSX | Either works | Native text extraction regardless |

## Options

| Option | Description | Default |
|--------|-------------|---------|
| `--no-ocr` | Disable OCR processing | OCR enabled |
| `-o, --output` | Save to file | stdout |

## Alternative Command

```bash
gobbler convert document /path/to/document.pdf -o output.md
```

## Prerequisites

Start services before using:

```bash
cd /path/to/gobbler
docker compose up -d docling

# Check health
curl http://localhost:5001/health
```

## Output Format

```markdown
---
source: /path/to/document.pdf
type: document
format: pdf
pages: 42
word_count: 8234
converted_at: 2026-01-03T10:30:00Z
---

# Document Title

Document content with preserved structure...

## Tables

| Column 1 | Column 2 |
|----------|----------|
| Data     | Data     |
```

## Troubleshooting

### "Service unavailable"

```bash
# Start the Docling service
docker compose up -d docling

# Check it's running
docker ps | grep docling

# View logs
docker logs gobbler-docling --tail 50
```

### "Server disconnected" (Out of memory)

```bash
# Use --no-ocr for digital PDFs
gobbler document file.pdf --no-ocr -o output.md

# Or increase Docker memory in docker-compose.yml
# Change: memory: 4g → memory: 8g
docker compose up -d docling
```

### "OCR failed"

- Document may be corrupted
- Try `--no-ocr` if the PDF has embedded text
- Check Docker has sufficient memory
