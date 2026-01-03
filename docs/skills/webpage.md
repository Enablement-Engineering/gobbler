# Web Page Conversion

Convert web pages to markdown using the Crawl4AI service.

**Requires**: Crawl4AI Docker container running

## Quick Start

```bash
# Start the service
docker compose up -d crawl4ai

# Basic fetch
gobbler webpage "https://example.com"

# Save to file
gobbler webpage "https://example.com" -o page.md

# Custom timeout
gobbler webpage "https://example.com" --timeout 60
```

## Extract with CSS Selector

Extract specific content from a page:

```bash
# Extract main article
gobbler webpage "https://example.com" --selector "article.main-content" -o article.md

# Extract by ID
gobbler webpage "https://example.com" --selector "#content" -o content.md

# Extract by class
gobbler webpage "https://example.com" --selector ".post-body" -o post.md
```

## Options

| Option | Description | Default |
|--------|-------------|---------|
| `--selector` | CSS selector to extract specific content | Full page |
| `--timeout` | Request timeout in seconds | 30 |
| `-o, --output` | Save to file | stdout |

## Alternative Command

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

## Output Format

```markdown
---
source: https://example.com/article
type: webpage
title: "Article Title"
word_count: 2341
converted_at: 2026-01-03T10:30:00Z
---

# Article Title

Page content converted to markdown...
```

## Features

- **JavaScript rendering** - Handles dynamic content
- **Clean markdown** - Removes ads, navigation, scripts
- **Preserves structure** - Headings, lists, links, code blocks
- **Image references** - Includes image alt text

## Common Selectors

| Site Type | Typical Selector |
|-----------|------------------|
| Blog posts | `article`, `.post-content`, `.entry-content` |
| Documentation | `main`, `.content`, `.docs-content` |
| News articles | `article`, `.article-body`, `.story-body` |
| GitHub README | `.markdown-body` |

## Troubleshooting

### "Service unavailable"

```bash
# Start the Crawl4AI service
docker compose up -d crawl4ai

# Check it's running
docker ps | grep crawl4ai

# View logs
docker logs gobbler-crawl4ai --tail 50
```

### Timeout errors

Increase the timeout for slow sites:

```bash
gobbler webpage "https://slow-site.com" --timeout 120
```

### Missing content

Try a more specific selector or check if the content is loaded via JavaScript after page load.
