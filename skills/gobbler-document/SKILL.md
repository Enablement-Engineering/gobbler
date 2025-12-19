---
name: gobbler-document
description: Convert PDF, DOCX, PPTX, and XLSX documents to markdown with optional OCR. Use when user wants to extract text from documents, PDFs, Word files, PowerPoint presentations, or Excel spreadsheets.
---

# Gobbler Document

Convert documents to markdown using the Docling service.

**Requires**: Docling Docker container running on port 5001

## Convert Document

```bash
uv run scripts/convert.py /path/to/document.pdf

# Enable OCR for scanned documents
uv run scripts/convert.py /path/to/scanned.pdf --ocr

# Save to file
uv run scripts/convert.py /path/to/document.docx --output output.md
```

## Supported Formats

- **PDF** - Portable Document Format (with OCR support for scanned pages)
- **DOCX** - Microsoft Word documents
- **PPTX** - Microsoft PowerPoint presentations
- **XLSX** - Microsoft Excel spreadsheets

## Prerequisites

Start Docling container before using:

```bash
docker run -d -p 5001:5001 --name docling quay.io/docling/docling-serve
```

Check health:

```bash
uv run ../gobbler-utils/scripts/docker_health.py docling
```
