"""Docling document conversion provider.

This provider uses the Docling Docker service for document conversion
to markdown with optional OCR support.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import aiofiles

from gobbler_core.providers.document.base import DocumentProvider, DocumentResult
from gobbler_core.providers.registry import ProviderRegistry
from gobbler_core.utils.http_client import RetryableHTTPClient

logger = logging.getLogger(__name__)

# Supported document formats
SUPPORTED_EXTENSIONS: set[str] = {".pdf", ".docx", ".pptx", ".xlsx"}


class DoclingProvider(DocumentProvider):
    """Document conversion provider using Docling Docker service.

    Converts PDF, DOCX, PPTX, and XLSX documents to markdown using
    the Docling service running in Docker. Supports OCR for scanned
    documents.

    Attributes:
        service_url: URL of the Docling service

    Example:
        provider = DoclingProvider(service_url="http://localhost:5001")
        result = await provider.convert(Path("document.pdf"), ocr=True)
        print(result.markdown)
    """

    def __init__(
        self,
        service_url: str = "http://localhost:5001",
        timeout: float = 120.0,
    ) -> None:
        """Initialize the Docling provider.

        Args:
            service_url: URL of the Docling service
            timeout: Request timeout in seconds
        """
        self.service_url = service_url.rstrip("/")
        self.timeout = timeout

    @property
    def name(self) -> str:
        """Return provider name."""
        return "docling"

    async def convert(
        self,
        file_path: Path,
        ocr: bool = True,
        **options: Any,  # noqa: ARG002  # Reserved for future provider options
    ) -> DocumentResult:
        """Convert document to markdown using Docling service.

        Args:
            file_path: Path to document file
            ocr: Enable OCR for scanned documents
            **options: Additional options (currently unused)

        Returns:
            DocumentResult with markdown content and metadata

        Raises:
            FileNotFoundError: If file_path doesn't exist
            ValueError: If file format is not supported
            RuntimeError: If conversion fails or service unavailable
        """
        # Validate file exists
        if not file_path.exists():
            msg = f"Document file not found: {file_path}"
            raise FileNotFoundError(msg)

        # Validate format
        ext = file_path.suffix.lower()
        if not self.supports_format(ext):
            msg = f"Unsupported format: {ext}. Supported: {', '.join(sorted(SUPPORTED_EXTENSIONS))}"
            raise ValueError(msg)

        # Read file
        try:
            async with aiofiles.open(file_path, "rb") as f:
                file_data = await f.read()
        except Exception as e:
            msg = f"Failed to read document file: {e}"
            raise RuntimeError(msg) from e

        # Make request to Docling service
        try:
            async with RetryableHTTPClient(timeout=self.timeout) as client:
                files = {"files": (file_path.name, file_data)}
                data = {
                    "to_formats": "md",
                    "do_ocr": str(ocr).lower(),
                }

                response = await client.post(
                    f"{self.service_url}/v1/convert/file",
                    files=files,
                    data=data,
                )
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
        return self._process_response(result, file_path)

    def _process_response(self, result: dict[str, Any], file_path: Path) -> DocumentResult:
        """Process the Docling API response.

        Args:
            result: JSON response from Docling
            file_path: Original file path for metadata

        Returns:
            DocumentResult

        Raises:
            RuntimeError: If conversion failed
        """
        status = result.get("status")

        if status == "failure":
            errors = result.get("errors", ["Unknown error"])
            msg = f"Document conversion failed: {'; '.join(errors)}"
            raise RuntimeError(msg)

        if status == "skipped":
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

        # Estimate page count
        word_count = len(markdown_content.split())
        pages = result.get("pages", 0) if "pages" in result else max(1, word_count // 300)

        return DocumentResult(
            markdown=markdown_content,
            pages=pages,
            metadata={
                "file_path": str(file_path),
                "format": file_path.suffix.lower(),
                "service": "docling",
            },
        )

    def supports_format(self, file_extension: str) -> bool:
        """Check if file format is supported.

        Args:
            file_extension: File extension including dot (e.g., ".pdf")

        Returns:
            True if format is supported
        """
        return file_extension.lower() in SUPPORTED_EXTENSIONS


# Register provider with the registry
ProviderRegistry.register("document", "docling", DoclingProvider)
