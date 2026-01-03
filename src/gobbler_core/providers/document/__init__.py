"""Document conversion providers for PDF, DOCX, PPTX, XLSX to markdown.

This package provides abstracted document conversion capabilities with multiple
backend implementations.

Available Providers:
    - docling: Docling Docker service (default)

Example:
    from gobbler_core.providers.document import (
        DocumentProvider,
        DoclingProvider,
        get_default_provider,
    )

    # Use default provider from config
    provider = get_default_provider()
    result = await provider.convert(Path("document.pdf"))

    # Or create specific provider
    provider = DoclingProvider(service_url="http://localhost:5001")
    result = await provider.convert(Path("document.pdf"), ocr=True)
"""

from gobbler_core.providers.document.base import (
    DocumentProvider,
    DocumentResult,
)
from gobbler_core.providers.document.docling import DoclingProvider

__all__ = [
    "DoclingProvider",
    "DocumentProvider",
    "DocumentResult",
    "get_default_provider",
]


def get_default_provider(**kwargs) -> DocumentProvider:
    """Get the default document provider based on configuration.

    Args:
        **kwargs: Override configuration options

    Returns:
        Configured DocumentProvider instance
    """
    from gobbler_core.providers.registry import ProviderRegistry

    provider_name = kwargs.pop("provider", "docling")
    return ProviderRegistry.create("document", provider_name, **kwargs)
