---
name: gobbler-document
description: Converts PDF, DOCX, PPTX, XLSX documents to markdown with OCR support. Triggers on .pdf, .docx, .pptx, .xlsx files, or requests to extract text from documents, Word files, PowerPoint, or Excel spreadsheets.
---

# Gobbler Document

Convert documents to markdown using the Docling service.

**Requires**: Docling Docker container running (`docker compose up -d docling`)

## CLI Reference

```
gobbler document [OPTIONS] FILE_PATH
```

### Arguments

| Argument | Required | Description |
|----------|----------|-------------|
| `FILE_PATH` | Yes | Path to the document file |

### Options

| Option | Short | Default | Description |
|--------|-------|---------|-------------|
| `--output` | `-o` | stdout | Output file path |
| `--ocr/--no-ocr` | | `--ocr` | Enable/disable OCR for scanned documents |
| `--format` | `-f` | `markdown` | Output format: `markdown`, `json`, or `table` |
| `--provider` | `-p` | `docling` | Document conversion provider |

## Examples

```bash
# Basic conversion (OCR enabled by default)
gobbler document /path/to/document.pdf -o output.md

# Disable OCR for faster processing on digital PDFs
gobbler document /path/to/document.pdf --no-ocr -o output.md

# Output as JSON with metadata
gobbler document report.pdf --format json -o result.json

# Output as table format
gobbler document spreadsheet.xlsx --format table
```

**Note**: OCR is **enabled by default** for maximum compatibility with scanned documents. Use `--no-ocr` for faster processing when you know the PDF has embedded text.

## When to Disable OCR

| Document Type | Recommendation | Notes |
|--------------|----------------|-------|
| Digital PDF | Use `--no-ocr` | Faster - text is already embedded |
| Scanned PDF | Default (OCR on) | Required - images need OCR |
| DOCX/PPTX/XLSX/XLS | Either works | Native text extraction regardless |

## Saving Output

When saving documents to a file, follow these steps:

### Step 1: Check for default output directory

```bash
gobbler config get output.default_directory
```

### Step 2: Save to the default directory

If a default directory is configured, use it with a descriptive filename:

```bash
gobbler document /path/to/report.pdf -o "<default_directory>/Report Summary.md"
```

### Step 3: If no default directory is configured

If the config returns empty/null, save to the current directory or ask the user where to save:

```bash
gobbler document /path/to/report.pdf -o "Report Summary.md"
```

## Supported Formats

- **PDF** - Portable Document Format (with optional OCR for scanned pages)
- **DOCX** - Microsoft Word documents
- **PPTX** - Microsoft PowerPoint presentations
- **XLSX** - Microsoft Excel spreadsheets
- **XLS** - Legacy Microsoft Excel spreadsheets (auto-converted to XLSX for processing)

## Prerequisites

Start services before using:

```bash
cd /path/to/gobbler
docker compose up -d docling

# Check health
curl http://localhost:5001/health
```
