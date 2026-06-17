# Document Conversion

Use for PDFs, DOCX, PPTX, XLSX, XLS, document text extraction, OCR, reports, papers, spreadsheets, or presentations.

## Commands

```bash
# Check service readiness first
gobbler doctor --json

# Basic conversion
gobbler document ./paper.pdf -o ./outputs/paper.md

# Disable OCR for faster digital PDF conversion
gobbler document ./paper.pdf --no-ocr -o ./outputs/paper.md

# Office documents
gobbler document ./report.docx -o ./outputs/report.md
gobbler document ./slides.pptx -o ./outputs/slides.md
gobbler document ./sheet.xlsx -o ./outputs/sheet.md

# JSON or table output
gobbler document ./report.pdf --format json -o ./outputs/report.json
gobbler document ./sheet.xlsx --format table
```

## Requirements

- Document conversion uses the Docling service.
- Start services with `make start-docker` or `docker compose up -d docling`.
- Docling can need substantial memory for OCR-heavy PDFs; allocate enough Docker/Colima resources.

## Useful options

- `--output`, `-o`: output file path.
- `--ocr/--no-ocr`: OCR is enabled by default for scanned documents.
- `--format`, `-f`: `markdown`, `json`, or `table`.
- `--provider`, `-p`: document conversion provider, usually `docling`.

## OCR guidance

- Digital PDF with embedded text: use `--no-ocr` for speed.
- Scanned PDF: keep OCR enabled.
- DOCX/PPTX/XLSX/XLS: native extraction usually works without OCR concerns.

## Troubleshooting

```bash
gobbler doctor --json
make start-docker
docker compose ps || docker-compose ps
docker logs gobbler-docling --tail 50
```

For directories of documents, use `references/batch.md`.
