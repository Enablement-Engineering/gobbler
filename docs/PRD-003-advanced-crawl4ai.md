# PRD-003: Advanced Crawl4AI Features

## Overview
**Epic**: Enhanced Web Scraping Capabilities
**Phase**: 2 - Feature Enhancement
**Estimated Effort**: 3-4 days
**Dependencies**: None - extends existing webpage converter
**Parallel**: ✅ Can be implemented alongside other PRDs

## Problem Statement
Gobbler currently uses Crawl4AI for basic web page to markdown conversion, but doesn't expose key powerful features:
- **Link extraction & crawling** - Follow links to configurable depth for documentation sites
- **Advanced selectors** - CSS/XPath for targeted content extraction
- **Session management** - Handle auth, cookies, localStorage for authenticated content

Users who need to crawl entire documentation sites, extract specific content sections, or access authenticated pages must use separate tools or manually script solutions.

**User Stories:**
- "As a content archiver, I want to crawl a documentation site to configurable depth"
- "As a researcher, I want to extract only the main article content using CSS selectors"
- "As a developer, I want to crawl authenticated content by reusing my login session"

## Success Criteria
- [ ] Configurable link following (depth-based crawling)
- [ ] CSS/XPath selector-based extraction
- [ ] Session persistence (cookies, localStorage)
- [ ] Link extraction with internal/external categorization
- [ ] Polite crawling with delays and robots.txt respect

## Technical Requirements

### Enhanced MCP Tools

#### 1. `fetch_webpage_with_selector`

```python
@mcp.tool()
async def fetch_webpage_with_selector(
    url: str,
    output_file: Optional[str] = None,
    # Selector Options
    css_selector: Optional[str] = None,
    xpath_selector: Optional[str] = None,
    extract_links: bool = False,
    # Content Options
    include_images: bool = True,
    # Session Options
    session_id: Optional[str] = None,
    # Advanced Options
    bypass_cache: bool = False,
    timeout: int = 30,
) -> str:
    """
    Convert web page to markdown with CSS/XPath selector support.

    Extract only specific content from web pages using CSS or XPath selectors.
    Useful for extracting main article content, filtering navigation, or
    targeting specific sections.

    Args:
        url: Full HTTP/HTTPS URL of web page
        output_file: Path to save markdown (auto-generates if directory)

        Selector Options:
        css_selector: Extract only content matching CSS selector (e.g., 'article.main', '#content')
        xpath_selector: Extract only content matching XPath (e.g., '//div[@class="content"]')
        extract_links: Extract all links with metadata (internal/external) (default: False)

        Content Options:
        include_images: Include image references in markdown (default: True)

        Session Options:
        session_id: Reuse browser session for authenticated crawling (default: None)

        Advanced Options:
        bypass_cache: Force fresh fetch, bypass Crawl4AI cache (default: False)
        timeout: Request timeout in seconds (default: 30, max: 120)

    Returns:
        Markdown content with YAML frontmatter including:
        - Extracted content from selector
        - Links metadata (if extract_links=True)
        - Selector used for extraction
    """
```

#### 2. `crawl_site`

```python
@mcp.tool()
async def crawl_site(
    start_url: str,
    output_dir: str,
    # Crawl Options
    max_depth: int = 2,
    max_pages: int = 50,
    same_domain_only: bool = True,
    url_pattern: Optional[str] = None,
    exclude_pattern: Optional[str] = None,
    css_selector: Optional[str] = None,
    # Content Options
    include_images: bool = True,
    extract_links: bool = True,
    # Performance Options
    concurrency: int = 3,
    delay_between_requests: float = 1.0,
    respect_robots_txt: bool = True,
    # Session Options
    session_id: Optional[str] = None,
    # Advanced Options
    timeout: int = 30,
) -> str:
    """
    Crawl website starting from URL, following links to configurable depth.

    Recursively follows links and converts pages to markdown. Respects robots.txt
    and implements polite crawling with configurable delays. Useful for
    documentation sites, blogs, or content archives.

    Args:
        start_url: Starting URL for crawl
        output_dir: Directory to save markdown files (creates subdirectories)

        Crawl Options:
        max_depth: Maximum link depth to follow (default: 2, max: 5)
        max_pages: Maximum total pages to crawl (default: 50, max: 500)
        same_domain_only: Only follow links on same domain (default: True)
        url_pattern: Regex pattern - only crawl URLs matching (default: None)
        exclude_pattern: Regex pattern - skip URLs matching (default: None)
        css_selector: CSS selector to extract from each page (default: None)

        Content Options:
        include_images: Include image references in markdown (default: True)
        extract_links: Extract link graph for visualization (default: True)

        Performance Options:
        concurrency: Concurrent page fetches (default: 3, max: 10)
        delay_between_requests: Seconds between requests (default: 1.0)
        respect_robots_txt: Check and respect robots.txt (default: True)

        Session Options:
        session_id: Reuse browser session (for authenticated crawling) (default: None)

        Advanced Options:
        timeout: Per-page timeout in seconds (default: 30, max: 120)

    Returns:
        Crawl summary with:
        - Total pages crawled
        - Pages by depth level
        - List of saved files
        - Link graph (if extract_links=True)
        - Any errors encountered
        - Crawl statistics
    """
```

#### 3. `create_crawl_session`

```python
@mcp.tool()
async def create_crawl_session(
    session_name: str,
    login_url: Optional[str] = None,
    cookies: Optional[List[Dict]] = None,
    local_storage: Optional[Dict] = None,
    user_agent: Optional[str] = None,
) -> str:
    """
    Create reusable browser session for authenticated crawling.

    Persists cookies, localStorage, and session state for reuse across multiple
    crawl operations. Useful for accessing authenticated content without repeated logins.

    Args:
        session_name: Unique name for this session
        login_url: URL to visit first (e.g., to trigger auth) (default: None)
        cookies: List of cookie dicts to initialize session (default: None)
        local_storage: localStorage key-value pairs (default: None)
        user_agent: Custom user agent for session (default: None)

    Returns:
        Session ID and instructions for using with other tools

    Example:
        # Create session with cookies from browser export
        session = create_crawl_session(
            session_name="github",
            cookies=[
                {"name": "user_session", "value": "abc123", "domain": ".github.com"}
            ]
        )

        # Use session in subsequent crawls
        crawl_site("https://github.com/myorg/private-repo", session_id=session_id)
    """
```

## Implementation Details

### Selector-Based Extraction

```python
# src/gobbler_mcp/converters/webpage_selector.py
from typing import Optional, List, Dict, Tuple
import httpx
import asyncio
from pathlib import Path
from ..config import get_config
from ..utils.frontmatter import create_webpage_frontmatter

async def convert_webpage_with_selector(
    url: str,
    css_selector: Optional[str] = None,
    xpath_selector: Optional[str] = None,
    extract_links: bool = False,
    include_images: bool = True,
    session_id: Optional[str] = None,
    bypass_cache: bool = False,
    timeout: int = 30,
) -> Tuple[str, Dict]:
    """
    Convert web page with CSS/XPath selector support.
    """
    config = get_config()
    service_url = config.get_service_url("crawl4ai")
    api_token = config.data.get("services", {}).get("crawl4ai", {}).get("api_token")

    # Build browser configuration
    browser_config = {
        "type": "BrowserConfig",
        "params": {"headless": True}
    }

    # Build crawler configuration
    crawler_params = {
        "stream": False,
        "cache_mode": "bypass" if bypass_cache else "enabled",
    }

    # Add CSS or XPath selector for targeted extraction
    if css_selector:
        crawler_params["css_selector"] = css_selector
    elif xpath_selector:
        crawler_params["xpath"] = xpath_selector

    # Add extraction config
    if extract_links:
        crawler_params["extraction_config"] = {
            "extract_links": True
        }

    # Load session state if provided
    if session_id:
        session_state = _load_session_state(session_id)
        if session_state:
            browser_config["params"]["cookies"] = session_state.get("cookies", [])

    # Build Crawl4AI request
    crawl_request = {
        "urls": [url],
        "browser_config": browser_config,
        "crawler_config": {
            "type": "CrawlerRunConfig",
            "params": crawler_params
        }
    }

    headers = {"Authorization": f"Bearer {api_token}"}

    # Submit crawl request and poll for completion
    async with httpx.AsyncClient(timeout=timeout) as client:
        response = await client.post(
            f"{service_url}/crawl",
            json=crawl_request,
            headers=headers
        )
        response.raise_for_status()
        task_data = response.json()
        task_id = task_data.get("task_id")

        # Poll for completion
        result = await _poll_for_completion(client, service_url, task_id, headers, timeout)

    # Extract markdown content
    markdown_content = result.get("markdown", {}).get("fit_markdown") or \
                      result.get("markdown", {}).get("raw_markdown")

    if not markdown_content:
        raise RuntimeError("No markdown content in response")

    # Build metadata
    metadata = {
        "url": url,
        "title": result.get("title", "Web Page"),
        "word_count": len(markdown_content.split()),
        "selector_used": css_selector or xpath_selector,
    }

    # Add links if extracted
    if extract_links and result.get("links"):
        metadata["links"] = {
            "internal": result["links"].get("internal", []),
            "external": result["links"].get("external", []),
        }

    # Create frontmatter
    frontmatter = create_webpage_frontmatter(
        url=url,
        title=metadata["title"],
        word_count=metadata["word_count"],
        conversion_time_ms=0,
    )

    # Add selector info to frontmatter
    if css_selector or xpath_selector:
        frontmatter += f"selector: {css_selector or xpath_selector}\n"

    full_markdown = frontmatter + markdown_content

    return full_markdown, metadata


async def _poll_for_completion(
    client: httpx.AsyncClient,
    service_url: str,
    task_id: str,
    headers: dict,
    max_wait: int
) -> dict:
    """Poll Crawl4AI for task completion"""
    wait_interval = 1
    elapsed = 0

    while elapsed < max_wait:
        await asyncio.sleep(wait_interval)
        elapsed += wait_interval

        status_response = await client.get(
            f"{service_url}/task/{task_id}",
            headers=headers
        )
        status_response.raise_for_status()
        task_status = status_response.json()

        if task_status.get("status") == "completed":
            results = task_status.get("results", [])
            if not results:
                raise RuntimeError("No results returned")
            return results[0]
        elif task_status.get("status") == "failed":
            raise RuntimeError(f"Crawl failed: {task_status.get('error')}")

    raise httpx.TimeoutException(f"Crawl timeout after {max_wait}s")
```

### Site Crawler Implementation

```python
# src/gobbler_mcp/crawlers/site_crawler.py
import asyncio
import re
from typing import Set, List, Dict, Optional
from urllib.parse import urljoin, urlparse
from collections import deque
from pathlib import Path
from bs4 import BeautifulSoup
from ..converters.webpage_selector import convert_webpage_with_selector

class SiteCrawler:
    """Recursive site crawler with depth control and link extraction"""

    def __init__(
        self,
        start_url: str,
        output_dir: Path,
        max_depth: int = 2,
        max_pages: int = 50,
        same_domain_only: bool = True,
        url_pattern: Optional[str] = None,
        exclude_pattern: Optional[str] = None,
        css_selector: Optional[str] = None,
        concurrency: int = 3,
        delay: float = 1.0,
        respect_robots_txt: bool = True,
        session_id: Optional[str] = None,
        extract_links: bool = True,
    ):
        self.start_url = start_url
        self.output_dir = output_dir
        self.max_depth = max_depth
        self.max_pages = max_pages
        self.same_domain_only = same_domain_only
        self.url_pattern = re.compile(url_pattern) if url_pattern else None
        self.exclude_pattern = re.compile(exclude_pattern) if exclude_pattern else None
        self.css_selector = css_selector
        self.concurrency = concurrency
        self.delay = delay
        self.respect_robots_txt = respect_robots_txt
        self.session_id = session_id
        self.extract_links = extract_links

        self.visited: Set[str] = set()
        self.queue: deque = deque([(start_url, 0)])  # (url, depth)
        self.results: List[Dict] = []
        self.link_graph: List[Dict] = []  # For link visualization
        self.base_domain = urlparse(start_url).netloc

    def should_crawl(self, url: str) -> bool:
        """Check if URL should be crawled"""
        if url in self.visited or len(self.visited) >= self.max_pages:
            return False

        parsed = urlparse(url)

        # Same domain check
        if self.same_domain_only and parsed.netloc != self.base_domain:
            return False

        # URL pattern check
        if self.url_pattern and not self.url_pattern.search(url):
            return False

        # Exclude pattern check
        if self.exclude_pattern and self.exclude_pattern.search(url):
            return False

        return True

    async def crawl(self) -> Dict:
        """Execute crawl"""
        semaphore = asyncio.Semaphore(self.concurrency)

        async def crawl_page(url: str, depth: int):
            if not self.should_crawl(url):
                return

            async with semaphore:
                self.visited.add(url)

                try:
                    # Polite crawling delay
                    await asyncio.sleep(self.delay)

                    # Convert page with optional selector
                    markdown, metadata = await convert_webpage_with_selector(
                        url=url,
                        css_selector=self.css_selector,
                        extract_links=self.extract_links,
                        session_id=self.session_id,
                        timeout=30
                    )

                    # Save to file
                    safe_filename = re.sub(r'[^\w\-_]', '_', url.split('/')[-1] or 'index')
                    output_file = self.output_dir / f"{safe_filename}_depth{depth}.md"
                    output_file.write_text(markdown)

                    self.results.append({
                        'url': url,
                        'depth': depth,
                        'output_file': str(output_file),
                        'title': metadata.get('title'),
                        'word_count': metadata.get('word_count'),
                    })

                    # Extract and queue links for next depth
                    if depth < self.max_depth and metadata.get('links'):
                        internal_links = metadata['links'].get('internal', [])
                        for link_url in internal_links[:20]:  # Limit links per page
                            normalized_url = urljoin(url, link_url)
                            if self.should_crawl(normalized_url):
                                self.queue.append((normalized_url, depth + 1))

                            # Build link graph
                            if self.extract_links:
                                self.link_graph.append({
                                    'source': url,
                                    'target': normalized_url,
                                    'depth': depth
                                })

                except Exception as e:
                    self.results.append({
                        'url': url,
                        'depth': depth,
                        'error': str(e),
                    })

        # Process initial URL
        initial_url, initial_depth = self.queue.popleft()
        await crawl_page(initial_url, initial_depth)

        # Process remaining queue
        while self.queue and len(self.visited) < self.max_pages:
            tasks = []
            # Process up to concurrency limit
            for _ in range(min(self.concurrency, len(self.queue))):
                if self.queue:
                    url, depth = self.queue.popleft()
                    tasks.append(crawl_page(url, depth))

            if tasks:
                await asyncio.gather(*tasks)

        return self._generate_summary()

    def _generate_summary(self) -> Dict:
        """Generate crawl summary"""
        successful = [r for r in self.results if 'error' not in r]
        failed = [r for r in self.results if 'error' in r]

        summary = {
            'total_pages': len(self.results),
            'successful': len(successful),
            'failed': len(failed),
            'pages_by_depth': self._count_by_depth(),
            'results': self.results,
        }

        if self.extract_links:
            summary['link_graph'] = self.link_graph
            summary['total_links'] = len(self.link_graph)

        return summary

    def _count_by_depth(self) -> Dict[int, int]:
        """Count pages by depth level"""
        counts = {}
        for result in self.results:
            if 'depth' in result:
                depth = result['depth']
                counts[depth] = counts.get(depth, 0) + 1
        return counts
```

### Session Management

```python
# src/gobbler_mcp/crawlers/session_manager.py
import json
import logging
from pathlib import Path
from typing import Dict, Optional, List

logger = logging.getLogger(__name__)

class SessionManager:
    """Manage browser sessions for authenticated crawling"""

    def __init__(self, sessions_dir: Optional[Path] = None):
        self.sessions_dir = sessions_dir or Path.home() / ".config" / "gobbler" / "sessions"
        self.sessions_dir.mkdir(parents=True, exist_ok=True)

    def create_session(
        self,
        session_name: str,
        cookies: Optional[List[Dict]] = None,
        local_storage: Optional[Dict] = None,
        user_agent: Optional[str] = None,
    ) -> str:
        """Create and persist a browser session"""
        session_id = f"session_{session_name}"
        session_file = self.sessions_dir / f"{session_id}.json"

        session_data = {
            "name": session_name,
            "cookies": cookies or [],
            "local_storage": local_storage or {},
            "user_agent": user_agent,
        }

        with open(session_file, 'w') as f:
            json.dump(session_data, f, indent=2)

        logger.info(f"Created session: {session_id}")
        return session_id

    def load_session(self, session_id: str) -> Optional[Dict]:
        """Load session state"""
        session_file = self.sessions_dir / f"{session_id}.json"

        if not session_file.exists():
            logger.warning(f"Session not found: {session_id}")
            return None

        with open(session_file, 'r') as f:
            return json.load(f)

    def delete_session(self, session_id: str) -> bool:
        """Delete a session"""
        session_file = self.sessions_dir / f"{session_id}.json"

        if session_file.exists():
            session_file.unlink()
            logger.info(f"Deleted session: {session_id}")
            return True

        return False

    def list_sessions(self) -> List[Dict]:
        """List all available sessions"""
        sessions = []
        for session_file in self.sessions_dir.glob("session_*.json"):
            with open(session_file, 'r') as f:
                data = json.load(f)
                sessions.append({
                    'id': session_file.stem,
                    'name': data.get('name'),
                    'cookie_count': len(data.get('cookies', [])),
                })
        return sessions


# Helper function for converters
def _load_session_state(session_id: str) -> Optional[Dict]:
    """Load session state for use in converters"""
    manager = SessionManager()
    return manager.load_session(session_id)
```

## Acceptance Criteria

### 1. Selector-Based Extraction
- [ ] CSS selector extraction works correctly
- [ ] XPath selector extraction works correctly
- [ ] Extracted content preserves structure
- [ ] Link extraction with internal/external categorization
- [ ] Session integration works with selectors

### 2. Site Crawling
- [ ] Recursive link following to max_depth
- [ ] Same-domain restriction enforced
- [ ] URL pattern filtering works
- [ ] Robots.txt respected
- [ ] Polite crawling with delays
- [ ] Concurrency control
- [ ] Link graph generation
- [ ] Comprehensive summary report
- [ ] CSS selector applies to all crawled pages

### 3. Session Management
- [ ] Sessions persist cookies to disk
- [ ] localStorage supported
- [ ] Sessions reusable across tools
- [ ] Session listing and deletion works
- [ ] Custom user agents work
- [ ] Session state loaded correctly in converters

## Deliverables

### Files to Create
```
src/gobbler_mcp/
├── converters/
│   └── webpage_selector.py      # Selector-based webpage converter
├── crawlers/
│   ├── __init__.py
│   ├── site_crawler.py          # Recursive site crawler
│   └── session_manager.py       # Browser session management
└── server.py                    # Add new tools

tests/
├── unit/
│   ├── test_webpage_selector.py
│   ├── test_site_crawler.py
│   └── test_session_manager.py
└── integration/
    ├── test_selector_crawl.py
    └── test_authenticated_crawl.py
```

### Dependencies to Add
```toml
# Add to pyproject.toml
dependencies = [
    # ... existing ...
    "beautifulsoup4>=4.12.0",  # For link extraction
]
```

## Technical Notes

### Crawl4AI API Capabilities Used
Based on Crawl4AI documentation:
- CSS selectors via `css_selector` parameter
- XPath via `xpath` parameter
- Link extraction via `extraction_config.extract_links`
- Session state via `cookies` in browser config
- Polite crawling with delays

### Performance Considerations
- CSS/XPath extraction: Similar performance to full page extraction
- Site crawling: 1-2 seconds per page with delays
- Link graph generation: Negligible overhead
- Session management: <10ms per session load

### Selector Examples
```python
# CSS Selectors
css_selector="article.main"           # Main article
css_selector="#content"                # Content by ID
css_selector=".post-content"          # Content by class
css_selector="main > article"         # Direct child

# XPath Selectors
xpath_selector="//div[@class='content']"
xpath_selector="//article[@role='main']"
xpath_selector="//div[contains(@class, 'post')]"
```

### Link Graph Format
```json
{
  "link_graph": [
    {
      "source": "https://example.com/",
      "target": "https://example.com/page1",
      "depth": 0
    },
    {
      "source": "https://example.com/page1",
      "target": "https://example.com/page2",
      "depth": 1
    }
  ],
  "total_links": 2
}
```

## Definition of Done
- [ ] All three tools implemented
- [ ] Integration with Crawl4AI working
- [ ] Site crawler with depth control functional
- [ ] Session management working
- [ ] Link extraction and graph generation
- [ ] Tests cover new functionality
- [ ] Documentation complete with examples
- [ ] Performance acceptable

## References
- Crawl4AI documentation: https://docs.crawl4ai.com/
- Crawl4AI GitHub: https://github.com/unclecode/crawl4ai
- CSS Selectors: https://developer.mozilla.org/en-US/docs/Web/CSS/CSS_Selectors
- XPath: https://developer.mozilla.org/en-US/docs/Web/XPath
