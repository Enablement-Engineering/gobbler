# Webpage Conversion

Use for URLs, web pages, articles, site scraping, selector extraction, and saving web content as markdown.

## Commands

```bash
# Check service readiness first
gobbler doctor --json

# Basic page conversion
gobbler webpage "https://example.com" -o ./outputs/page.md

# Custom timeout
gobbler webpage "https://example.com" --timeout 60 -o ./outputs/page.md

# Exclude images from output
gobbler webpage "https://example.com" --no-images -o ./outputs/page.md

# Extract a specific selector
gobbler webpage "https://example.com" --selector "article.main-content" -o ./outputs/article.md

# JSON or table output
gobbler webpage "https://example.com" --format json
gobbler webpage "https://example.com" --format table
```

## Requirements

- Webpage conversion uses the Crawl4AI service.
- Start services with `make start-docker` or `docker compose up -d crawl4ai`.

## Useful options

- `--output`, `-o`: output file path.
- `--selector`, `-s`: CSS selector for targeted extraction.
- `--clean`, `-c`: auto-strip nav/footer/sidebar boilerplate.
- `--timeout`, `-t`: request timeout in seconds.
- `--images/--no-images`: include or exclude images.
- `--format`, `-f`: `markdown`, `json`, or `table`.
- `--provider`, `-p`: webpage conversion provider, usually `crawl4ai`.
- `--skip-if-exists`: skip existing output files in repeatable/batch workflows.

## Tips

- Use `--clean` for AI consumption when boilerplate is noisy.
- Use `--selector` for precise article/body extraction.
- For URL lists, use `references/batch.md`.

## Troubleshooting

```bash
gobbler doctor --json
make start-docker
docker compose ps || docker-compose ps
docker logs gobbler-crawl4ai --tail 50
```
