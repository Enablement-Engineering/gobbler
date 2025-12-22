---
name: gobbler-document
description: Convert PDF, DOCX, PPTX, and XLSX documents to markdown with optional OCR. Use when user wants to extract text from documents, PDFs, Word files, PowerPoint presentations, or Excel spreadsheets.
version: 2.0.0
---

# Gobbler Document

Convert documents to markdown using the Docling service.

**Requires**: Docling Docker container running (`docker compose up -d docling`)

## Convert Document

```bash
# Basic conversion (digital PDFs - fast)
gobbler document /path/to/document.pdf -o output.md

# Disable OCR explicitly (recommended for digital PDFs)
gobbler document /path/to/document.pdf --no-ocr -o output.md

# Enable OCR for scanned documents (slower, needs more memory)
gobbler document /path/to/scanned.pdf --ocr -o output.md
```

## When to Use OCR

| Document Type | Use OCR? | Notes |
|--------------|----------|-------|
| Digital PDF | No | Text is already embedded, OCR wastes resources |
| Scanned PDF | Yes | Images of text need OCR |
| DOCX/PPTX/XLSX | No | Native text extraction |

## Supported Formats

- **PDF** - Portable Document Format (with optional OCR for scanned pages)
- **DOCX** - Microsoft Word documents
- **PPTX** - Microsoft PowerPoint presentations
- **XLSX** - Microsoft Excel spreadsheets

## Alternative: Using the Convert Subcommand

```bash
gobbler convert document /path/to/document.pdf --no-ocr -o output.md
```

## Python SDK

```python
from gobbler_sdk import GobblerClient

client = GobblerClient()

# Convert document
result = client.convert.document(
    "/path/to/document.pdf",
    enable_ocr=False  # Set True for scanned docs
)
print(result.markdown)
print(result.metadata)  # pages, word_count, format, etc.
```

## REST API

```bash
curl -X POST http://localhost:4600/convert/document \
  -H "Content-Type: application/json" \
  -d '{
    "file_path": "/path/to/document.pdf",
    "enable_ocr": false
  }'
```

## Prerequisites

Start services before using:

```bash
cd /path/to/gobbler
docker compose up -d docling

# Check health
curl http://localhost:5001/health
```
