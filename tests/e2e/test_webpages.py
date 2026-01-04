"""E2E tests for web page conversion.

These tests require the Crawl4AI Docker container to be running.
Start with: docker compose up crawl4ai
"""

import pytest

from .helpers import get_first_url, load_url_list, validate_markdown_output

pytestmark = [pytest.mark.requires_network, pytest.mark.requires_crawl4ai]


class TestSingleWebpage:
    """Tests for single webpage conversion."""

    def test_fetch_documentation_page(self, run_gobbler):
        """Test fetching a technical documentation page."""
        url = get_first_url("webpages", "documentation.txt")

        result = run_gobbler(
            ["webpage", url],
            timeout=60,
        )

        assert result.returncode == 0, f"CLI failed: {result.stderr}"

        validation = validate_markdown_output(result.stdout, "webpage")
        assert validation["valid"], f"Validation errors: {validation['errors']}"
        assert validation["word_count"] > 50, "Page content too short"

    def test_fetch_government_page(self, run_gobbler):
        """Test fetching a .gov page (public domain content)."""
        url = get_first_url("webpages", "government.txt")

        result = run_gobbler(
            ["webpage", url],
            timeout=60,
        )

        assert result.returncode == 0, f"CLI failed: {result.stderr}"

        validation = validate_markdown_output(result.stdout, "webpage")
        assert validation["valid"], f"Validation errors: {validation['errors']}"

    def test_fetch_wikipedia_article(self, run_gobbler):
        """Test fetching Wikipedia article (complex structure)."""
        url = get_first_url("webpages", "wikipedia.txt")

        result = run_gobbler(
            ["webpage", url],
            timeout=60,
        )

        assert result.returncode == 0, f"CLI failed: {result.stderr}"

        validation = validate_markdown_output(result.stdout, "webpage")
        assert validation["valid"], f"Validation errors: {validation['errors']}"

        # Wikipedia articles should have substantial content
        assert validation["word_count"] > 200, "Wikipedia article too short"

    def test_fetch_blog_page(self, run_gobbler):
        """Test fetching a CC-licensed blog page."""
        url = get_first_url("webpages", "blogs.txt")

        result = run_gobbler(
            ["webpage", url],
            timeout=60,
        )

        assert result.returncode == 0, f"CLI failed: {result.stderr}"

        validation = validate_markdown_output(result.stdout, "webpage")
        assert validation["valid"], f"Validation errors: {validation['errors']}"

    def test_fetch_to_file(self, run_gobbler, temp_output_dir):
        """Test saving webpage to file."""
        url = get_first_url("webpages", "documentation.txt")
        output_file = temp_output_dir / "page.md"

        result = run_gobbler(
            ["webpage", url, "-o", str(output_file)],
            timeout=60,
        )

        assert result.returncode == 0, f"CLI failed: {result.stderr}"
        assert output_file.exists(), "Output file not created"

        content = output_file.read_text()
        validation = validate_markdown_output(content, "webpage")
        assert validation["valid"], f"Validation errors: {validation['errors']}"

    def test_fetch_without_images(self, run_gobbler):
        """Test fetching page with images disabled."""
        url = get_first_url("webpages", "documentation.txt")

        result = run_gobbler(
            ["webpage", url, "--no-images"],
            timeout=60,
        )

        assert result.returncode == 0, f"CLI failed: {result.stderr}"

        validation = validate_markdown_output(result.stdout, "webpage")
        assert validation["valid"], f"Validation errors: {validation['errors']}"


class TestWebpageErrors:
    """Tests for webpage conversion error handling."""

    def test_invalid_url_error(self, run_gobbler):
        """Test error handling for invalid URL."""
        result = run_gobbler(
            ["webpage", "not-a-valid-url"],
            timeout=30,
        )

        assert result.returncode != 0, "Should fail for invalid URL"

    def test_nonexistent_domain_error(self, run_gobbler):
        """Test error handling for nonexistent domain."""
        result = run_gobbler(
            ["webpage", "https://this-domain-definitely-does-not-exist-12345.com"],
            timeout=30,
        )

        assert result.returncode != 0, "Should fail for nonexistent domain"

    def test_timeout_handling(self, run_gobbler):
        """Test that timeout parameter works."""
        url = get_first_url("webpages", "documentation.txt")

        # Very short timeout should work for a responsive site
        result = run_gobbler(
            ["webpage", url, "--timeout", "5"],
            timeout=30,
        )

        # Should either succeed quickly or timeout gracefully
        # (depends on network conditions)
        if result.returncode == 0:
            validation = validate_markdown_output(result.stdout, "webpage")
            assert validation["valid"]


@pytest.mark.slow
class TestBatchWebpages:
    """Tests for batch webpage conversion."""

    def test_batch_fetch_documentation(self, run_gobbler, temp_output_dir, urls_dir):
        """Test batch fetching documentation pages."""
        urls = load_url_list("webpages", "documentation.txt")[:3]  # Limit for speed

        # Write URLs to temp file
        url_file = temp_output_dir / "urls.txt"
        url_file.write_text("\n".join(urls))

        result = run_gobbler(
            [
                "batch",
                "webpages",
                str(url_file),
                "-o",
                str(temp_output_dir / "output"),
            ],
            timeout=180,
        )

        assert result.returncode == 0, f"CLI failed: {result.stderr}"

        # Should have created markdown files
        output_dir = temp_output_dir / "output"
        if output_dir.exists():
            md_files = list(output_dir.glob("*.md"))
            assert len(md_files) >= 1, "No output files created"

    def test_batch_fetch_with_concurrency(self, run_gobbler, temp_output_dir, urls_dir):
        """Test batch fetching with custom concurrency."""
        urls = load_url_list("webpages", "documentation.txt")[:2]

        url_file = temp_output_dir / "urls.txt"
        url_file.write_text("\n".join(urls))

        result = run_gobbler(
            [
                "batch",
                "webpages",
                str(url_file),
                "-o",
                str(temp_output_dir / "output"),
                "--concurrency",
                "2",
            ],
            timeout=180,
        )

        assert result.returncode == 0, f"CLI failed: {result.stderr}"
