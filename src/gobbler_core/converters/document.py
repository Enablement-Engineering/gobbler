"""Document conversion module with pluggable provider support.

This module provides document conversion capabilities with support for
pluggable conversion providers. The default provider uses the Docling
Docker service.

Example:
    # Using default provider
    markdown, metadata = await convert_document_to_markdown("document.pdf")

    # Using a specific provider
    from gobbler_core.providers.document import DoclingProvider
    provider = DoclingProvider(service_url="http://localhost:5001")
    markdown, metadata = await convert_document_to_markdown("document.pdf", provider=provider)
"""

from __future__ import annotations

import logging
import time
from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING

import aiofiles

from gobbler_core.utils.file_handler import get_file_extension, validate_input_path
from gobbler_core.utils.frontmatter import count_words, create_document_frontmatter
from gobbler_core.utils.http_client import RetryableHTTPClient

if TYPE_CHECKING:
    from gobbler_core.providers.document import DocumentProvider

logger = logging.getLogger(__name__)

SUPPORTED_EXTENSIONS = (".pdf", ".docx", ".pptx", ".xlsx")


async def convert_document_to_markdown(
    file_path: str,
    enable_ocr: bool = True,
    service_url: str = "http://localhost:5001",
    metrics_callback: Callable[[str, int], None] | None = None,
    logger_instance: logging.Logger | None = None,
    provider: DocumentProvider | None = None,
) -> tuple[str, dict]:
    """Convert document to markdown using a document conversion provider.

    Uses a pluggable document conversion provider for the actual conversion.
    If no provider is specified, uses the default Docling Docker service.

    Args:
        file_path: Absolute path to document file
        enable_ocr: Enable OCR for scanned documents
        service_url: Docling service URL (default: "http://localhost:5001")
            Only used if provider is None
        metrics_callback: Optional callback for metrics tracking,
            called with (converter_type, size_bytes)
        logger_instance: Optional custom logger instance
        provider: Optional document conversion provider. If None, uses
            default DoclingProvider with the specified service_url.

    Returns:
        Tuple of (markdown_content, metadata)

    Raises:
        ValueError: Invalid file path or unsupported format
        RuntimeError: Service unavailable or conversion failed

    Example:
        # Using default provider
        markdown, metadata = await convert_document_to_markdown("document.pdf")

        # Using a specific provider
        from gobbler_core.providers.document import DoclingProvider
        provider = DoclingProvider(service_url="http://localhost:5001")
        markdown, metadata = await convert_document_to_markdown("document.pdf", provider=provider)
    """
    # Use custom logger if provided, otherwise use module logger
    log = logger_instance or logger

    # Validate file path
    error = validate_input_path(file_path, SUPPORTED_EXTENSIONS)
    if error:
        raise ValueError(error)

    file_format = get_file_extension(file_path)
    provider_name = provider.name if provider else "docling"

    log.info(
        "Starting document conversion",
        extra={
            "extra_fields": {
                "file_path": file_path,
                "file_format": file_format,
                "enable_ocr": enable_ocr,
                "provider": provider_name,
            }
        },
    )
    start_time = time.time()

    # Use provider-based conversion if a provider is specified
    if provider is not None:
        result = await provider.convert(Path(file_path), ocr=enable_ocr)
        markdown_content = result.markdown
        pages = result.pages
        word_count = result.word_count
    else:
        # Legacy path: use direct Docling HTTP calls
        markdown_content, pages, word_count = await _convert_with_docling(
            file_path, enable_ocr, service_url, log
        )

    conversion_time_ms = int((time.time() - start_time) * 1000)

    # Create frontmatter
    frontmatter = create_document_frontmatter(
        file_path=file_path,
        doc_format=file_format,
        pages=pages,
        word_count=word_count,
        conversion_time_ms=conversion_time_ms,
    )

    # Combine frontmatter and markdown
    full_markdown = frontmatter + markdown_content

    # Track conversion size via callback if provided
    if metrics_callback is not None:
        metrics_callback("document", len(full_markdown))

    # Prepare metadata response
    metadata = {
        "file_path": file_path,
        "format": file_format,
        "pages": pages,
        "word_count": word_count,
        "conversion_time_ms": conversion_time_ms,
        "provider": provider_name,
    }

    log.info(
        "Document conversion completed",
        extra={
            "extra_fields": {
                "word_count": word_count,
                "pages": pages,
                "file_format": file_format,
                "provider": provider_name,
            }
        },
    )

    return full_markdown, metadata


async def _convert_with_docling(
    file_path: str,
    enable_ocr: bool,
    service_url: str,
    log: logging.Logger,
) -> tuple[str, int, int]:
    """Convert document using direct Docling HTTP calls (legacy path).

    Args:
        file_path: Path to document file
        enable_ocr: Enable OCR for scanned documents
        service_url: Docling service URL
        log: Logger instance

    Returns:
        Tuple of (markdown_content, pages, word_count)

    Raises:
        RuntimeError: If conversion fails
    """
    # Read file asynchronously
    try:
        async with aiofiles.open(file_path, "rb") as f:
            file_data = await f.read()
    except Exception as e:
        msg = f"Failed to read document file: {e}"
        raise RuntimeError(msg) from e

    filename = Path(file_path).name

    try:
        async with RetryableHTTPClient(timeout=120.0) as client:
            # Prepare the multipart form data
            files = {"files": (filename, file_data)}
            data = {
                "to_formats": "md",
                "do_ocr": str(enable_ocr).lower(),
            }

            # Make request to Docling service
            response = await client.post(f"{service_url}/v1/convert/file", files=files, data=data)
            response.raise_for_status()
            result = response.json()

    except Exception as e:
        error_str = str(e)
        error_type = type(e).__name__

        if "ConnectError" in error_type or "Connection" in error_str:
            msg = (
                "Docling service unavailable. The service may not be running. "
                "Start with: docker-compose up -d docling"
            )
            raise RuntimeError(msg) from e
        msg = f"Document conversion failed: {e}"
        raise RuntimeError(msg) from e

    # Process response
    if result.get("status") == "failure":
        errors = result.get("errors", ["Unknown error"])
        msg = f"Document conversion failed: {'; '.join(errors)}"
        raise RuntimeError(msg)

    if result.get("status") == "skipped":
        msg = (
            "Document conversion was skipped. The file may be corrupted or "
            "use an unsupported format variation."
        )
        raise RuntimeError(msg)

    document_data = result.get("document", {})
    markdown_content = document_data.get("md_content", "")

    if not markdown_content:
        msg = (
            "Failed to extract markdown from document. The document may be "
            "corrupted or password-protected."
        )
        raise RuntimeError(msg)

    # Count words in the markdown
    word_count = count_words(markdown_content)

    # Estimate page count from content
    pages = result.get("pages", 0) if "pages" in result else max(1, word_count // 300)

    return markdown_content, pages, word_count
