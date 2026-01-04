"""Output validation utilities for E2E tests."""

import re
from typing import Any

import yaml


def validate_markdown_output(
    content: str,
    expected_type: str | None = None,
) -> dict[str, Any]:
    """Validate markdown output structure and return parsed data.

    Validates that the content:
    - Has valid YAML frontmatter
    - Contains required fields for the content type
    - Has meaningful body content

    Args:
        content: Raw markdown output from gobbler
        expected_type: Expected content type (youtube_transcript, webpage,
                      document, audio_transcript). If None, skips type check.

    Returns:
        Dictionary with:
        - valid: bool - Whether validation passed
        - errors: list[str] - Any validation errors
        - metadata: dict - Parsed frontmatter metadata
        - body: str - Content body (after frontmatter)
        - word_count: int - Approximate word count
    """
    errors: list[str] = []
    metadata: dict[str, Any] = {}
    body = ""

    # Strip any leading content before frontmatter (e.g., progress spinners)
    # Only strip if content doesn't already start with ---
    if not content.strip().startswith("---"):
        # Look for the first occurrence of "---" at the start of a line
        frontmatter_start = content.find("\n---")
        if frontmatter_start != -1:
            content = content[frontmatter_start + 1 :]  # +1 to skip the newline
    else:
        content = content.strip()

    # Must have frontmatter
    if not content.startswith("---"):
        errors.append("Missing YAML frontmatter (must start with ---)")
        return {
            "valid": False,
            "errors": errors,
            "metadata": metadata,
            "body": content,
            "word_count": len(content.split()),
        }

    # Parse frontmatter using regex to find --- at line start only
    # This handles cases where --- appears within field values (e.g., video descriptions)
    frontmatter_pattern = re.compile(r"^---\s*$", re.MULTILINE)
    matches = list(frontmatter_pattern.finditer(content))

    if len(matches) < 2:
        errors.append("Invalid frontmatter structure (missing closing ---)")
        return {
            "valid": False,
            "errors": errors,
            "metadata": metadata,
            "body": content,
            "word_count": len(content.split()),
        }

    # Extract frontmatter between first and second ---
    frontmatter_start = matches[0].end()
    frontmatter_end = matches[1].start()
    frontmatter_yaml = content[frontmatter_start:frontmatter_end]
    body = content[matches[1].end() :].strip()

    try:
        metadata = yaml.safe_load(frontmatter_yaml) or {}
    except yaml.YAMLError as e:
        errors.append(f"Invalid YAML in frontmatter: {e}")
        return {
            "valid": False,
            "errors": errors,
            "metadata": {},
            "body": body,
            "word_count": 0,
        }

    # Validate required fields based on type
    required_fields: dict[str, list[str]] = {
        "youtube_transcript": ["source", "type", "video_id", "word_count"],
        "webpage": ["source", "type", "title", "word_count"],
        "document": ["source", "type", "format", "word_count"],
        "audio_transcript": ["source", "type", "duration", "language", "model"],
    }

    if expected_type:
        # Check type matches
        actual_type = metadata.get("type")
        if actual_type != expected_type:
            errors.append(f"Wrong type: expected '{expected_type}', got '{actual_type}'")

        # Check required fields
        for field in required_fields.get(expected_type, []):
            if field not in metadata:
                errors.append(f"Missing required field: {field}")

    # Body should have meaningful content
    word_count = len(body.split())
    if word_count < 10:
        errors.append(f"Body too short: {word_count} words (minimum 10)")

    return {
        "valid": len(errors) == 0,
        "errors": errors,
        "metadata": metadata,
        "body": body,
        "word_count": word_count,
    }


def has_timestamps(content: str) -> bool:
    """Check if content contains timestamp markers.

    Timestamps are typically in format [0:00], [00:00], or [0:00:00].

    Args:
        content: Markdown content to check

    Returns:
        True if timestamps found
    """
    # Match [0:00], [00:00], [0:00:00], [00:00:00] patterns
    return bool(re.search(r"\[\d{1,2}:\d{2}(:\d{2})?\]", content))


def has_markdown_structure(content: str) -> dict[str, bool]:
    """Check for common markdown structural elements.

    Args:
        content: Markdown content to check

    Returns:
        Dictionary indicating presence of various elements
    """
    return {
        "has_headings": bool(re.search(r"^#{1,6}\s", content, re.MULTILINE)),
        "has_bold": "**" in content,
        "has_italic": bool(re.search(r"(?<!\*)\*(?!\*)", content)),
        "has_lists": bool(re.search(r"^[\-\*]\s|^\d+\.\s", content, re.MULTILINE)),
        "has_links": bool(re.search(r"\[.+?\]\(.+?\)", content)),
        "has_code": "`" in content,
        "has_tables": bool(re.search(r"\|.+\|", content)),
    }
