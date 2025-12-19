#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["httpx>=0.27.0"]
# ///
"""
Convert document to markdown using Docling service.

Usage:
    uv run convert.py <file_path> [--ocr] [--output FILE]

Examples:
    uv run convert.py document.pdf
    uv run convert.py scanned.pdf --ocr
    uv run convert.py document.docx --output output.md
"""

import argparse
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import httpx

DOCLING_URL = "http://localhost:5001"
SUPPORTED_EXTENSIONS = (".pdf", ".docx", ".pptx", ".xlsx")


def create_frontmatter(
    file_path: str, file_format: str, pages: int, word_count: int, conversion_time_ms: int
) -> str:
    """Create YAML frontmatter for document."""
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    return f"""---
source: "{file_path}"
type: document
format: {file_format}
pages: {pages}
word_count: {word_count}
conversion_time_ms: {conversion_time_ms}
converted_at: {timestamp}
---

"""


def convert_document(
    file_path: str,
    enable_ocr: bool = True,
    timeout: int = 120,
) -> str:
    """Convert document to markdown."""
    path = Path(file_path)

    if not path.exists():
        raise FileNotFoundError(f"File not found: {file_path}")

    ext = path.suffix.lower()
    if ext not in SUPPORTED_EXTENSIONS:
        raise ValueError(f"Unsupported format: {ext}. Supported: {SUPPORTED_EXTENSIONS}")

    start_time = time.time()

    # Read file
    file_data = path.read_bytes()
    filename = path.name
    file_format = ext.lstrip(".")

    # Prepare multipart form
    files = {"files": (filename, file_data)}
    data = {
        "to_formats": "md",
        "do_ocr": str(enable_ocr).lower(),
    }

    # Make request to Docling
    # Use short connect timeout but allow longer read timeout for large documents
    timeout_config = httpx.Timeout(timeout, connect=5.0)
    with httpx.Client(timeout=timeout_config) as client:
        response = client.post(
            f"{DOCLING_URL}/v1/convert/file",
            files=files,
            data=data,
        )
        response.raise_for_status()
        result = response.json()

    # Check for errors
    if result.get("status") == "failure":
        errors = result.get("errors", ["Unknown error"])
        raise RuntimeError(f"Conversion failed: {'; '.join(errors)}")

    if result.get("status") == "skipped":
        raise RuntimeError("Conversion skipped. File may be corrupted or unsupported.")

    # Extract markdown
    document_data = result.get("document", {})
    markdown_content = document_data.get("md_content", "")

    if not markdown_content:
        raise RuntimeError("No markdown content returned. File may be corrupted.")

    conversion_time_ms = int((time.time() - start_time) * 1000)
    word_count = len(markdown_content.split())

    # Estimate pages (Docling doesn't always return page count)
    pages = max(1, word_count // 300)

    # Create frontmatter
    frontmatter = create_frontmatter(
        file_path=str(path.absolute()),
        file_format=file_format,
        pages=pages,
        word_count=word_count,
        conversion_time_ms=conversion_time_ms,
    )

    return frontmatter + markdown_content


def main():
    parser = argparse.ArgumentParser(description="Convert document to markdown")
    parser.add_argument("file", help="Document file path")
    parser.add_argument("--ocr", action="store_true", help="Enable OCR (default: enabled)")
    parser.add_argument("--no-ocr", action="store_true", help="Disable OCR")
    parser.add_argument("--output", "-o", help="Output file path")
    parser.add_argument("--timeout", "-t", type=int, default=120, help="Timeout in seconds")
    args = parser.parse_args()

    enable_ocr = not args.no_ocr  # OCR enabled by default

    try:
        markdown = convert_document(
            args.file,
            enable_ocr=enable_ocr,
            timeout=args.timeout,
        )

        if args.output:
            Path(args.output).write_text(markdown)
            print(f"Saved to {args.output}", file=sys.stderr)
        else:
            print(markdown)

    except httpx.ConnectError:
        print("Error: Cannot connect to Docling. Is it running on port 5001?", file=sys.stderr)
        sys.exit(1)
    except FileNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
