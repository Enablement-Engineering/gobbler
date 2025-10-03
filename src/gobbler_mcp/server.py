"""Main MCP server implementation using FastMCP."""

import json
import logging
from contextlib import asynccontextmanager
from typing import Optional

import httpx
from fastmcp import FastMCP
from youtube_transcript_api import (
    NoTranscriptFound,
    TranscriptsDisabled,
    VideoUnavailable,
)

from .batch.file_batch import process_audio_batch, process_document_batch
from .batch.progress_tracker import ProgressTracker
from .batch.webpage_batch import process_webpage_batch
from .batch.youtube_batch import process_youtube_batch
from .config import get_config
from .converters import (
    convert_audio_to_markdown,
    convert_document_to_markdown,
    convert_webpage_to_markdown,
    convert_webpage_with_selector,
    convert_youtube_to_markdown,
)
from .utils import save_markdown_file, validate_output_path
from .utils.health import ServiceHealth
from .utils.queue import (
    estimate_task_duration,
    format_job_response,
    get_job_info,
    get_queue,
    list_jobs_in_queue,
    should_queue_task,
)

# Configure logging to stderr only (required for stdio transport)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler()],
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastMCP):  # type: ignore
    """
    Application lifespan manager.

    Handles initialization and cleanup of resources.
    """
    # Startup
    logger.info("Starting Gobbler MCP server...")
    config = get_config()
    logger.info(f"Configuration loaded from {config.config_path}")

    # Check service health at startup (don't fail if unavailable)
    async with ServiceHealth() as health:
        service_urls = {
            "Crawl4AI": config.get_service_url("crawl4ai"),
            "Docling": config.get_service_url("docling"),
            "Whisper": config.get_service_url("whisper"),
        }
        health_status = await health.check_all_services(service_urls)

        available = [name for name, status in health_status.items() if status]
        unavailable = [name for name, status in health_status.items() if not status]

        if available:
            logger.info(f"Available services: {', '.join(available)}")
        if unavailable:
            logger.warning(
                f"Unavailable services: {', '.join(unavailable)}. "
                "Some tools will not work until services are started."
            )

    logger.info("Gobbler MCP server started successfully")

    yield

    # Shutdown
    logger.info("Shutting down Gobbler MCP server...")


# Initialize FastMCP server
mcp = FastMCP("gobbler-mcp", lifespan=lifespan)


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
            if output_path.is_dir() or not output_file.endswith('.md'):
                # Get title from metadata and sanitize for filename
                title = metadata.get('title', f"video_{metadata['video_id']}")
                # Remove invalid filename characters
                safe_title = "".join(c for c in title if c.isalnum() or c in (' ', '-', '_')).strip()
                safe_title = safe_title.replace(' ', '_')

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
        return (
            "Video not found: The video may be private, deleted, or the URL is incorrect."
        )
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
        if timeout < 5 or timeout > 120:
            return "Error: timeout must be between 5 and 120 seconds"

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
            "Crawl4AI service unavailable. The service may not be running. "
            "Start with: docker-compose up -d crawl4ai"
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
        if timeout < 5 or timeout > 120:
            return "Error: timeout must be between 5 and 120 seconds"

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
            "Crawl4AI service unavailable. The service may not be running. "
            "Start with: docker-compose up -d crawl4ai"
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
async def create_crawl_session(
    session_id: str,
    cookies: Optional[str] = None,
    local_storage: Optional[str] = None,
    user_agent: Optional[str] = None,
) -> str:
    """
    Create reusable browser session for authenticated crawling.

    Browser sessions persist cookies and localStorage to disk, allowing authenticated
    content access across multiple crawl operations. Sessions are stored in
    ~/.config/gobbler/sessions/ and can be reused with fetch_webpage_with_selector
    and crawl_site tools.

    Args:
        session_id: Unique identifier for the session (alphanumeric, hyphens, underscores)
        cookies: JSON string containing list of cookie objects with name, value, domain, etc.
        local_storage: JSON string containing localStorage key-value pairs
        user_agent: Custom user agent string to use with this session

    Returns:
        Success message with session details and storage location

    Cookie Format:
        Each cookie should be a dict with these fields:
        - name (required): Cookie name
        - value (required): Cookie value
        - domain (required): Cookie domain
        - path (optional): Cookie path (default: "/")
        - secure (optional): HTTPS only (default: false)
        - httpOnly (optional): HTTP only flag (default: false)
        - sameSite (optional): SameSite policy ("Strict", "Lax", "None")

    Examples:
        Create session with cookies:
        cookies_json = '[{"name": "session_token", "value": "abc123", "domain": "example.com"}]'
        create_crawl_session("my-site", cookies=cookies_json)

        Create session with localStorage:
        storage_json = '{"user_id": "12345", "theme": "dark"}'
        create_crawl_session("my-app", local_storage=storage_json)

        Create session with custom user agent:
        create_crawl_session("my-bot", user_agent="MyBot/1.0 (+http://mysite.com/bot)")

        Use session with selector tool:
        fetch_webpage_with_selector(
            url="https://example.com/dashboard",
            css_selector="div.user-data",
            session_id="my-site"
        )
    """
    try:
        from .crawlers.session_manager import SessionManager

        # Parse JSON inputs
        cookies_list = None
        if cookies:
            try:
                cookies_list = json.loads(cookies)
                if not isinstance(cookies_list, list):
                    return "Error: cookies must be a JSON array of cookie objects"
            except json.JSONDecodeError as e:
                return f"Error: Invalid cookies JSON: {e}"

        local_storage_dict = None
        if local_storage:
            try:
                local_storage_dict = json.loads(local_storage)
                if not isinstance(local_storage_dict, dict):
                    return "Error: local_storage must be a JSON object"
            except json.JSONDecodeError as e:
                return f"Error: Invalid local_storage JSON: {e}"

        # Validate session_id
        if not session_id.replace("-", "").replace("_", "").isalnum():
            return "Error: session_id must contain only alphanumeric characters, hyphens, and underscores"

        # Create session
        session_manager = SessionManager()
        result = await session_manager.create_session(
            session_id=session_id,
            cookies=cookies_list,
            local_storage=local_storage_dict,
            user_agent=user_agent,
        )

        # Format response
        response_parts = [
            f"✅ Session '{session_id}' created successfully",
            f"Storage location: {result['file_path']}",
            f"Cookies: {result['cookie_count']}",
        ]

        if result["local_storage_keys"]:
            response_parts.append(
                f"localStorage keys: {', '.join(result['local_storage_keys'])}"
            )

        if result["has_user_agent"]:
            response_parts.append("Custom user agent: configured")

        response_parts.append(
            f"\nUse with session_id='{session_id}' in fetch_webpage_with_selector or crawl_site"
        )

        return "\n".join(response_parts)

    except Exception as e:
        logger.error(f"Failed to create session: {e}", exc_info=True)
        return f"Failed to create session: {str(e)}"


@mcp.tool()
async def crawl_site(
    start_url: str,
    max_depth: int = 2,
    max_pages: int = 50,
    url_include_pattern: Optional[str] = None,
    url_exclude_pattern: Optional[str] = None,
    css_selector: Optional[str] = None,
    respect_robots_txt: bool = True,
    crawl_delay: float = 1.0,
    concurrency: int = 3,
    session_id: Optional[str] = None,
    output_dir: Optional[str] = None,
) -> str:
    """
    Recursively crawl website and extract content with link graph generation.

    Performs breadth-first crawl of a website, extracting content from each page and
    building a link graph showing relationships between pages. Supports depth control,
    URL pattern filtering, robots.txt respect, and polite crawling with delays.

    Args:
        start_url: URL to start crawling from
        max_depth: Maximum crawl depth (default: 2, max: 5)
        max_pages: Maximum pages to crawl (default: 50, max: 500)
        url_include_pattern: Regex pattern - only crawl URLs matching this
        url_exclude_pattern: Regex pattern - skip URLs matching this
        css_selector: Apply CSS selector to extract specific content from all pages
        respect_robots_txt: Respect robots.txt rules (default: True)
        crawl_delay: Delay between requests in seconds (default: 1.0, polite crawling)
        concurrency: Max concurrent requests (default: 3, max: 10)
        session_id: Session ID for authenticated crawling
        output_dir: Optional directory to save all crawled pages as markdown files

    Returns:
        Crawl summary with statistics and link graph visualization

    Examples:
        Basic documentation site crawl:
        crawl_site("https://docs.example.com", max_depth=2, max_pages=20)

        Crawl with URL filtering:
        crawl_site(
            "https://blog.example.com",
            url_include_pattern=r"/posts/",
            url_exclude_pattern=r"/(tag|category)/",
            max_pages=100
        )

        Authenticated crawl with selector:
        crawl_site(
            "https://app.example.com",
            css_selector="article.content",
            session_id="my-session",
            max_depth=3
        )

        Save all pages to directory:
        crawl_site(
            "https://docs.example.com",
            output_dir="/Users/me/crawled-docs",
            max_pages=50
        )
    """
    try:
        from .crawlers.site_crawler import SiteCrawler

        # Validate output_dir if provided
        if output_dir:
            error = validate_output_path(output_dir + "/dummy.md")  # Validate parent dir
            if error and "must end with .md" not in error:
                return f"Error: {error}"

        # Create crawler and run
        crawler = SiteCrawler()
        pages, summary = await crawler.crawl_site(
            start_url=start_url,
            max_depth=max_depth,
            max_pages=max_pages,
            url_include_pattern=url_include_pattern,
            url_exclude_pattern=url_exclude_pattern,
            css_selector=css_selector,
            respect_robots_txt=respect_robots_txt,
            crawl_delay=crawl_delay,
            concurrency=concurrency,
            session_id=session_id,
        )

        # Save pages to output_dir if specified
        if output_dir:
            import os
            from pathlib import Path

            output_path = Path(output_dir)
            output_path.mkdir(parents=True, exist_ok=True)

            for i, page in enumerate(pages):
                # Create safe filename from URL
                url_path = page["url"].replace("https://", "").replace("http://", "")
                safe_name = "".join(c if c.isalnum() or c in ("-", "_") else "_" for c in url_path)
                safe_name = safe_name[:100]  # Limit length

                file_path = output_path / f"{i:03d}_{safe_name}.md"
                success = await save_markdown_file(str(file_path), page["markdown"])

                if not success:
                    logger.warning(f"Failed to save page: {page['url']}")

        # Format response
        link_graph = summary["link_graph"]
        response_parts = [
            f"✅ Crawl complete: {summary['total_pages']} pages crawled",
            f"Duration: {summary['duration_ms']}ms",
            f"Max depth reached: {summary['max_depth_reached']}",
            f"Domains: {', '.join(summary['domains'])}",
            "",
            "**Link Graph Summary:**",
            f"Total nodes: {len(link_graph)}",
            f"Total edges: {sum(len(links) for links in link_graph.values())}",
        ]

        # Show top linked pages
        page_incoming = {}
        for source, targets in link_graph.items():
            for target in targets:
                page_incoming[target] = page_incoming.get(target, 0) + 1

        if page_incoming:
            top_pages = sorted(page_incoming.items(), key=lambda x: x[1], reverse=True)[:5]
            response_parts.append("\n**Most linked pages:**")
            for url, count in top_pages:
                # Shorten URL for display
                display_url = url if len(url) < 80 else url[:77] + "..."
                response_parts.append(f"- {display_url} ({count} incoming links)")

        if output_dir:
            response_parts.append(f"\n📁 Pages saved to: {output_dir}")

        return "\n".join(response_parts)

    except Exception as e:
        logger.error(f"Failed to crawl site: {e}", exc_info=True)
        return f"Failed to crawl site: {str(e)}"


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
        # Convert to markdown
        markdown, metadata = await convert_document_to_markdown(
            file_path=file_path,
            enable_ocr=enable_ocr,
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
        return f"Docling service unavailable. The service may not be running. Start with: docker-compose up -d docling"
    except Exception as e:
        logger.error(f"Unexpected error in convert_document: {e}", exc_info=True)
        return f"Failed to convert document: {str(e)}"


def _download_youtube_video_task(
    video_url: str,
    output_dir: str,
    quality: str = "best",
    format: str = "mp4",
) -> str:
    """Internal download function for both sync and queue execution."""
    import yt_dlp
    from pathlib import Path

    # Validate output directory
    output_path = Path(output_dir)
    if not output_path.is_absolute():
        return f"Error: output_dir must be an absolute path. Got: {output_dir}"

    # Create directory if it doesn't exist
    output_path.mkdir(parents=True, exist_ok=True)

    # Get video info first to get title
    ydl_opts_info = {
        'quiet': True,
        'no_warnings': True,
    }

    with yt_dlp.YoutubeDL(ydl_opts_info) as ydl:
        info = ydl.extract_info(video_url, download=False)
        title = info.get('title', 'video')
        # Sanitize title for filename
        safe_title = "".join(c for c in title if c.isalnum() or c in (' ', '-', '_')).strip()
        safe_title = safe_title.replace(' ', '_')

    # Configure download options
    quality_format = {
        'best': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',
        '1080p': 'bestvideo[height<=1080][ext=mp4]+bestaudio[ext=m4a]/best[height<=1080][ext=mp4]/best',
        '720p': 'bestvideo[height<=720][ext=mp4]+bestaudio[ext=m4a]/best[height<=720][ext=mp4]/best',
        '480p': 'bestvideo[height<=480][ext=mp4]+bestaudio[ext=m4a]/best[height<=480][ext=mp4]/best',
        '360p': 'bestvideo[height<=360][ext=mp4]+bestaudio[ext=m4a]/best[height<=360][ext=mp4]/best',
    }

    selected_format = quality_format.get(quality, quality_format['best'])

    ydl_opts = {
        'format': selected_format,
        'outtmpl': str(output_path / f'{safe_title}.%(ext)s'),
        'merge_output_format': format,
        'quiet': False,
        'no_warnings': False,
    }

    # Download video
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        ydl.download([video_url])

    # Find the downloaded file
    output_file = output_path / f'{safe_title}.{format}'
    if output_file.exists():
        file_size_mb = output_file.stat().st_size / 1024 / 1024
        return f"Video downloaded successfully to: {output_file}\nFile size: {file_size_mb:.1f} MB"
    else:
        return f"Download completed but file not found at expected location: {output_file}"


@mcp.tool()
async def download_youtube_video(
    video_url: str,
    output_dir: str,
    quality: str = "best",
    format: str = "mp4",
    auto_queue: bool = False,
) -> str:
    """
    Download YouTube video to local file.

    Downloads video using yt-dlp with configurable quality and format.
    Automatically sanitizes filenames and creates output directory if needed.

    Args:
        video_url: YouTube video URL (youtube.com/watch?v=ID or youtu.be/ID format)
        output_dir: Directory to save the downloaded video (must be absolute path)
        quality: Video quality - 'best', '1080p', '720p', '480p', '360p' (default: 'best')
        format: Output format - 'mp4', 'webm', 'mkv' (default: 'mp4')
        auto_queue: Automatically queue task if estimated duration > 1:45 (default: False)

    Returns:
        Success message with path to downloaded file.
        If queued: Returns job_id and estimated completion time.
    """
    try:
        # Check if should queue
        if should_queue_task("download_youtube", auto_queue, quality=quality):
            # Queue the task
            queue = get_queue("download")
            job = queue.enqueue(
                _download_youtube_video_task,
                video_url=video_url,
                output_dir=output_dir,
                quality=quality,
                format=format,
                job_timeout="20m",
            )
            return format_job_response(job, "download_youtube", quality=quality)

        # Execute synchronously (run in thread to avoid blocking)
        import asyncio
        return await asyncio.to_thread(_download_youtube_video_task, video_url, output_dir, quality, format)

    except Exception as e:
        logger.error(f"Unexpected error in download_youtube_video: {e}", exc_info=True)
        return f"Failed to download video: {str(e)}"


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
    auto_queue: bool = False,
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
        auto_queue: Automatically queue task if estimated duration > 1:45 (default: False)

    Returns:
        Markdown text with YAML frontmatter if output_file not provided,
        or success message with file path if output_file provided.
        If queued: Returns job_id and estimated completion time.
    """
    try:
        import os
        from pathlib import Path

        # Validate file exists first
        if not Path(file_path).exists():
            return f"Error: File not found: {file_path}"

        # Get file size for queue estimation
        file_size_mb = os.path.getsize(file_path) / 1024 / 1024

        # Check if should queue
        if should_queue_task("transcribe_audio", auto_queue, file_size_mb=file_size_mb):
            # Queue the task
            queue = get_queue("transcription")
            job = queue.enqueue(
                _transcribe_audio_task,
                file_path=file_path,
                model=model,
                language=language,
                output_file=output_file,
                job_timeout="30m",
            )
            return format_job_response(job, "transcribe_audio", file_size_mb=file_size_mb)

        # Execute synchronously
        return await _transcribe_audio_task(file_path, model, language, output_file)

    except ValueError as e:
        # File validation errors
        return str(e)
    except RuntimeError as e:
        # Service unavailable or not implemented
        if "not yet implemented" in str(e):
            return str(e)
        return f"Whisper service unavailable. The service may not be running. Start with: docker-compose up -d whisper"
    except Exception as e:
        logger.error(f"Unexpected error in transcribe_audio: {e}", exc_info=True)
        return f"Failed to transcribe audio: {str(e)}"


@mcp.tool()
async def get_job_status(job_id: str) -> str:
    """
    Check status and result of a queued job.

    Retrieves current status, progress, and result (if completed) for a job
    that was queued via auto_queue flag.

    Args:
        job_id: Job ID returned when task was queued

    Returns:
        Job status information including:
        - Current status (queued/started/finished/failed)
        - Progress information
        - Result (if completed)
        - Error message (if failed)
    """
    try:
        job_info = get_job_info(job_id)
        if job_info is None:
            return f"Job not found: {job_id}"

        # Format response based on status
        status = job_info["status"]
        result = [f"Job ID: {job_id}", f"Status: {status}"]

        if status == "queued":
            position = job_info.get("queue_position", "unknown")
            result.append(f"Queue position: {position}")
            result.append("Waiting to start...")

        elif status == "started":
            result.append("Job is currently running...")
            if job_info.get("progress"):
                result.append(f"Progress: {job_info['progress']}")

        elif status == "finished":
            result.append("✅ Job completed successfully")
            if job_info.get("result"):
                result.append(f"\nResult:\n{job_info['result']}")

        elif status == "failed":
            result.append("❌ Job failed")
            if job_info.get("error"):
                result.append(f"Error: {job_info['error']}")

        return "\n".join(result)

    except Exception as e:
        logger.error(f"Error getting job status: {e}", exc_info=True)
        return f"Failed to get job status: {str(e)}"


@mcp.tool()
async def list_jobs(queue_name: str = "default", limit: int = 20) -> str:
    """
    List jobs in a queue.

    Shows recent jobs in the specified queue with their current status.
    Useful for monitoring background tasks.

    Args:
        queue_name: Queue to list jobs from (default: 'default', options: 'transcription', 'download')
        limit: Maximum number of jobs to return (default: 20, max: 100)

    Returns:
        List of jobs with status, ID, and created time
    """
    try:
        if limit > 100:
            limit = 100

        jobs = list_jobs_in_queue(queue_name, limit)

        if not jobs:
            return f"No jobs found in queue '{queue_name}'"

        result = [f"Jobs in queue '{queue_name}' (showing up to {limit}):\n"]

        for job_data in jobs:
            status_icon = {
                "queued": "⏳",
                "started": "🔄",
                "finished": "✅",
                "failed": "❌",
            }.get(job_data["status"], "❓")

            result.append(
                f"{status_icon} {job_data['status'].upper()}: {job_data['id']}"
            )
            result.append(f"   Created: {job_data['created_at']}")

            if job_data["status"] == "queued" and job_data.get("queue_position"):
                result.append(f"   Position: {job_data['queue_position']}")

            result.append("")

        return "\n".join(result)

    except Exception as e:
        logger.error(f"Error listing jobs: {e}", exc_info=True)
        return f"Failed to list jobs: {str(e)}"


# ===== Batch Processing Tools =====


def _batch_transcribe_youtube_playlist_task(
    playlist_url: str,
    output_dir: str,
    include_timestamps: bool = False,
    language: str = "auto",
    max_videos: int = 100,
    concurrency: int = 3,
    skip_existing: bool = True,
) -> str:
    """Internal task for batch YouTube playlist processing."""
    import asyncio

    # Run async batch processing
    summary = asyncio.run(
        process_youtube_batch(
            playlist_url=playlist_url,
            output_dir=output_dir,
            include_timestamps=include_timestamps,
            language=language,
            max_videos=max_videos,
            concurrency=concurrency,
            skip_existing=skip_existing,
        )
    )

    return summary.format_report()


@mcp.tool()
async def batch_transcribe_youtube_playlist(
    playlist_url: str,
    output_dir: str,
    include_timestamps: bool = False,
    language: str = "auto",
    max_videos: int = 100,
    concurrency: int = 3,
    skip_existing: bool = True,
    auto_queue: bool = False,
) -> str:
    """
    Extract transcripts from all videos in a YouTube playlist.

    Processes videos with controlled concurrency to avoid rate limiting.
    Automatically sanitizes filenames and creates output directory structure.
    All results are saved to the output directory.

    Args:
        playlist_url: YouTube playlist URL (youtube.com/playlist?list=...)
        output_dir: Directory to save markdown transcripts (must be absolute path)
        include_timestamps: Include timestamp markers in transcripts (default: False)
        language: Transcript language code or 'auto' (default: 'auto')
        max_videos: Maximum number of videos to process (default: 100, max: 500)
        concurrency: Number of videos to process concurrently (default: 3, max: 10)
        skip_existing: Skip videos that already have output files (default: True)
        auto_queue: Queue batch if >10 videos (default: False)

    Returns:
        Batch summary report with statistics and file list
    """
    try:
        from pathlib import Path

        # Validate output directory
        output_path = Path(output_dir)
        if not output_path.is_absolute():
            return f"Error: output_dir must be an absolute path. Got: {output_dir}"

        # Get video count for queueing decision
        from .batch.youtube_batch import get_playlist_videos

        try:
            videos = await get_playlist_videos(playlist_url, max_videos)
            video_count = len(videos)
        except ValueError as e:
            return str(e)

        # Check if should queue (>10 videos and auto_queue enabled)
        if auto_queue and video_count > 10:
            queue = get_queue("default")
            job = queue.enqueue(
                _batch_transcribe_youtube_playlist_task,
                playlist_url=playlist_url,
                output_dir=output_dir,
                include_timestamps=include_timestamps,
                language=language,
                max_videos=max_videos,
                concurrency=concurrency,
                skip_existing=skip_existing,
                job_timeout="2h",
            )

            estimated_minutes = video_count * 2  # Rough estimate: 2 min per video
            return (
                f"Batch queued successfully!\n\n"
                f"Playlist: {video_count} videos found\n"
                f"Job ID: {job.id}\n"
                f"Queue: {job.origin}\n"
                f"Estimated completion: ~{estimated_minutes} minutes\n\n"
                f"Check status with: get_job_status(job_id=\"{job.id}\")\n"
                f"Or list all jobs with: list_jobs()"
            )

        # Execute synchronously
        summary = await process_youtube_batch(
            playlist_url=playlist_url,
            output_dir=output_dir,
            include_timestamps=include_timestamps,
            language=language,
            max_videos=max_videos,
            concurrency=concurrency,
            skip_existing=skip_existing,
        )

        return summary.format_report()

    except ValueError as e:
        return str(e)
    except Exception as e:
        logger.error(f"Unexpected error in batch_transcribe_youtube_playlist: {e}", exc_info=True)
        return f"Failed to process playlist: {str(e)}"


def _batch_fetch_webpages_task(
    urls: list,
    output_dir: str,
    include_images: bool = True,
    timeout: int = 30,
    concurrency: int = 5,
    skip_existing: bool = True,
) -> str:
    """Internal task for batch webpage processing."""
    import asyncio

    summary = asyncio.run(
        process_webpage_batch(
            urls=urls,
            output_dir=output_dir,
            include_images=include_images,
            timeout=timeout,
            concurrency=concurrency,
            skip_existing=skip_existing,
        )
    )

    return summary.format_report()


@mcp.tool()
async def batch_fetch_webpages(
    urls: list[str],
    output_dir: str,
    include_images: bool = True,
    timeout: int = 30,
    concurrency: int = 5,
    skip_existing: bool = True,
    auto_queue: bool = False,
) -> str:
    """
    Convert multiple web pages to markdown format.

    Processes URLs with controlled concurrency to avoid overwhelming target servers.
    Automatically generates filenames from page titles or URLs.
    All results are saved to the output directory.

    Args:
        urls: List of web page URLs to convert (max: 100 URLs per batch)
        output_dir: Directory to save markdown files (must be absolute path)
        include_images: Include image references in markdown (default: True)
        timeout: Request timeout per page in seconds (default: 30, max: 120)
        concurrency: Number of pages to process concurrently (default: 5, max: 10)
        skip_existing: Skip URLs that already have output files (default: True)
        auto_queue: Queue batch if >10 URLs (default: False)

    Returns:
        Batch summary report with statistics and file list
    """
    try:
        from pathlib import Path

        # Validate parameters
        if not urls:
            return "Error: urls list cannot be empty"

        if len(urls) > 100:
            return "Error: Maximum 100 URLs per batch. Please split into smaller batches."

        if timeout < 5 or timeout > 120:
            return "Error: timeout must be between 5 and 120 seconds"

        if concurrency < 1 or concurrency > 10:
            return "Error: concurrency must be between 1 and 10"

        # Validate output directory
        output_path = Path(output_dir)
        if not output_path.is_absolute():
            return f"Error: output_dir must be an absolute path. Got: {output_dir}"

        # Check if should queue
        if auto_queue and len(urls) > 10:
            queue = get_queue("default")
            job = queue.enqueue(
                _batch_fetch_webpages_task,
                urls=urls,
                output_dir=output_dir,
                include_images=include_images,
                timeout=timeout,
                concurrency=concurrency,
                skip_existing=skip_existing,
                job_timeout="2h",
            )

            estimated_minutes = len(urls) * 1  # Rough estimate: 1 min per URL
            return (
                f"Batch queued successfully!\n\n"
                f"URLs: {len(urls)} pages\n"
                f"Job ID: {job.id}\n"
                f"Queue: {job.origin}\n"
                f"Estimated completion: ~{estimated_minutes} minutes\n\n"
                f"Check status with: get_job_status(job_id=\"{job.id}\")\n"
                f"Or list all jobs with: list_jobs()"
            )

        # Execute synchronously
        summary = await process_webpage_batch(
            urls=urls,
            output_dir=output_dir,
            include_images=include_images,
            timeout=timeout,
            concurrency=concurrency,
            skip_existing=skip_existing,
        )

        return summary.format_report()

    except Exception as e:
        logger.error(f"Unexpected error in batch_fetch_webpages: {e}", exc_info=True)
        return f"Failed to process webpages: {str(e)}"


def _batch_transcribe_directory_task(
    input_dir: str,
    output_dir: str = None,
    model: str = "small",
    language: str = "auto",
    pattern: str = "*",
    recursive: bool = False,
    concurrency: int = 2,
    skip_existing: bool = True,
) -> str:
    """Internal task for batch directory transcription."""
    import asyncio

    summary = asyncio.run(
        process_audio_batch(
            input_dir=input_dir,
            output_dir=output_dir,
            model=model,
            language=language,
            pattern=pattern,
            recursive=recursive,
            concurrency=concurrency,
            skip_existing=skip_existing,
        )
    )

    return summary.format_report()


@mcp.tool()
async def batch_transcribe_directory(
    input_dir: str,
    output_dir: Optional[str] = None,
    model: str = "small",
    language: str = "auto",
    pattern: str = "*",
    recursive: bool = False,
    concurrency: int = 2,
    skip_existing: bool = True,
    auto_queue: bool = False,
) -> str:
    """
    Transcribe all audio/video files in a directory.

    Automatically detects supported file formats and processes them with Whisper.
    Supported formats: mp3, mp4, wav, m4a, mov, avi, mkv, flac, ogg, webm.
    All results are saved to the output directory.

    Args:
        input_dir: Directory containing audio/video files (must be absolute path)
        output_dir: Directory for transcripts (default: same as input_dir)
        model: Whisper model size (default: 'small', options: tiny, base, small, medium, large)
        language: Audio language code or 'auto' (default: 'auto')
        pattern: Glob pattern for file matching (default: '*' for all supported formats)
        recursive: Search subdirectories (default: False)
        concurrency: Number of files to process concurrently (default: 2, max: 4)
        skip_existing: Skip files with existing transcript files (default: True)
        auto_queue: Queue batch if >10 files (default: False)

    Returns:
        Batch summary report with statistics and file list
    """
    try:
        from pathlib import Path

        # Validate input directory
        input_path = Path(input_dir)
        if not input_path.is_absolute():
            return f"Error: input_dir must be an absolute path. Got: {input_dir}"

        if not input_path.exists():
            return f"Error: Directory not found: {input_dir}"

        if not input_path.is_dir():
            return f"Error: Not a directory: {input_dir}"

        # Validate concurrency
        if concurrency < 1 or concurrency > 4:
            return "Error: concurrency must be between 1 and 4"

        # Count files for queueing decision
        from .batch.file_batch import scan_directory

        try:
            files = scan_directory(input_dir, pattern, recursive, file_type="audio")
            file_count = len(files)
        except ValueError as e:
            return str(e)

        # Check if should queue
        if auto_queue and file_count > 10:
            queue = get_queue("transcription")
            job = queue.enqueue(
                _batch_transcribe_directory_task,
                input_dir=input_dir,
                output_dir=output_dir,
                model=model,
                language=language,
                pattern=pattern,
                recursive=recursive,
                concurrency=concurrency,
                skip_existing=skip_existing,
                job_timeout="4h",
            )

            estimated_minutes = file_count * 5  # Rough estimate: 5 min per file
            return (
                f"Batch queued successfully!\n\n"
                f"Files found: {file_count} audio/video files\n"
                f"Job ID: {job.id}\n"
                f"Queue: {job.origin}\n"
                f"Estimated completion: ~{estimated_minutes} minutes\n\n"
                f"Check status with: get_job_status(job_id=\"{job.id}\")\n"
                f"Or list all jobs with: list_jobs()"
            )

        # Execute synchronously
        summary = await process_audio_batch(
            input_dir=input_dir,
            output_dir=output_dir,
            model=model,
            language=language,
            pattern=pattern,
            recursive=recursive,
            concurrency=concurrency,
            skip_existing=skip_existing,
        )

        return summary.format_report()

    except ValueError as e:
        return str(e)
    except Exception as e:
        logger.error(f"Unexpected error in batch_transcribe_directory: {e}", exc_info=True)
        return f"Failed to transcribe directory: {str(e)}"


def _batch_convert_documents_task(
    input_dir: str,
    output_dir: str = None,
    enable_ocr: bool = True,
    pattern: str = "*",
    recursive: bool = False,
    concurrency: int = 3,
    skip_existing: bool = True,
) -> str:
    """Internal task for batch document conversion."""
    import asyncio

    summary = asyncio.run(
        process_document_batch(
            input_dir=input_dir,
            output_dir=output_dir,
            enable_ocr=enable_ocr,
            pattern=pattern,
            recursive=recursive,
            concurrency=concurrency,
            skip_existing=skip_existing,
        )
    )

    return summary.format_report()


@mcp.tool()
async def batch_convert_documents(
    input_dir: str,
    output_dir: Optional[str] = None,
    enable_ocr: bool = True,
    pattern: str = "*",
    recursive: bool = False,
    concurrency: int = 3,
    skip_existing: bool = True,
    auto_queue: bool = False,
) -> str:
    """
    Convert all documents in a directory to markdown.

    Supports PDF, DOCX, PPTX, XLSX with optional OCR for scanned documents.
    All results are saved to the output directory.

    Args:
        input_dir: Directory containing documents (must be absolute path)
        output_dir: Directory for markdown files (default: same as input_dir)
        enable_ocr: Enable OCR for scanned documents (default: True)
        pattern: Glob pattern for file matching (default: '*' for all supported formats)
        recursive: Search subdirectories (default: False)
        concurrency: Number of documents to process concurrently (default: 3, max: 5)
        skip_existing: Skip documents with existing markdown files (default: True)
        auto_queue: Queue batch if >10 documents (default: False)

    Returns:
        Batch summary report with statistics and file list
    """
    try:
        from pathlib import Path

        # Validate input directory
        input_path = Path(input_dir)
        if not input_path.is_absolute():
            return f"Error: input_dir must be an absolute path. Got: {input_dir}"

        if not input_path.exists():
            return f"Error: Directory not found: {input_dir}"

        if not input_path.is_dir():
            return f"Error: Not a directory: {input_dir}"

        # Validate concurrency
        if concurrency < 1 or concurrency > 5:
            return "Error: concurrency must be between 1 and 5"

        # Count files for queueing decision
        from .batch.file_batch import scan_directory

        try:
            files = scan_directory(input_dir, pattern, recursive, file_type="document")
            file_count = len(files)
        except ValueError as e:
            return str(e)

        # Check if should queue
        if auto_queue and file_count > 10:
            queue = get_queue("default")
            job = queue.enqueue(
                _batch_convert_documents_task,
                input_dir=input_dir,
                output_dir=output_dir,
                enable_ocr=enable_ocr,
                pattern=pattern,
                recursive=recursive,
                concurrency=concurrency,
                skip_existing=skip_existing,
                job_timeout="3h",
            )

            estimated_minutes = file_count * 3  # Rough estimate: 3 min per document
            return (
                f"Batch queued successfully!\n\n"
                f"Documents found: {file_count} files\n"
                f"Job ID: {job.id}\n"
                f"Queue: {job.origin}\n"
                f"Estimated completion: ~{estimated_minutes} minutes\n\n"
                f"Check status with: get_job_status(job_id=\"{job.id}\")\n"
                f"Or list all jobs with: list_jobs()"
            )

        # Execute synchronously
        summary = await process_document_batch(
            input_dir=input_dir,
            output_dir=output_dir,
            enable_ocr=enable_ocr,
            pattern=pattern,
            recursive=recursive,
            concurrency=concurrency,
            skip_existing=skip_existing,
        )

        return summary.format_report()

    except ValueError as e:
        return str(e)
    except Exception as e:
        logger.error(f"Unexpected error in batch_convert_documents: {e}", exc_info=True)
        return f"Failed to convert documents: {str(e)}"


@mcp.tool()
async def get_batch_progress(batch_id: str) -> str:
    """
    Get real-time progress for a running batch operation.

    Provides detailed progress information including current item, success/failure
    counts, and any errors encountered.

    Args:
        batch_id: Batch operation ID returned when batch was started

    Returns:
        Progress report with:
        - Current status (running/completed/failed)
        - Items processed / total items
        - Success and failure counts
        - Current item being processed
        - Recent errors (if any)
    """
    try:
        tracker = ProgressTracker(batch_id)
        progress = await tracker.get_progress()

        if not progress:
            return f"Batch not found: {batch_id}\n\nBatch may have expired (24 hour retention) or ID is incorrect."

        return tracker.format_progress_report(progress)

    except Exception as e:
        logger.error(f"Error getting batch progress: {e}", exc_info=True)
        return f"Failed to get batch progress: {str(e)}"
