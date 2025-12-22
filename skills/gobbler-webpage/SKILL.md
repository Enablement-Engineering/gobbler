---
name: gobbler-webpage
description: Convert web pages to markdown, extract specific content with CSS selectors, and crawl websites. Use when user wants to fetch, scrape, or extract content from web pages or websites.
version: 2.0.0
---

# Gobbler Webpage

Convert web pages to markdown using the Crawl4AI service.

**Requires**: Crawl4AI Docker container running (`docker compose up -d crawl4ai`)

## Fetch Single Page

```bash
# Basic fetch
gobbler webpage "https://example.com"

# Save to file
gobbler webpage "https://example.com" -o page.md

# Custom timeout
gobbler webpage "https://example.com" --timeout 60
```

## Extract with CSS Selector

```bash
# Extract specific content
gobbler webpage "https://example.com" --selector "article.main-content" -o article.md
```

## Alternative: Using the Convert Subcommand

```bash
gobbler convert webpage "https://example.com" -o page.md
```

## Python SDK

```python
from gobbler_sdk import GobblerClient

client = GobblerClient()

# Fetch webpage
result = client.convert.webpage(
    "https://example.com",
    include_images=True,
    timeout=30
)
print(result.markdown)
print(result.metadata)  # url, title, word_count, etc.
```

## REST API

```bash
curl -X POST http://localhost:4600/convert/webpage \
  -H "Content-Type: application/json" \
  -d '{
    "url": "https://example.com",
    "include_images": true,
    "timeout": 30
  }'
```

## Advanced Options (via API)

```bash
# With CSS selector extraction
curl -X POST http://localhost:4600/convert/webpage \
  -H "Content-Type: application/json" \
  -d '{
    "url": "https://example.com",
    "css_selector": "article.content",
    "extract_links": true,
    "bypass_cache": true
  }'
```

## Prerequisites

Start services before using:

```bash
cd /path/to/gobbler
docker compose up -d crawl4ai

# Check health
curl http://localhost:11235/health
```
