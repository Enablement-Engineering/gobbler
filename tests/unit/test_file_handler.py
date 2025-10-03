"""Unit tests for file handling utilities."""

import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock, AsyncMock
import aiofiles

from gobbler_mcp.utils.file_handler import (
    save_markdown_file,
    validate_output_path,
    validate_input_path,
    get_file_extension,
)


class TestFileExtraction:
    """Test file extension extraction."""

    def test_get_file_extension_basic(self):
        """Test extracting file extension without dot."""
        assert get_file_extension("/path/to/file.pdf") == "pdf"
        assert get_file_extension("/path/to/file.docx") == "docx"
        assert get_file_extension("/path/to/file.MP3") == "mp3"  # Case insensitive

    def test_get_file_extension_multiple_dots(self):
        """Test extension extraction with multiple dots in filename."""
        assert get_file_extension("/path/to/my.file.name.pdf") == "pdf"


class TestOutputPathValidation:
    """Test output file path validation."""

    def test_validate_output_path_valid(self):
        """Test that valid output paths pass validation."""
        assert validate_output_path("/path/to/output.md") is None

    def test_validate_output_path_must_be_absolute(self):
        """Test that relative paths are rejected."""
        error = validate_output_path("relative/path/output.md")
        assert error is not None
        assert "absolute path" in error

    def test_validate_output_path_must_be_md(self):
        """Test that non-.md extensions are rejected."""
        error = validate_output_path("/path/to/output.txt")
        assert error is not None
        assert ".md extension" in error


class TestInputPathValidation:
    """Test input file path validation."""

    @patch("gobbler_mcp.utils.file_handler.Path")
    def test_validate_input_path_file_not_found(self, mock_path_class):
        """Test that nonexistent files are rejected."""
        mock_path = MagicMock()
        mock_path.exists.return_value = False
        mock_path_class.return_value = mock_path

        error = validate_input_path("/path/to/nonexistent.pdf", (".pdf",))
        assert error is not None
        assert "File not found" in error

    @patch("gobbler_mcp.utils.file_handler.Path")
    def test_validate_input_path_not_a_file(self, mock_path_class):
        """Test that directories are rejected."""
        mock_path = MagicMock()
        mock_path.exists.return_value = True
        mock_path.is_file.return_value = False
        mock_path_class.return_value = mock_path

        error = validate_input_path("/path/to/directory", (".pdf",))
        assert error is not None
        assert "not a file" in error

    @patch("gobbler_mcp.utils.file_handler.Path")
    def test_validate_input_path_unsupported_extension(self, mock_path_class):
        """Test that unsupported extensions are rejected."""
        mock_path = MagicMock()
        mock_path.exists.return_value = True
        mock_path.is_file.return_value = True
        mock_path.suffix.lower.return_value = ".txt"
        mock_path_class.return_value = mock_path

        error = validate_input_path("/path/to/file.txt", (".pdf", ".docx"))
        assert error is not None
        assert "Unsupported file format" in error

    @patch("gobbler_mcp.utils.file_handler.Path")
    def test_validate_input_path_valid_file(self, mock_path_class):
        """Test that valid files pass validation."""
        mock_path = MagicMock()
        mock_path.exists.return_value = True
        mock_path.is_file.return_value = True
        mock_path.suffix.lower.return_value = ".pdf"
        mock_path_class.return_value = mock_path

        error = validate_input_path("/path/to/file.pdf", (".pdf", ".docx"))
        assert error is None


class TestSaveMarkdownFile:
    """Test markdown file saving functionality."""

    @pytest.mark.asyncio
    @patch("gobbler_mcp.utils.file_handler.Path")
    @patch("gobbler_mcp.utils.file_handler.aiofiles.open")
    async def test_save_markdown_file_success(self, mock_open, mock_path_class):
        """Test successful markdown file save."""
        # Mock file operations
        mock_file = MagicMock()
        mock_file.__aenter__ = AsyncMock(return_value=mock_file)
        mock_file.__aexit__ = AsyncMock()
        mock_file.write = AsyncMock()
        mock_open.return_value = mock_file

        # Mock path
        mock_path = MagicMock()
        mock_path.parent.exists.return_value = True
        mock_path_class.return_value = mock_path

        result = await save_markdown_file("/path/to/output.md", "# Test Content")

        assert result is True
        mock_file.write.assert_called_once_with("# Test Content")

    @pytest.mark.asyncio
    @patch("gobbler_mcp.utils.file_handler.Path")
    @patch("gobbler_mcp.utils.file_handler.aiofiles.open")
    async def test_save_markdown_file_creates_directories(self, mock_open, mock_path_class):
        """Test that parent directories are created if needed."""
        # Mock file operations
        mock_file = MagicMock()
        mock_file.__aenter__ = AsyncMock(return_value=mock_file)
        mock_file.__aexit__ = AsyncMock()
        mock_file.write = AsyncMock()
        mock_open.return_value = mock_file

        # Mock path - parent doesn't exist
        mock_parent = MagicMock()
        mock_parent.exists.return_value = False
        mock_parent.mkdir = MagicMock()
        mock_path = MagicMock()
        mock_path.parent = mock_parent
        mock_path_class.return_value = mock_path

        result = await save_markdown_file("/path/to/output.md", "# Test", create_dirs=True)

        assert result is True
        mock_parent.mkdir.assert_called_once_with(parents=True, exist_ok=True)

    @pytest.mark.asyncio
    @patch("gobbler_mcp.utils.file_handler.Path")
    @patch("gobbler_mcp.utils.file_handler.aiofiles.open")
    async def test_save_markdown_file_permission_error(self, mock_open, mock_path_class):
        """Test handling of permission errors."""
        mock_path = MagicMock()
        mock_path.parent.exists.return_value = True
        mock_path_class.return_value = mock_path

        mock_open.side_effect = PermissionError("Permission denied")

        result = await save_markdown_file("/path/to/output.md", "# Test")

        assert result is False
