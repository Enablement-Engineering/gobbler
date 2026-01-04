"""Web crawling and session management tools.

Tools for crawling websites and managing browser sessions:
- create_crawl_session: Create reusable browser sessions with cookies
- crawl_site: Recursively crawl websites with link graph generation
- download_youtube_video: Download YouTube videos to local files
"""

import json
import logging

from fastmcp import FastMCP

from ..utils import save_markdown_file, validate_output_path

logger = logging.getLogger(__name__)


def register_tools(mcp: FastMCP):  # noqa: C901, PLR0915
    """Register crawling and session tools with the MCP server."""

    @mcp.tool()
    async def create_crawl_session(  # noqa: PLR0911
        session_id: str,
        cookies: str | None = None,
        local_storage: str | None = None,
        user_agent: str | None = None,
    ) -> str:
        """Create reusable browser session for authenticated crawling.

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
            from ..crawlers.session_manager import SessionManager

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
                return (
                    "Error: session_id must contain only alphanumeric characters, "
                    "hyphens, and underscores"
                )

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
            logger.exception("Failed to create session")
            return f"Failed to create session: {e!s}"

    @mcp.tool()
    async def crawl_site(  # noqa: C901, PLR0912
        start_url: str,
        max_depth: int = 2,
        max_pages: int = 50,
        url_include_pattern: str | None = None,
        url_exclude_pattern: str | None = None,
        css_selector: str | None = None,
        respect_robots_txt: bool = True,
        crawl_delay: float = 1.0,
        concurrency: int = 3,
        session_id: str | None = None,
        output_dir: str | None = None,
    ) -> str:
        """Recursively crawl website and extract content with link graph generation.

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
            from ..crawlers.site_crawler import SiteCrawler

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
                from pathlib import Path

                output_path = Path(output_dir)
                output_path.mkdir(parents=True, exist_ok=True)

                for i, page in enumerate(pages):
                    # Create safe filename from URL
                    url_path = page["url"].replace("https://", "").replace("http://", "")
                    safe_name = "".join(
                        c if c.isalnum() or c in ("-", "_") else "_" for c in url_path
                    )
                    safe_name = safe_name[:100]  # Limit length

                    file_path = output_path / f"{i:03d}_{safe_name}.md"
                    success = await save_markdown_file(str(file_path), page["markdown"])

                    if not success:
                        logger.warning("Failed to save page: %s", page["url"])

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
            page_incoming: dict[str, int] = {}
            for _source, targets in link_graph.items():
                for target in targets:
                    page_incoming[target] = page_incoming.get(target, 0) + 1

            max_url_display_len = 80
            if page_incoming:
                top_pages = sorted(page_incoming.items(), key=lambda x: x[1], reverse=True)[:5]
                response_parts.append("\n**Most linked pages:**")
                for page_url, count in top_pages:
                    # Shorten URL for display
                    if len(page_url) < max_url_display_len:
                        display_url = page_url
                    else:
                        display_url = page_url[:77] + "..."
                    response_parts.append(f"- {display_url} ({count} incoming links)")

            if output_dir:
                response_parts.append(f"\n📁 Pages saved to: {output_dir}")

            return "\n".join(response_parts)

        except Exception as e:
            logger.exception("Failed to crawl site")
            return f"Failed to crawl site: {e!s}"

    def _download_youtube_video_task(
        video_url: str,
        output_dir: str,
        quality: str = "best",
        output_format: str = "mp4",
    ) -> str:
        """Internal download function for both sync and queue execution."""
        from pathlib import Path

        import yt_dlp

        # Validate output directory
        output_path = Path(output_dir)
        if not output_path.is_absolute():
            return f"Error: output_dir must be an absolute path. Got: {output_dir}"

        # Create directory if it doesn't exist
        output_path.mkdir(parents=True, exist_ok=True)

        # Get video info first to get title
        ydl_opts_info = {
            "quiet": True,
            "no_warnings": True,
        }

        with yt_dlp.YoutubeDL(ydl_opts_info) as ydl:
            info = ydl.extract_info(video_url, download=False)
            title = info.get("title", "video")
            # Sanitize title for filename
            safe_title = "".join(c for c in title if c.isalnum() or c in (" ", "-", "_")).strip()
            safe_title = safe_title.replace(" ", "_")

        # Configure download options
        quality_format = {
            "best": "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best",
            "1080p": (
                "bestvideo[height<=1080][ext=mp4]+bestaudio[ext=m4a]/"
                "best[height<=1080][ext=mp4]/best"
            ),
            "720p": (
                "bestvideo[height<=720][ext=mp4]+bestaudio[ext=m4a]/best[height<=720][ext=mp4]/best"
            ),
            "480p": (
                "bestvideo[height<=480][ext=mp4]+bestaudio[ext=m4a]/best[height<=480][ext=mp4]/best"
            ),
            "360p": (
                "bestvideo[height<=360][ext=mp4]+bestaudio[ext=m4a]/best[height<=360][ext=mp4]/best"
            ),
        }

        selected_format = quality_format.get(quality, quality_format["best"])

        ydl_opts = {
            "format": selected_format,
            "outtmpl": str(output_path / f"{safe_title}.%(ext)s"),
            "merge_output_format": output_format,
            "quiet": False,
            "no_warnings": False,
        }

        # Download video
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([video_url])

        # Find the downloaded file
        output_file = output_path / f"{safe_title}.{output_format}"
        if output_file.exists():
            file_size_mb = output_file.stat().st_size / 1024 / 1024
            return (
                f"Video downloaded successfully to: {output_file}\nFile size: {file_size_mb:.1f} MB"
            )
        return f"Download completed but file not found at expected location: {output_file}"

    @mcp.tool()
    async def download_youtube_video(
        video_url: str,
        output_dir: str,
        quality: str = "best",
        output_format: str = "mp4",
    ) -> str:
        """Download YouTube video to local file.

        Downloads video using yt-dlp with configurable quality and format.
        Automatically sanitizes filenames and creates output directory if needed.

        Args:
            video_url: YouTube video URL (youtube.com/watch?v=ID or youtu.be/ID format)
            output_dir: Directory to save the downloaded video (must be absolute path)
            quality: Video quality - 'best', '1080p', '720p', '480p', '360p'
            output_format: Output format - 'mp4', 'webm', 'mkv' (default: 'mp4')

        Returns:
            Success message with path to downloaded file.
        """
        try:
            # Execute synchronously (run in thread to avoid blocking)
            import asyncio

            return await asyncio.to_thread(
                _download_youtube_video_task, video_url, output_dir, quality, output_format
            )

        except Exception as e:
            logger.exception("Unexpected error in download_youtube_video")
            return f"Failed to download video: {e!s}"
