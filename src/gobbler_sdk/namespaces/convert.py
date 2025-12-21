"""Conversion namespace for Gobbler SDK.

This module provides methods for converting various content types to markdown.
"""

from typing import TYPE_CHECKING, Any

from gobbler_sdk.exceptions import ConversionError
from gobbler_sdk.types import (
    ConversionMetadata,
    ConversionResult,
    DocumentOptions,
    TranscriptionOptions,
    WebpageOptions,
)

if TYPE_CHECKING:
    import httpx


class ConvertNamespace:
    """Namespace for content conversion operations.

    This class provides methods for converting different content types
    (YouTube, audio, documents, webpages) to markdown format.
    """

    def __init__(self, client: "httpx.Client", base_url: str) -> None:
        """Initialize the convert namespace.

        Args:
            client: httpx Client instance for making requests
            base_url: Base URL of the Gobbler daemon API
        """
        self._client = client
        self._base_url = base_url

    def _parse_response(self, response_data: dict[str, Any]) -> ConversionResult:
        """Parse API response into ConversionResult.

        Args:
            response_data: Raw response data from API

        Returns:
            Parsed ConversionResult
        """
        metadata_data = response_data.get("metadata", {})
        metadata = ConversionMetadata(
            title=metadata_data.get("title"),
            source_url=metadata_data.get("source_url"),
            source_file=metadata_data.get("source_file"),
            content_type=metadata_data.get("content_type"),
            conversion_date=metadata_data.get("conversion_date"),
            language=metadata_data.get("language"),
            duration=metadata_data.get("duration"),
            word_count=metadata_data.get("word_count"),
            author=metadata_data.get("author"),
            description=metadata_data.get("description"),
            tags=metadata_data.get("tags", []),
            model=metadata_data.get("model"),
            error=metadata_data.get("error"),
        )

        return ConversionResult(
            markdown=response_data.get("markdown", ""),
            metadata=metadata,
            output_file=response_data.get("output_file"),
            success=response_data.get("success", True),
            error=response_data.get("error"),
        )

    def youtube(
        self,
        video_url: str,
        language: str | None = None,
        include_timestamps: bool = False,
        output_file: str | None = None,
    ) -> ConversionResult:
        """Convert a YouTube video to markdown transcript.

        Args:
            video_url: YouTube video URL
            language: Expected language code (ISO 639-1), auto-detected if not specified
            include_timestamps: Include timestamps in the transcript
            output_file: Optional path to save the output

        Returns:
            ConversionResult with markdown transcript and metadata

        Raises:
            ConversionError: If the conversion fails
            ConnectionError: If unable to connect to daemon
        """
        try:
            response = self._client.post(
                f"{self._base_url}/convert/youtube",
                json={
                    "video_url": video_url,
                    "language": language,
                    "include_timestamps": include_timestamps,
                    "output_file": output_file,
                },
            )
            response.raise_for_status()
            return self._parse_response(response.json())
        except Exception as e:
            error_msg = str(e)
            if hasattr(e, "response") and hasattr(e.response, "json"):
                try:
                    error_data = e.response.json()
                    error_msg = error_data.get("error", error_msg)
                except Exception:
                    pass
            raise ConversionError(f"Failed to convert YouTube video: {error_msg}", source=video_url) from e

    def audio(
        self,
        file_path: str,
        options: TranscriptionOptions | None = None,
    ) -> ConversionResult:
        """Transcribe an audio file to markdown.

        Args:
            file_path: Path to audio file (local or URL)
            options: Transcription options

        Returns:
            ConversionResult with markdown transcript and metadata

        Raises:
            ConversionError: If the transcription fails
            ConnectionError: If unable to connect to daemon
        """
        opts = options or TranscriptionOptions()

        try:
            response = self._client.post(
                f"{self._base_url}/convert/audio",
                json={
                    "file_path": file_path,
                    "model": opts.model,
                    "language": opts.language,
                    "include_timestamps": opts.include_timestamps,
                    "output_file": opts.output_file,
                    "auto_queue": opts.auto_queue,
                },
            )
            response.raise_for_status()
            return self._parse_response(response.json())
        except Exception as e:
            error_msg = str(e)
            if hasattr(e, "response") and hasattr(e.response, "json"):
                try:
                    error_data = e.response.json()
                    error_msg = error_data.get("error", error_msg)
                except Exception:
                    pass
            raise ConversionError(f"Failed to transcribe audio: {error_msg}", source=file_path) from e

    def document(
        self,
        file_path: str,
        options: DocumentOptions | None = None,
    ) -> ConversionResult:
        """Convert a document to markdown.

        Args:
            file_path: Path to document file (local or URL)
            options: Document conversion options

        Returns:
            ConversionResult with markdown content and metadata

        Raises:
            ConversionError: If the conversion fails
            ConnectionError: If unable to connect to daemon
        """
        opts = options or DocumentOptions()

        try:
            response = self._client.post(
                f"{self._base_url}/convert/document",
                json={
                    "file_path": file_path,
                    "enable_ocr": opts.enable_ocr,
                    "output_file": opts.output_file,
                },
            )
            response.raise_for_status()
            return self._parse_response(response.json())
        except Exception as e:
            error_msg = str(e)
            if hasattr(e, "response") and hasattr(e.response, "json"):
                try:
                    error_data = e.response.json()
                    error_msg = error_data.get("error", error_msg)
                except Exception:
                    pass
            raise ConversionError(f"Failed to convert document: {error_msg}", source=file_path) from e

    def webpage(
        self,
        url: str,
        options: WebpageOptions | None = None,
    ) -> ConversionResult:
        """Convert a webpage to markdown.

        Args:
            url: URL of the webpage to convert
            options: Webpage conversion options

        Returns:
            ConversionResult with markdown content and metadata

        Raises:
            ConversionError: If the conversion fails
            ConnectionError: If unable to connect to daemon
        """
        opts = options or WebpageOptions()

        try:
            response = self._client.post(
                f"{self._base_url}/convert/webpage",
                json={
                    "url": url,
                    "include_images": opts.include_images,
                    "timeout": opts.timeout,
                    "css_selector": opts.css_selector,
                    "xpath": opts.xpath,
                    "extract_links": opts.extract_links,
                    "session_id": opts.session_id,
                    "bypass_cache": opts.bypass_cache,
                },
            )
            response.raise_for_status()
            return self._parse_response(response.json())
        except Exception as e:
            error_msg = str(e)
            if hasattr(e, "response") and hasattr(e.response, "json"):
                try:
                    error_data = e.response.json()
                    error_msg = error_data.get("error", error_msg)
                except Exception:
                    pass
            raise ConversionError(f"Failed to convert webpage: {error_msg}", source=url) from e


class AsyncConvertNamespace:
    """Async namespace for content conversion operations.

    This class provides async methods for converting different content types
    (YouTube, audio, documents, webpages) to markdown format.
    """

    def __init__(self, client: "httpx.AsyncClient", base_url: str) -> None:
        """Initialize the async convert namespace.

        Args:
            client: httpx AsyncClient instance for making requests
            base_url: Base URL of the Gobbler daemon API
        """
        self._client = client
        self._base_url = base_url

    def _parse_response(self, response_data: dict[str, Any]) -> ConversionResult:
        """Parse API response into ConversionResult.

        Args:
            response_data: Raw response data from API

        Returns:
            Parsed ConversionResult
        """
        metadata_data = response_data.get("metadata", {})
        metadata = ConversionMetadata(
            title=metadata_data.get("title"),
            source_url=metadata_data.get("source_url"),
            source_file=metadata_data.get("source_file"),
            content_type=metadata_data.get("content_type"),
            conversion_date=metadata_data.get("conversion_date"),
            language=metadata_data.get("language"),
            duration=metadata_data.get("duration"),
            word_count=metadata_data.get("word_count"),
            author=metadata_data.get("author"),
            description=metadata_data.get("description"),
            tags=metadata_data.get("tags", []),
            model=metadata_data.get("model"),
            error=metadata_data.get("error"),
        )

        return ConversionResult(
            markdown=response_data.get("markdown", ""),
            metadata=metadata,
            output_file=response_data.get("output_file"),
            success=response_data.get("success", True),
            error=response_data.get("error"),
        )

    async def youtube(
        self,
        video_url: str,
        language: str | None = None,
        include_timestamps: bool = False,
        output_file: str | None = None,
    ) -> ConversionResult:
        """Convert a YouTube video to markdown transcript.

        Args:
            video_url: YouTube video URL
            language: Expected language code (ISO 639-1), auto-detected if not specified
            include_timestamps: Include timestamps in the transcript
            output_file: Optional path to save the output

        Returns:
            ConversionResult with markdown transcript and metadata

        Raises:
            ConversionError: If the conversion fails
            ConnectionError: If unable to connect to daemon
        """
        try:
            response = await self._client.post(
                f"{self._base_url}/convert/youtube",
                json={
                    "video_url": video_url,
                    "language": language,
                    "include_timestamps": include_timestamps,
                    "output_file": output_file,
                },
            )
            response.raise_for_status()
            return self._parse_response(response.json())
        except Exception as e:
            error_msg = str(e)
            if hasattr(e, "response") and hasattr(e.response, "json"):
                try:
                    error_data = e.response.json()
                    error_msg = error_data.get("error", error_msg)
                except Exception:
                    pass
            raise ConversionError(f"Failed to convert YouTube video: {error_msg}", source=video_url) from e

    async def audio(
        self,
        file_path: str,
        options: TranscriptionOptions | None = None,
    ) -> ConversionResult:
        """Transcribe an audio file to markdown.

        Args:
            file_path: Path to audio file (local or URL)
            options: Transcription options

        Returns:
            ConversionResult with markdown transcript and metadata

        Raises:
            ConversionError: If the transcription fails
            ConnectionError: If unable to connect to daemon
        """
        opts = options or TranscriptionOptions()

        try:
            response = await self._client.post(
                f"{self._base_url}/convert/audio",
                json={
                    "file_path": file_path,
                    "model": opts.model,
                    "language": opts.language,
                    "include_timestamps": opts.include_timestamps,
                    "output_file": opts.output_file,
                    "auto_queue": opts.auto_queue,
                },
            )
            response.raise_for_status()
            return self._parse_response(response.json())
        except Exception as e:
            error_msg = str(e)
            if hasattr(e, "response") and hasattr(e.response, "json"):
                try:
                    error_data = e.response.json()
                    error_msg = error_data.get("error", error_msg)
                except Exception:
                    pass
            raise ConversionError(f"Failed to transcribe audio: {error_msg}", source=file_path) from e

    async def document(
        self,
        file_path: str,
        options: DocumentOptions | None = None,
    ) -> ConversionResult:
        """Convert a document to markdown.

        Args:
            file_path: Path to document file (local or URL)
            options: Document conversion options

        Returns:
            ConversionResult with markdown content and metadata

        Raises:
            ConversionError: If the conversion fails
            ConnectionError: If unable to connect to daemon
        """
        opts = options or DocumentOptions()

        try:
            response = await self._client.post(
                f"{self._base_url}/convert/document",
                json={
                    "file_path": file_path,
                    "enable_ocr": opts.enable_ocr,
                    "output_file": opts.output_file,
                },
            )
            response.raise_for_status()
            return self._parse_response(response.json())
        except Exception as e:
            error_msg = str(e)
            if hasattr(e, "response") and hasattr(e.response, "json"):
                try:
                    error_data = e.response.json()
                    error_msg = error_data.get("error", error_msg)
                except Exception:
                    pass
            raise ConversionError(f"Failed to convert document: {error_msg}", source=file_path) from e

    async def webpage(
        self,
        url: str,
        options: WebpageOptions | None = None,
    ) -> ConversionResult:
        """Convert a webpage to markdown.

        Args:
            url: URL of the webpage to convert
            options: Webpage conversion options

        Returns:
            ConversionResult with markdown content and metadata

        Raises:
            ConversionError: If the conversion fails
            ConnectionError: If unable to connect to daemon
        """
        opts = options or WebpageOptions()

        try:
            response = await self._client.post(
                f"{self._base_url}/convert/webpage",
                json={
                    "url": url,
                    "include_images": opts.include_images,
                    "timeout": opts.timeout,
                    "css_selector": opts.css_selector,
                    "xpath": opts.xpath,
                    "extract_links": opts.extract_links,
                    "session_id": opts.session_id,
                    "bypass_cache": opts.bypass_cache,
                },
            )
            response.raise_for_status()
            return self._parse_response(response.json())
        except Exception as e:
            error_msg = str(e)
            if hasattr(e, "response") and hasattr(e.response, "json"):
                try:
                    error_data = e.response.json()
                    error_msg = error_data.get("error", error_msg)
                except Exception:
                    pass
            raise ConversionError(f"Failed to convert webpage: {error_msg}", source=url) from e
