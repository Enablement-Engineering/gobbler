"""Single-file conversion tools.

Tools for converting individual files/URLs to markdown:
- transcribe_youtube: YouTube video transcript extraction
- fetch_webpage: Basic webpage to markdown conversion
- fetch_webpage_with_selector: Advanced webpage extraction with selectors
- convert_document: Document (PDF, DOCX, etc.) to markdown
- transcribe_audio: Audio/video file transcription
"""

import logging
from typing import Optional

import httpx
from fastmcp import FastMCP
from youtube_transcript_api import (
    NoTranscriptFound,
    TranscriptsDisabled,
    VideoUnavailable,
)

from ..constants import MIN_TIMEOUT, MAX_TIMEOUT
from ..config import get_config
from ..converters import (
    convert_audio_to_markdown,
    convert_document_to_markdown,
    convert_webpage_to_markdown,
    convert_webpage_with_selector,
    convert_youtube_to_markdown,
)
from ..utils import save_markdown_file, validate_output_path, get_metrics_callback

logger = logging.getLogger(__name__)


def register_tools(mcp: FastMCP):
    """Register conversion tools with the MCP server."""

    @mcp.tool()
    async def transcribe_youtube(
        video_url: str,
        include_timestamps: bool = False,
        language: str = "auto",
        output_file: Optional[str] = None,
    ) -> str:
        """
        Extract YouTube video transcript and convert to clean markdown format.

        Uses official YouTube transcript API for fast, accurate results. Works without
        Docker containers. Returns markdown with YAML frontmatter containing metadata
        about the video and transcript.

        Args:
            video_url: YouTube video URL (youtube.com/watch?v=ID or youtu.be/ID format)
            include_timestamps: Include timestamp markers in the transcript (default: False)
            language: Transcript language code (ISO 639-1) or 'auto' for video default (default: 'auto')
            output_file: Optional directory path or full file path to save markdown. If a directory is provided, the file will be named using the video title.

        Returns:
            Markdown text with YAML frontmatter if output_file not provided,
            or success message with file path if output_file provided
        """
        try:
            # Convert to markdown
            markdown, metadata = await convert_youtube_to_markdown(
                video_url=video_url,
                include_timestamps=include_timestamps,
                language=language,
            )

            # Handle output
            if output_file:
                import os
                from pathlib import Path

                output_path = Path(output_file)

                # If output_file is a directory or doesn't have .md extension, use video title
                if output_path.is_dir() or not output_file.endswith(".md"):
                    # Get title from metadata and sanitize for filename
                    title = metadata.get("title", f"video_{metadata['video_id']}")
                    # Remove invalid filename characters
                    safe_title = "".join(
                        c for c in title if c.isalnum() or c in (" ", "-", "_")
                    ).strip()
                    safe_title = safe_title.replace(" ", "_")

                    # Construct the full path
                    if output_path.is_dir():
                        output_file = str(output_path / f"{safe_title}.md")
                    else:
                        # It's a directory path provided as string
                        output_file = os.path.join(output_file, f"{safe_title}.md")

                # Validate output path
                error = validate_output_path(output_file)
                if error:
                    return f"Error: {error}"

                # Save to file
                success = await save_markdown_file(output_file, markdown)
                if success:
                    return f"Transcript saved to: {output_file}"
                else:
                    return f"Failed to write file: Permission denied for {output_file}"
            else:
                # Return markdown directly
                return markdown

        except ValueError as e:
            return str(e)
        except VideoUnavailable:
            return "Video not found: The video may be private, deleted, or the URL is incorrect."
        except TranscriptsDisabled:
            return (
                "No transcript available for this video. The video may not have captions, "
                "or they may be disabled. To transcribe anyway, use transcribe_audio with the video file."
            )
        except NoTranscriptFound as e:
            return (
                f"Transcript not available in language '{language}'. {str(e)}. "
                "Use language='auto' for default."
            )
        except Exception as e:
            logger.error(f"Unexpected error in transcribe_youtube: {e}", exc_info=True)
            return f"Failed to extract transcript: {str(e)}"

    @mcp.tool()
    async def fetch_webpage(
        url: str,
        include_images: bool = True,
        timeout: int = 30,
        output_file: Optional[str] = None,
    ) -> str:
        """
        Convert web page content to clean markdown format.

        Fetches HTML via Crawl4AI and converts to structured markdown, preserving
        document structure, headings, links, code blocks, and basic formatting. Handles
        JavaScript-rendered content via browser automation. Requires Crawl4AI Docker container.

        Args:
            url: The full HTTP/HTTPS URL of the web page to convert
            include_images: Include image alt text and references in markdown output (default: True)
            timeout: Request timeout in seconds (default: 30, max: 120)
            output_file: Optional absolute path to save markdown file (includes frontmatter)

        Returns:
            Markdown text with YAML frontmatter if output_file not provided,
            or success message with file path if output_file provided
        """
        try:
            # Validate timeout
            if timeout < MIN_TIMEOUT or timeout > MAX_TIMEOUT:
                return f"Error: timeout must be between {MIN_TIMEOUT} and {MAX_TIMEOUT} seconds"

            # Convert to markdown
            markdown, metadata = await convert_webpage_to_markdown(
                url=url,
                include_images=include_images,
                timeout=timeout,
            )

            # Handle output
            if output_file:
                error = validate_output_path(output_file)
                if error:
                    return f"Error: {error}"

                success = await save_markdown_file(output_file, markdown)
                if success:
                    return f"Web page saved to: {output_file}"
                else:
                    return f"Failed to write file: Permission denied for {output_file}"
            else:
                return markdown

        except httpx.ConnectError:
            return (
                "❌ Crawl4AI service unavailable.\n\n"
                "What went wrong:\n"
                "   The Crawl4AI Docker container is not running or not reachable.\n\n"
                "Why this happened:\n"
                "   • Docker services may not be started\n"
                "   • Container crashed or failed to start\n"
                "   • Port 11235 is blocked or in use\n\n"
                "How to fix:\n"
                "   1. Start services: `make start-docker`\n"
                "   2. Check status: `make status`\n"
                "   3. View logs: `make logs`\n\n"
                "Note: YouTube transcription still works without Docker!"
            )
        except httpx.TimeoutException:
            return (
                f"⏱️  Connection timeout after {timeout} seconds.\n\n"
                "What went wrong:\n"
                f"   Failed to fetch {url} within {timeout} seconds.\n\n"
                "Why this happened:\n"
                "   • Target server is slow or unresponsive\n"
                "   • Network connectivity issues\n"
                "   • URL may be inaccessible\n\n"
                "How to fix:\n"
                "   • Increase timeout: Use timeout parameter (max 120 seconds)\n"
                "   • Check URL is accessible in browser\n"
                "   • Try again later if server is overloaded"
            )
        except httpx.HTTPStatusError as e:
            status_code = e.response.status_code
            if status_code == 404:
                return f"HTTP 404: Page not found at {url}"
            elif status_code >= 500:
                return f"HTTP {status_code}: Server error at {url}. The target server may be experiencing issues."
            else:
                return f"HTTP {status_code}: Failed to fetch {url}"
        except RuntimeError as e:
            error_msg = str(e)
            if "not yet implemented" in error_msg:
                return error_msg
            # Crawl4AI errors
            return f"Crawl4AI error: {error_msg}"
        except Exception as e:
            logger.error(f"Unexpected error in fetch_webpage: {e}", exc_info=True)
            return f"Failed to convert web page: {str(e)}"

    @mcp.tool()
    async def fetch_webpage_with_selector(
        url: str,
        css_selector: Optional[str] = None,
        xpath: Optional[str] = None,
        include_images: bool = True,
        extract_links: bool = False,
        session_id: Optional[str] = None,
        bypass_cache: bool = False,
        timeout: int = 30,
        output_file: Optional[str] = None,
    ) -> str:
        """
        Extract specific content from webpage using CSS or XPath selectors.

        Extends basic webpage conversion with targeted content extraction. Use CSS selectors
        (e.g., "article.main", "div#content") or XPath expressions to extract specific sections.
        Optionally extract and categorize all links. Supports session-based crawling for
        authenticated content. Requires Crawl4AI Docker container.

        Args:
            url: The full HTTP/HTTPS URL of the web page to convert
            css_selector: CSS selector to extract specific content (e.g., "article.main", "div.content")
            xpath: XPath expression to extract content (alternative to css_selector, cannot use both)
            include_images: Include image alt text and references in markdown output (default: True)
            extract_links: Extract and categorize links as internal/external (default: False)
            session_id: Session ID for authenticated crawling (loads saved cookies/localStorage)
            bypass_cache: Bypass Crawl4AI cache for fresh content (default: False)
            timeout: Request timeout in seconds (default: 30, max: 120)
            output_file: Optional absolute path to save markdown file (includes frontmatter)

        Returns:
            Markdown text with YAML frontmatter if output_file not provided,
            or success message with file path if output_file provided.

            If extract_links=True, metadata includes:
            - all_links: All extracted links with text
            - internal_links: Same-domain links
            - external_links: Different-domain links
            - Link counts for each category

        Examples:
            Extract main article content:
            "Extract the article from https://example.com/post using CSS selector 'article.main'"

            Extract documentation content:
            "Get content from https://docs.example.com using selector 'div.content'"

            Extract with links:
            "Extract content from https://blog.example.com with selector '.post' and extract all links"
        """
        try:
            # Validate timeout
            if timeout < MIN_TIMEOUT or timeout > MAX_TIMEOUT:
                return f"Error: timeout must be between {MIN_TIMEOUT} and {MAX_TIMEOUT} seconds"

            # Validate selector combination
            if css_selector and xpath:
                return "Error: Cannot specify both css_selector and xpath. Choose one."

            # Convert to markdown
            markdown, metadata = await convert_webpage_with_selector(
                url=url,
                css_selector=css_selector,
                xpath=xpath,
                include_images=include_images,
                extract_links=extract_links,
                session_id=session_id,
                bypass_cache=bypass_cache,
                timeout=timeout,
            )

            # Handle output
            if output_file:
                error = validate_output_path(output_file)
                if error:
                    return f"Error: {error}"

                success = await save_markdown_file(output_file, markdown)
                if success:
                    # Add link summary if links were extracted
                    if extract_links and metadata.get("links"):
                        links_info = metadata["links"]
                        return (
                            f"Web page with selector saved to: {output_file}\n"
                            f"Extracted {links_info['total_count']} links "
                            f"({links_info['internal_count']} internal, {links_info['external_count']} external)"
                        )
                    return f"Web page with selector saved to: {output_file}"
                else:
                    return f"Failed to write file: Permission denied for {output_file}"
            else:
                # Add link summary if links were extracted
                result = markdown
                if extract_links and metadata.get("links"):
                    links_info = metadata["links"]
                    link_summary = (
                        f"\n\n---\n\n**Links Extracted**: {links_info['total_count']} total "
                        f"({links_info['internal_count']} internal, {links_info['external_count']} external)"
                    )
                    result += link_summary
                return result

        except ValueError as e:
            # Validation errors
            return str(e)
        except httpx.ConnectError:
            return (
                "❌ Crawl4AI service unavailable.\n\n"
                "What went wrong:\n"
                "   The Crawl4AI Docker container is not running or not reachable.\n\n"
                "Why this happened:\n"
                "   • Docker services may not be started\n"
                "   • Container crashed or failed to start\n"
                "   • Port 11235 is blocked or in use\n\n"
                "How to fix:\n"
                "   1. Start services: `make start-docker`\n"
                "   2. Check status: `make status`\n"
                "   3. View logs: `make logs`\n\n"
                "Note: YouTube transcription still works without Docker!"
            )
        except httpx.TimeoutException:
            return (
                f"Failed to fetch URL: Connection timeout after {timeout} seconds. "
                "The target server may be slow or the URL may be inaccessible. "
                "To increase timeout, use the timeout parameter (maximum 120 seconds)."
            )
        except httpx.HTTPStatusError as e:
            status_code = e.response.status_code
            if status_code == 404:
                return f"HTTP 404: Page not found at {url}"
            elif status_code >= 500:
                return f"HTTP {status_code}: Server error at {url}. The target server may be experiencing issues."
            else:
                return f"HTTP {status_code}: Failed to fetch {url}"
        except RuntimeError as e:
            error_msg = str(e)
            if "not yet implemented" in error_msg:
                return error_msg
            # Crawl4AI errors
            return f"Crawl4AI error: {error_msg}"
        except Exception as e:
            logger.error(f"Unexpected error in fetch_webpage_with_selector: {e}", exc_info=True)
            return f"Failed to convert web page with selector: {str(e)}"

    @mcp.tool()
    async def convert_document(
        file_path: str,
        enable_ocr: bool = True,
        output_file: Optional[str] = None,
    ) -> str:
        """
        Convert document files (PDF, DOCX, PPTX, XLSX) to clean markdown format.

        Preserves structure including tables, headings, lists, and code blocks. Supports
        OCR for scanned documents. Requires Docling Docker container.

        Args:
            file_path: Absolute path to the document file to convert
            enable_ocr: Enable OCR for scanned documents (slower but handles image-based PDFs, default: True)
            output_file: Optional absolute path to save markdown file (includes frontmatter)

        Returns:
            Markdown text with YAML frontmatter if output_file not provided,
            or success message with file path if output_file provided
        """
        try:
            # Get infrastructure dependencies
            config = get_config()
            service_url = config.get_service_url("docling")
            metrics_callback = get_metrics_callback()

            # Convert to markdown
            markdown, metadata = await convert_document_to_markdown(
                file_path=file_path,
                enable_ocr=enable_ocr,
                service_url=service_url,
                metrics_callback=metrics_callback,
            )

            # Handle output
            if output_file:
                error = validate_output_path(output_file)
                if error:
                    return f"Error: {error}"

                success = await save_markdown_file(output_file, markdown)
                if success:
                    return f"Document saved to: {output_file}"
                else:
                    return f"Failed to write file: Permission denied for {output_file}"
            else:
                return markdown

        except ValueError as e:
            # File validation errors
            return str(e)
        except RuntimeError as e:
            # Service unavailable or not implemented
            if "not yet implemented" in str(e):
                return str(e)
            return (
                "❌ Docling service unavailable.\n\n"
                "What went wrong:\n"
                "   The Docling Docker container is not running or not reachable.\n\n"
                "Why this happened:\n"
                "   • Docker services may not be started\n"
                "   • Container crashed or failed to start\n"
                "   • Port 5001 is blocked or in use\n\n"
                "How to fix:\n"
                "   1. Start services: `make start-docker`\n"
                "   2. Check status: `make status`\n"
                "   3. View logs: `docker logs gobbler-docling`\n\n"
                "Note: This only affects document conversion (PDF, DOCX, etc.)"
            )
        except Exception as e:
            logger.error(f"Unexpected error in convert_document: {e}", exc_info=True)
            return f"Failed to convert document: {str(e)}"

    async def _transcribe_audio_task(
        file_path: str,
        model: str = "small",
        language: str = "auto",
        output_file: Optional[str] = None,
    ) -> str:
        """Internal transcription function for both sync and queue execution."""
        # Convert to markdown
        markdown, metadata = await convert_audio_to_markdown(
            file_path=file_path,
            model=model,
            language=language,
        )

        # Handle output
        if output_file:
            error = validate_output_path(output_file)
            if error:
                return f"Error: {error}"

            success = await save_markdown_file(output_file, markdown)
            if success:
                return f"Transcript saved to: {output_file}"
            else:
                return f"Failed to write file: Permission denied for {output_file}"
        else:
            return markdown

    @mcp.tool()
    async def transcribe_audio(
        file_path: str,
        model: str = "small",
        language: str = "auto",
        output_file: Optional[str] = None,
    ) -> str:
        """
        Transcribe audio and video files to text using OpenAI Whisper.

        Supports multiple audio/video formats with automatic format detection via ffmpeg.
        Configurable model size for speed/accuracy tradeoff. Uses faster-whisper with
        Metal/CoreML acceleration on M-series Macs for optimal performance.

        Args:
            file_path: Absolute path to the audio or video file to transcribe
            model: Whisper model size - larger = more accurate but slower (default: 'small', options: tiny, base, small, medium, large)
            language: Audio language code (ISO 639-1) or 'auto' for automatic detection (default: 'auto')
            output_file: Optional absolute path to save markdown file (includes frontmatter)

        Returns:
            Markdown text with YAML frontmatter if output_file not provided,
            or success message with file path if output_file provided.
        """
        try:
            from pathlib import Path

            # Validate file exists first
            if not Path(file_path).exists():
                return f"Error: File not found: {file_path}"

            # Execute transcription
            return await _transcribe_audio_task(file_path, model, language, output_file)

        except ValueError as e:
            # File validation errors
            return str(e)
        except RuntimeError as e:
            # Transcription errors
            return str(e)
        except Exception as e:
            logger.error(f"Unexpected error in transcribe_audio: {e}", exc_info=True)
            return f"Failed to transcribe audio: {str(e)}"
