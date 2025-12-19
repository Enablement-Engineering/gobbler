"""File handling utilities for saving converted content."""

import logging
from pathlib import Path
from typing import Optional

import aiofiles

logger = logging.getLogger(__name__)


async def save_markdown_file(
    file_path: str,
    content: str,
    create_dirs: bool = True,
) -> bool:
    """
    Save markdown content to file.

    Args:
        file_path: Absolute path to save file
        content: Markdown content with frontmatter
        create_dirs: Create parent directories if they don't exist

    Returns:
        True if successful, False otherwise
    """
    try:
        path = Path(file_path)

        # Create parent directories if needed
        if create_dirs and not path.parent.exists():
            path.parent.mkdir(parents=True, exist_ok=True)
            logger.info(f"Created directory: {path.parent}")

        # Write file
        async with aiofiles.open(path, "w", encoding="utf-8") as f:
            await f.write(content)

        logger.info(f"Saved markdown to: {file_path}")
        return True

    except PermissionError:
        logger.error(f"Permission denied writing to: {file_path}")
        return False
    except Exception as e:
        logger.error(f"Failed to write file {file_path}: {e}")
        return False


def validate_output_path(file_path: str) -> Optional[str]:
    """
    Validate output file path.

    Args:
        file_path: Path to validate

    Returns:
        Error message if invalid, None if valid
    """
    # Check if absolute path
    if not file_path.startswith("/"):
        return f"output_file must be an absolute path starting with '/'. Got: {file_path}"

    # Check if .md extension
    if not file_path.endswith(".md"):
        return f"output_file must have .md extension. Got: {file_path}"

    return None


def validate_input_path(file_path: str, allowed_extensions: tuple) -> Optional[str]:
    """
    Validate input file path.

    Args:
        file_path: Path to validate
        allowed_extensions: Tuple of allowed file extensions (e.g., ('.pdf', '.docx'))

    Returns:
        Error message if invalid, None if valid
    """
    path = Path(file_path)

    # Check if file exists
    if not path.exists():
        return f"File not found: {file_path}. Verify the path is correct and the file exists."

    # Check if it's a file (not directory)
    if not path.is_file():
        return f"Path is not a file: {file_path}"

    # Check extension
    if path.suffix.lower() not in allowed_extensions:
        ext_list = ", ".join(allowed_extensions)
        return (
            f"Unsupported file format: {path.suffix}. "
            f"This tool supports {ext_list}."
        )

    return None


def get_file_extension(file_path: str) -> str:
    """
    Get file extension without the dot.

    Args:
        file_path: Path to file

    Returns:
        Extension without dot (e.g., "pdf", "docx")
    """
    return Path(file_path).suffix.lstrip(".").lower()
