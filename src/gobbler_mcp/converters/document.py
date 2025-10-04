"""Document conversion module (stub for Docling integration)."""

import logging
import time
from typing import Dict, Tuple

from ..config import get_config
from ..metrics import conversion_size, track_conversion
from ..utils.file_handler import get_file_extension, validate_input_path
from ..utils.frontmatter import count_words, create_document_frontmatter
from ..utils.http_client import RetryableHTTPClient

logger = logging.getLogger(__name__)

SUPPORTED_EXTENSIONS = (".pdf", ".docx", ".pptx", ".xlsx")


async def convert_document_to_markdown(
    file_path: str,
    enable_ocr: bool = True,
) -> Tuple[str, Dict]:
    """
    Convert document to markdown using Docling service.

    Makes HTTP POST request to the Docling service running in Docker,
    uploading the file for conversion. Supports PDF, DOCX, PPTX, XLSX
    formats with optional OCR for scanned documents.

    Args:
        file_path: Absolute path to document file
        enable_ocr: Enable OCR for scanned documents

    Returns:
        Tuple of (markdown_content, metadata)

    Raises:
        ValueError: Invalid file path or unsupported format
        RuntimeError: Service unavailable or conversion failed
    """
    # Validate file path
    error = validate_input_path(file_path, SUPPORTED_EXTENSIONS)
    if error:
        raise ValueError(error)

    with track_conversion("document"):
        config = get_config()
        service_url = config.get_service_url("docling")
        file_format = get_file_extension(file_path)

        logger.info(
            "Starting document conversion",
            extra={"extra_fields": {"file_path": file_path, "file_format": file_format, "enable_ocr": enable_ocr}}
        )
        start_time = time.time()

        # Read file asynchronously
        try:
            import aiofiles
            async with aiofiles.open(file_path, "rb") as f:
                file_data = await f.read()
        except Exception as e:
            raise RuntimeError(f"Failed to read document file: {e}")

        # Prepare multipart file upload
        # Docling-serve API expects:
        # POST /v1/convert/file
        # Content-Type: multipart/form-data
        # Body: files (multipart), optional: to_formats, do_ocr, ocr_engine
        import os
        filename = os.path.basename(file_path)

        try:
            async with RetryableHTTPClient(timeout=120.0) as client:
                # Prepare the multipart form data
                files = {
                    "files": (filename, file_data)
                }

                # Prepare form data with conversion parameters
                data = {
                    "to_formats": "md",  # Request markdown output
                    "do_ocr": str(enable_ocr).lower(),  # Enable/disable OCR
                }

                # Make request to Docling service
                response = await client.post(
                    f"{service_url}/v1/convert/file",
                    files=files,
                    data=data
                )
                response.raise_for_status()
                result = response.json()

        except Exception as e:
            # Check if service is unavailable
            if "ConnectError" in str(type(e).__name__) or "Connection" in str(e):
                raise RuntimeError(
                    "Docling service unavailable. The service may not be running. "
                    "Start with: docker-compose up -d docling"
                )
            raise RuntimeError(f"Document conversion failed: {e}")

        # Calculate conversion time
        conversion_time_ms = int((time.time() - start_time) * 1000)

        # Extract markdown content from response
        # Response format: {"document": {"md_content": "..."}, "status": "success", ...}
        if result.get("status") == "failure":
            errors = result.get("errors", ["Unknown error"])
            raise RuntimeError(f"Document conversion failed: {'; '.join(errors)}")

        if result.get("status") == "skipped":
            raise RuntimeError(
                f"Document conversion was skipped. The file may be corrupted or "
                f"use an unsupported format variation."
            )

        document_data = result.get("document", {})
        markdown_content = document_data.get("md_content", "")

        if not markdown_content:
            raise RuntimeError(
                "Failed to extract markdown from document. The document may be "
                "corrupted or password-protected."
            )

        # Count words in the markdown
        word_count = count_words(markdown_content)

        # Estimate page count from content (Docling doesn't always provide page count)
        # We'll look for page markers or estimate based on content length
        pages = 0
        if hasattr(result, "pages"):
            pages = result.get("pages", 0)
        else:
            # Rough estimate: average 300 words per page
            pages = max(1, word_count // 300)

        # Create frontmatter
        frontmatter = create_document_frontmatter(
            file_path=file_path,
            format=file_format,
            pages=pages,
            word_count=word_count,
            conversion_time_ms=conversion_time_ms,
        )

        # Combine frontmatter and markdown
        full_markdown = frontmatter + markdown_content

        # Track conversion size
        conversion_size.labels(converter_type="document").observe(len(full_markdown))

        # Prepare metadata response
        metadata = {
            "file_path": file_path,
            "format": file_format,
            "pages": pages,
            "word_count": word_count,
            "conversion_time_ms": conversion_time_ms,
        }

        logger.info(
            "Document conversion completed",
            extra={"extra_fields": {"word_count": word_count, "pages": pages, "file_format": file_format}}
        )

        return full_markdown, metadata
