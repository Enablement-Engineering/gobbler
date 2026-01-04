---
name: gobbler-webpage
description: Converts web pages to markdown with CSS selector extraction. Triggers on http/https URLs, fetch this page, grab webpage, scrape site, or requests to extract web content.
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

## Saving Output

When saving pages to a file, follow these steps:

### Step 1: Check for default output directory

```bash
gobbler config get output.default_directory
```

### Step 2: Save to the default directory

If a default directory is configured, use it with a descriptive filename:

```bash
gobbler webpage "https://example.com/article" -o "<default_directory>/Article Title.md"
```

### Step 3: If no default directory is configured

If the config returns empty/null, save to the current directory or ask the user where to save:

```bash
gobbler webpage "https://example.com/article" -o "Article Title.md"
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
