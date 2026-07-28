"""Regression tests for structurally registered provider contracts."""

from pathlib import Path
from typing import Any

import pytest

from gobbler_cli.commands import convert
from gobbler_cli.output import OutputFormat
from gobbler_core.providers.document.base import DocumentResult
from gobbler_core.providers.registry import ProviderRegistry
from gobbler_core.providers.transcription import get_default_provider
from gobbler_core.providers.transcription.base import TranscriptionResult
from gobbler_core.providers.webpage.base import WebPageResult


class StructuralTranscriptionProvider:
    """Transcription provider that satisfies the protocol without subclassing the ABC."""

    def __init__(self, **_options: Any) -> None:
        """Accept registry construction options used by the audio CLI path."""

    @property
    def name(self) -> str:
        return "structural-transcription-test"

    async def transcribe(
        self,
        audio_path: Path,
        language: str = "auto",
        **options: Any,
    ) -> TranscriptionResult:
        return TranscriptionResult(
            text="Structural audio result",
            segments=[],
            language=language or "en",
            duration=1.0,
            metadata={"path": str(audio_path), **options},
        )

    def supports_format(self, file_extension: str) -> bool:
        return file_extension == ".wav"


class StructuralDocumentProvider:
    """Document provider that satisfies the protocol without subclassing the ABC."""

    @property
    def name(self) -> str:
        return "structural-document-test"

    async def convert(
        self,
        file_path: Path,
        ocr: bool = True,
        **options: Any,
    ) -> DocumentResult:
        return DocumentResult(
            markdown="# Structural document result",
            pages=1,
            metadata={"path": str(file_path), "ocr": ocr, **options},
        )

    def supports_format(self, file_extension: str) -> bool:
        return file_extension == ".pdf"


class StructuralWebPageProvider:
    """Webpage provider that satisfies the protocol without subclassing the ABC."""

    @property
    def name(self) -> str:
        return "structural-webpage-test"

    async def fetch(
        self,
        url: str,
        timeout: int = 30,
        **options: Any,
    ) -> WebPageResult:
        return WebPageResult(
            markdown="# Structural webpage result",
            title="Structural webpage",
            url=url,
            metadata={"timeout": timeout, **options},
        )


def _register(category: str, name: str, provider_class: type[Any]) -> None:
    ProviderRegistry.register(category, name, provider_class)


def test_default_transcription_provider_accepts_structural_registration() -> None:
    """The default factory must honor the registry's structural type contract."""
    provider_name = "structural-transcription-test"
    _register("transcription", provider_name, StructuralTranscriptionProvider)
    try:
        provider = get_default_provider(provider=provider_name)
    finally:
        ProviderRegistry.unregister("transcription", provider_name)

    assert isinstance(provider, StructuralTranscriptionProvider)


@pytest.mark.asyncio
async def test_explicit_audio_provider_accepts_structural_registration(tmp_path: Path) -> None:
    """The explicit audio CLI path must execute a structurally registered provider."""
    provider_name = "structural-transcription-test"
    source = tmp_path / "audio.wav"
    output = tmp_path / "audio.md"
    source.write_bytes(b"audio")
    _register("transcription", provider_name, StructuralTranscriptionProvider)
    try:
        await convert._convert_audio(
            file_path=source,
            output=output,
            language="en",
            model="small",
            timestamps=False,
            output_format=OutputFormat.MARKDOWN,
            provider_name=provider_name,
        )
    finally:
        ProviderRegistry.unregister("transcription", provider_name)

    assert "Structural audio result" in output.read_text()


@pytest.mark.asyncio
async def test_explicit_document_provider_accepts_structural_registration(tmp_path: Path) -> None:
    """The explicit document CLI path must execute a structurally registered provider."""
    provider_name = "structural-document-test"
    source = tmp_path / "document.pdf"
    output = tmp_path / "document.md"
    source.write_bytes(b"document")
    _register("document", provider_name, StructuralDocumentProvider)
    try:
        await convert._convert_document(
            file_path=source,
            output=output,
            ocr=True,
            output_format=OutputFormat.MARKDOWN,
            provider_name=provider_name,
        )
    finally:
        ProviderRegistry.unregister("document", provider_name)

    assert "Structural document result" in output.read_text()


@pytest.mark.asyncio
async def test_explicit_webpage_provider_accepts_structural_registration(tmp_path: Path) -> None:
    """The explicit webpage CLI path must execute a structurally registered provider."""
    provider_name = "structural-webpage-test"
    output = tmp_path / "webpage.md"
    _register("webpage", provider_name, StructuralWebPageProvider)
    try:
        await convert._convert_webpage(
            url="https://example.com/structural",
            output=output,
            css_selector=None,
            clean=False,
            timeout=30,
            include_images=False,
            output_format=OutputFormat.MARKDOWN,
            provider_name=provider_name,
            use_proxy=False,
        )
    finally:
        ProviderRegistry.unregister("webpage", provider_name)

    assert "Structural webpage result" in output.read_text()
