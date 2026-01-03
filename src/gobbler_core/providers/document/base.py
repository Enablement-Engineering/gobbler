"""Base classes for document conversion providers.

This module defines the abstract interface for document conversion
providers in Gobbler.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class DocumentResult:
    """Result from a document conversion provider.

    Attributes:
        markdown: Converted markdown content
        pages: Number of pages in document
        metadata: Additional provider-specific metadata
    """

    markdown: str
    pages: int
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def word_count(self) -> int:
        """Get approximate word count of converted content."""
        return len(self.markdown.split())


class DocumentProvider(ABC):
    """Abstract base class for document conversion providers.

    All document conversion providers must implement this interface to ensure
    consistent behavior across different backends (e.g., Docling, Unstructured,
    PyMuPDF, etc.).

    Example:
        class MyDocumentProvider(DocumentProvider):
            @property
            def name(self) -> str:
                return "my-provider"

            async def convert(
                self,
                file_path: Path,
                ocr: bool = True,
                **options,
            ) -> DocumentResult:
                # Implementation here
                pass

            def supports_format(self, file_extension: str) -> bool:
                return file_extension.lower() in {".pdf", ".docx"}
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Provider name for identification and logging.

        Returns:
            Unique provider identifier in kebab-case (e.g., "docling")
        """

    @abstractmethod
    async def convert(
        self,
        file_path: Path,
        ocr: bool = True,
        **options: Any,
    ) -> DocumentResult:
        """Convert document file to markdown.

        Args:
            file_path: Path to document file (PDF, DOCX, PPTX, XLSX)
            ocr: Enable OCR for scanned documents
            **options: Provider-specific options

        Returns:
            DocumentResult with markdown content and metadata

        Raises:
            FileNotFoundError: If file_path doesn't exist
            ValueError: If file format is not supported
            RuntimeError: If conversion fails
        """

    @abstractmethod
    def supports_format(self, file_extension: str) -> bool:
        """Check if this provider supports the given file format.

        Args:
            file_extension: File extension including dot (e.g., ".pdf")

        Returns:
            True if format is supported
        """

    def __repr__(self) -> str:
        """Return string representation of provider."""
        return f"{self.__class__.__name__}(name={self.name!r})"
