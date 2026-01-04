---
name: gobbler-webpage
description: Convert web pages to markdown, extract specific content with CSS selectors, and crawl websites. Use when user wants to fetch, scrape, or extract content from web pages or websites.
version: 2.1.0
---

# Gobbler Webpage

Convert web pages to markdown using the Crawl4AI service.

**Requires**: Crawl4AI Docker container running (`docker compose up -d crawl4ai`)

## CLI Options

| Option | Short | Description | Default |
|--------|-------|-------------|---------|
| `--output` | `-o` | Output file path (stdout if not specified) | - |
| `--selector` | `-s` | CSS selector to extract specific content | - |
| `--timeout` | `-t` | Request timeout in seconds | 30 |
| `--images/--no-images` | - | Include images in output | `--images` |
| `--format` | `-f` | Output format: `markdown`, `json`, `table` | `markdown` |
| `--provider` | `-p` | Webpage conversion provider | `crawl4ai` |

## Fetch Single Page

```bash
# Basic fetch
gobbler webpage "https://example.com"

# Save to file
gobbler webpage "https://example.com" -o page.md

# Custom timeout
gobbler webpage "https://example.com" --timeout 60

# Exclude images from output
gobbler webpage "https://example.com" --no-images -o page.md
```

## Extract with CSS Selector

```bash
# Extract specific content
gobbler webpage "https://example.com" --selector "article.main-content" -o article.md
```

## Output Formats

```bash
# JSON format (includes metadata)
gobbler webpage "https://example.com" --format json

# Table format
gobbler webpage "https://example.com" --format table
```

## Alternative: Using the Convert Subcommand

```bash
gobbler convert webpage "https://example.com" -o page.md
```

## Prerequisites

Start services before using:

```bash
cd /path/to/gobbler
docker compose up -d crawl4ai

# Check health
curl http://localhost:11235/health
```
