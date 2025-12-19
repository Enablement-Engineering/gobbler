---
name: gobbler-webpage
description: Convert web pages to markdown, extract specific content with CSS selectors, and crawl websites. Use when user wants to fetch, scrape, or extract content from web pages or websites.
---

# Gobbler Webpage

Convert web pages to markdown using the Crawl4AI service.

**Requires**: Crawl4AI Docker container running on port 11235

## Fetch Single Page

Convert a web page to markdown:

```bash
uv run scripts/fetch.py "https://example.com"

# Exclude images
uv run scripts/fetch.py "https://example.com" --no-images

# Save to file
uv run scripts/fetch.py "https://example.com" --output page.md

# Custom timeout
uv run scripts/fetch.py "https://example.com" --timeout 60
```

## Extract with Selector

Extract specific content using CSS or XPath selectors:

```bash
# CSS selector
uv run scripts/fetch_with_selector.py "https://example.com" --selector "article.main-content"

# XPath selector
uv run scripts/fetch_with_selector.py "https://example.com" --xpath "//div[@class='content']"

# Extract and get all links
uv run scripts/fetch_with_selector.py "https://example.com" --selector ".content" --extract-links
```

## Crawl Website

Recursively crawl a website:

```bash
# Basic crawl (depth 2, max 50 pages)
uv run scripts/crawl.py "https://docs.example.com"

# Custom depth and limits
uv run scripts/crawl.py "https://docs.example.com" --max-depth 3 --max-pages 100

# URL pattern filtering
uv run scripts/crawl.py "https://example.com" --include "/docs/" --exclude "/api/"

# Save all pages to directory
uv run scripts/crawl.py "https://docs.example.com" --output-dir ./crawled
```

## Prerequisites

Start Crawl4AI container before using:

```bash
docker run -d -p 11235:11235 --name crawl4ai crawl4ai/crawl4ai
```

Check health:

```bash
uv run ../gobbler-utils/scripts/docker_health.py crawl4ai
```
