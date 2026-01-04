"""Thin CLI wrappers for MCP conversion tools.

These tools delegate to the gobbler CLI for actual implementation,
keeping the MCP server lightweight and avoiding code duplication.

Tools:
- transcribe_youtube: YouTube video transcript extraction via CLI
- fetch_webpage: Basic webpage to markdown conversion via CLI
- fetch_webpage_with_selector: Advanced webpage extraction (uses existing converter)
- convert_document: Document conversion via CLI
- transcribe_audio: Audio/video transcription via CLI
"""

import logging
import subprocess

import httpx
from fastmcp import FastMCP

from ..constants import MAX_TIMEOUT, MIN_TIMEOUT

# Import the selector converter directly since CLI doesn't fully support it yet
from ..converters import convert_webpage_with_selector
from ..utils import save_markdown_file, validate_output_path

logger = logging.getLogger(__name__)


def _run_cli(cmd: list[str], timeout: int = 300) -> tuple[bool, str]:
    """Run a CLI command and return success status and output.

    Args:
        cmd: Command list to execute
        timeout: Timeout in seconds (default: 5 minutes)

    Returns:
        Tuple of (success, output) where output is stdout on success or stderr on failure
    """
    try:
        # cmd is built from hardcoded "gobbler" binary with validated user arguments
        result = subprocess.run(  # nosec B603
            cmd,
            check=False,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        return False, f"Command timed out after {timeout} seconds"
    except FileNotFoundError:
        return False, "gobbler CLI not found. Ensure it's installed and in PATH."
    except Exception as e:
        return False, f"Failed to run command: {e!s}"
    else:
        if result.returncode != 0:
            return (
                False,
                result.stderr.strip() or f"Command failed with exit code {result.returncode}",
            )
        return True, result.stdout


def register_tools(mcp: FastMCP):  # noqa: C901, PLR0915
    """Register conversion tools with the MCP server."""

    @mcp.tool()
    async def transcribe_youtube(
        video_url: str,
        include_timestamps: bool = False,
        language: str = "auto",
        output_file: str | None = None,
    ) -> str:
        """Extract YouTube video transcript and convert to clean markdown format.

        Uses official YouTube transcript API for fast, accurate results. Works without
        Docker containers. Returns markdown with YAML frontmatter containing metadata
        about the video and transcript.

        Args:
            video_url: YouTube video URL (youtube.com/watch?v=ID or youtu.be/ID)
            include_timestamps: Include timestamp markers in transcript (default: False)
            language: Language code (ISO 639-1) or 'auto' for default (default: 'auto')
            output_file: Optional path to save markdown. If a directory, uses video title.

        Returns:
            Markdown text with YAML frontmatter if output_file not provided,
            or success message with file path if output_file provided
        """
        cmd = ["gobbler", "youtube", video_url]

        if include_timestamps:
            cmd.append("--timestamps")
        if language != "auto":
            cmd.extend(["--language", language])
        if output_file:
            cmd.extend(["-o", output_file])

        success, output = _run_cli(cmd)
        if not success:
            return f"Error: {output}"
        return output

    @mcp.tool()
    async def fetch_webpage(
        url: str,
        include_images: bool = True,
        timeout: int = 30,
        output_file: str | None = None,
    ) -> str:
        """Convert web page content to clean markdown format.

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
        # Validate timeout
        if timeout < MIN_TIMEOUT or timeout > MAX_TIMEOUT:
            return f"Error: timeout must be between {MIN_TIMEOUT} and {MAX_TIMEOUT} seconds"

        cmd = ["gobbler", "webpage", url]

        if not include_images:
            cmd.append("--no-images")
        cmd.extend(["--timeout", str(timeout)])
        if output_file:
            cmd.extend(["-o", output_file])

        success, output = _run_cli(cmd, timeout=timeout + 30)  # Extra buffer for CLI overhead
        if not success:
            return f"Error: {output}"
        return output

    @mcp.tool()
    async def fetch_webpage_with_selector(  # noqa: C901, PLR0911, PLR0912
        url: str,
        css_selector: str | None = None,
        xpath: str | None = None,
        include_images: bool = True,
        extract_links: bool = False,
        session_id: str | None = None,
        bypass_cache: bool = False,
        timeout: int = 30,
        output_file: str | None = None,
    ) -> str:
        """Extract specific content from webpage using CSS or XPath selectors.

        Extends basic webpage conversion with targeted content extraction. Use CSS selectors
        (e.g., "article.main", "div#content") or XPath expressions to extract specific sections.
        Optionally extract and categorize all links. Supports session-based crawling for
        authenticated content. Requires Crawl4AI Docker container.

        Args:
            url: The full HTTP/HTTPS URL of the web page to convert
            css_selector: CSS selector to extract content (e.g., "article.main")
            xpath: XPath expression to extract content (alternative to css_selector)
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
            "Extract content from https://blog.example.com with '.post' selector"
        """
        # Keep existing implementation since CLI doesn't fully support all options yet
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
                        int_count = links_info["internal_count"]
                        ext_count = links_info["external_count"]
                        return (
                            f"Web page with selector saved to: {output_file}\n"
                            f"Extracted {links_info['total_count']} links "
                            f"({int_count} internal, {ext_count} external)"
                        )
                    return f"Web page with selector saved to: {output_file}"
                return f"Failed to write file: Permission denied for {output_file}"
            # Add link summary if links were extracted
            result = markdown
            if extract_links and metadata.get("links"):
                links_info = metadata["links"]
                int_count = links_info["internal_count"]
                ext_count = links_info["external_count"]
                link_summary = (
                    f"\n\n---\n\n**Links Extracted**: {links_info['total_count']} total "
                    f"({int_count} internal, {ext_count} external)"
                )
                result += link_summary
            return result  # noqa: TRY300

        except ValueError as e:
            # Validation errors
            return str(e)
        except httpx.ConnectError:
            return (
                "Crawl4AI service unavailable.\n\n"
                "What went wrong:\n"
                "   The Crawl4AI Docker container is not running or not reachable.\n\n"
                "Why this happened:\n"
                "   - Docker services may not be started\n"
                "   - Container crashed or failed to start\n"
                "   - Port 11235 is blocked or in use\n\n"
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
            http_not_found = 404
            http_server_error = 500
            if status_code == http_not_found:
                return f"HTTP 404: Page not found at {url}"
            if status_code >= http_server_error:
                return (
                    f"HTTP {status_code}: Server error at {url}. "
                    "The target server may be experiencing issues."
                )
            return f"HTTP {status_code}: Failed to fetch {url}"
        except RuntimeError as e:
            error_msg = str(e)
            if "not yet implemented" in error_msg:
                return error_msg
            # Crawl4AI errors
            return f"Crawl4AI error: {error_msg}"
        except Exception as e:
            logger.exception("Unexpected error in fetch_webpage_with_selector")
            return f"Failed to convert web page with selector: {e!s}"

    @mcp.tool()
    async def convert_document(
        file_path: str,
        enable_ocr: bool = True,
        output_file: str | None = None,
    ) -> str:
        """Convert document files (PDF, DOCX, PPTX, XLSX) to clean markdown format.

        Preserves structure including tables, headings, lists, and code blocks. Supports
        OCR for scanned documents. Requires Docling Docker container.

        Args:
            file_path: Absolute path to the document file to convert
            enable_ocr: Enable OCR for scanned PDFs (slower, default: True)
            output_file: Optional path to save markdown file (includes frontmatter)

        Returns:
            Markdown text with YAML frontmatter if output_file not provided,
            or success message with file path if output_file provided
        """
        cmd = ["gobbler", "document", file_path]

        if enable_ocr:
            cmd.append("--ocr")
        else:
            cmd.append("--no-ocr")
        if output_file:
            cmd.extend(["-o", output_file])

        # Document conversion can be slow, especially with OCR
        success, output = _run_cli(cmd, timeout=600)
        if not success:
            return f"Error: {output}"
        return output

    @mcp.tool()
    async def transcribe_audio(
        file_path: str,
        model: str = "small",
        language: str = "auto",
        output_file: str | None = None,
    ) -> str:
        """Transcribe audio and video files to text using OpenAI Whisper.

        Supports multiple audio/video formats with automatic format detection via ffmpeg.
        Configurable model size for speed/accuracy tradeoff. Uses faster-whisper with
        Metal/CoreML acceleration on M-series Macs for optimal performance.

        Args:
            file_path: Absolute path to the audio or video file to transcribe
            model: Whisper model size (default: 'small', options: tiny/base/small/medium/large)
            language: Audio language code (ISO 639-1) or 'auto' (default: 'auto')
            output_file: Optional path to save markdown file (includes frontmatter)

        Returns:
            Markdown text with YAML frontmatter if output_file not provided,
            or success message with file path if output_file provided
        """
        cmd = ["gobbler", "audio", file_path]

        if model != "small":
            cmd.extend(["--model", model])
        if language != "auto":
            cmd.extend(["--language", language])
        if output_file:
            cmd.extend(["-o", output_file])

        # Audio transcription can take a long time depending on file size and model
        success, output = _run_cli(cmd, timeout=1800)  # 30 minute timeout
        if not success:
            return f"Error: {output}"
        return output
