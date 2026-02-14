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

    Reads service URL from config file. Falls back to defaults if
    config is unavailable.

    Args:
        **kwargs: Override configuration options (service_url, timeout)

    Returns:
        Configured DocumentProvider instance
    """
    service_url = kwargs.pop("service_url", None)

    if service_url is None:
        try:
            from gobbler_mcp.config import get_config

            config = get_config()
            service_url = config.get_service_url("docling")
        except Exception:
            service_url = "http://localhost:5001"

    return DoclingProvider(service_url=service_url, **kwargs)
