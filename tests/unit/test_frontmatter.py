"""Unit tests for frontmatter generation utilities."""

from datetime import UTC, datetime
from unittest.mock import patch

import yaml

from gobbler_core.utils.frontmatter import (
    _escape_yaml_string,
    count_words,
    create_audio_frontmatter,
    create_document_frontmatter,
    create_frontmatter,
    create_webpage_frontmatter,
    create_youtube_frontmatter,
    get_iso8601_timestamp,
)


class TestBasicFrontmatter:
    """Test basic frontmatter creation functionality."""

    def test_create_frontmatter_simple_metadata(self):
        """Test creating frontmatter with simple key-value pairs."""
        metadata = {
            "title": "Test Document",
            "author": "Test Author",
            "count": 42,
        }

        result = create_frontmatter(metadata)

        assert result.startswith("---\n")
        assert result.endswith("---\n")  # Fixed: no double newline
        assert "title: Test Document" in result
        assert "author: Test Author" in result
        assert "count: 42" in result

    def test_create_frontmatter_with_special_characters(self):
        """Test that special characters in strings are properly quoted."""
        metadata = {
            "title": "Title: With Colon",
            "description": "Description # with hash",
        }

        result = create_frontmatter(metadata)

        # Values with colons or hashes should be quoted
        assert '"Title: With Colon"' in result
        assert '"Description # with hash"' in result

    def test_create_frontmatter_with_newlines(self):
        """Test that multiline strings are properly escaped."""
        metadata = {
            "description": "Line 1\nLine 2\nLine 3",
        }

        result = create_frontmatter(metadata)

        # Newlines should be escaped as \n in double-quoted string
        assert r'"Line 1\nLine 2\nLine 3"' in result

        # Should parse correctly
        yaml_content = "\n".join(result.strip().split("\n")[1:-1])
        parsed = yaml.safe_load(yaml_content)
        assert parsed["description"] == "Line 1\nLine 2\nLine 3"

    def test_create_frontmatter_with_quotes(self):
        """Test that double quotes in strings are escaped."""
        metadata = {
            "description": 'He said "hello" to everyone',
        }

        result = create_frontmatter(metadata)

        # Should parse correctly with escaped quotes
        yaml_content = "\n".join(result.strip().split("\n")[1:-1])
        parsed = yaml.safe_load(yaml_content)
        assert parsed["description"] == 'He said "hello" to everyone'

    def test_create_frontmatter_youtube_description_with_special_chars(self):
        """Test YouTube-style descriptions with multiple special characters."""
        metadata = {
            "description": """""Speaker: Test Person
Check out: https://example.com
#hashtag @mention

Multiple
Lines
Here""",
        }

        result = create_frontmatter(metadata)

        # Should parse correctly and neutralize public GitHub mention triggers.
        yaml_content = "\n".join(result.strip().split("\n")[1:-1])
        parsed = yaml.safe_load(yaml_content)
        assert '""Speaker: Test Person' in parsed["description"]
        assert "#hashtag @\u200bmention" in parsed["description"]
        assert "Multiple\nLines\nHere" in parsed["description"]

    def test_create_frontmatter_neutralizes_github_mentions(self):
        """Test frontmatter cannot accidentally trigger GitHub notifications."""
        result = create_frontmatter(
            {"description": "S/O @Ph4seOn3 for the edit; email user@example.com"}
        )

        yaml_content = "\n".join(result.strip().split("\n")[1:-1])
        parsed = yaml.safe_load(yaml_content)
        assert "@Ph4seOn3" not in parsed["description"]
        assert "@\u200bPh4seOn3" in parsed["description"]
        assert "user@example.com" in parsed["description"]

    def test_create_frontmatter_with_different_types(self):
        """Test frontmatter with different value types."""
        metadata = {
            "string_val": "test",
            "int_val": 123,
            "float_val": 45.67,
            "bool_val": True,
            "null_val": None,
        }

        result = create_frontmatter(metadata)

        assert "string_val: test" in result
        assert "int_val: 123" in result
        assert "float_val: 45.67" in result
        assert "bool_val: True" in result
        assert "null_val: null" in result


class TestYamlStringEscaping:
    """Test YAML string escaping functionality."""

    def test_escape_simple_string(self):
        """Test that simple strings are not quoted."""
        result = _escape_yaml_string("Hello World")
        assert result == "Hello World"

    def test_escape_string_with_colon(self):
        """Test that strings with colons are quoted."""
        result = _escape_yaml_string("Key: Value")
        assert result == '"Key: Value"'

    def test_escape_string_with_hash(self):
        """Test that strings with hash are quoted."""
        result = _escape_yaml_string("Test #comment")
        assert result == '"Test #comment"'

    def test_escape_string_with_newlines(self):
        """Test that strings with newlines are properly escaped."""
        result = _escape_yaml_string("Line 1\nLine 2")
        assert result == r'"Line 1\nLine 2"'

    def test_escape_string_with_quotes(self):
        """Test that strings with quotes are properly escaped."""
        result = _escape_yaml_string('He said "hello"')
        assert result == r'"He said \"hello\""'

    def test_escape_string_with_backslash(self):
        """Test that backslashes alone don't require quoting in YAML."""
        result = _escape_yaml_string("path\\to\\file")
        # Backslashes alone don't need quoting, they're literal in YAML
        assert result == "path\\to\\file"

    def test_escape_string_with_backslash_and_special_char(self):
        """Test that backslashes are escaped when string needs quoting."""
        result = _escape_yaml_string("path\\to: file")
        # When quoted due to colon, backslash must be escaped
        assert result == r'"path\\to: file"'

    def test_escape_string_with_leading_special_char(self):
        """Test that strings starting with special chars are quoted."""
        test_cases = [
            (" leading space", '" leading space"'),
            ("'single quote", '"\'single quote"'),
            ('"double quote', '"\\"double quote"'),
            ("-dash", '"-dash"'),
            ("[bracket", '"[bracket"'),
            ("{brace", '"{brace"'),
            ("@at", '"@at"'),
            ("`backtick", '"`backtick"'),
            ("!exclaim", '"!exclaim"'),
            ("&ampersand", '"&ampersand"'),
            ("*asterisk", '"*asterisk"'),
            ("|pipe", '"|pipe"'),
            (">greater", '">greater"'),
            ("%percent", '"%percent"'),
        ]
        for input_str, expected in test_cases:
            result = _escape_yaml_string(input_str)
            assert result == expected, f"Failed for input: {input_str}"

    def test_escape_string_with_trailing_space(self):
        """Test that strings ending with space are quoted."""
        result = _escape_yaml_string("trailing space ")
        assert result == '"trailing space "'

    def test_escape_preserves_tabs(self):
        """Test that tabs are escaped."""
        result = _escape_yaml_string("col1\tcol2")
        assert result == r'"col1\tcol2"'

    def test_escape_preserves_carriage_return(self):
        """Test that carriage returns are escaped."""
        result = _escape_yaml_string("line1\r\nline2")
        assert result == r'"line1\r\nline2"'


class TestTimestampGeneration:
    """Test ISO 8601 timestamp generation."""

    def test_get_iso8601_timestamp_format(self):
        """Test that timestamp is in correct ISO 8601 format."""
        timestamp = get_iso8601_timestamp()

        # Should match format: YYYY-MM-DDTHH:MM:SSZ
        assert len(timestamp) == 20
        assert timestamp[4] == "-"
        assert timestamp[7] == "-"
        assert timestamp[10] == "T"
        assert timestamp[13] == ":"
        assert timestamp[16] == ":"
        assert timestamp[-1] == "Z"

    @patch("gobbler_core.utils.frontmatter.datetime")
    def test_get_iso8601_timestamp_uses_utc(self, mock_datetime):
        """Test that timestamp uses UTC timezone."""
        # Mock datetime to return a fixed time
        mock_now = datetime(2025, 10, 3, 14, 30, 45, tzinfo=UTC)
        mock_datetime.now.return_value = mock_now

        timestamp = get_iso8601_timestamp()

        mock_datetime.now.assert_called_once_with(UTC)
        assert timestamp == "2025-10-03T14:30:45Z"


class TestWordCounting:
    """Test word counting functionality."""

    def test_count_words_simple_text(self):
        """Test word counting with simple text."""
        text = "Hello world this is a test"
        assert count_words(text) == 6

    def test_count_words_empty_string(self):
        """Test word counting with empty string."""
        assert count_words("") == 0

    def test_count_words_with_multiple_spaces(self):
        """Test word counting handles multiple spaces correctly."""
        text = "Hello    world   test"
        # split() handles multiple spaces automatically
        assert count_words(text) == 3

    def test_count_words_with_newlines(self):
        """Test word counting with newlines."""
        text = "Hello\nworld\ntest"
        assert count_words(text) == 3


class TestYouTubeFrontmatter:
    """Test YouTube-specific frontmatter generation."""

    @patch("gobbler_core.utils.frontmatter.get_iso8601_timestamp")
    def test_create_youtube_frontmatter_minimal(self, mock_timestamp):
        """Test YouTube frontmatter with minimal required fields."""
        mock_timestamp.return_value = "2025-10-03T00:00:00Z"

        result = create_youtube_frontmatter(
            video_url="https://youtube.com/watch?v=test123",
            video_id="test123",
            duration=180,
            language="en",
            word_count=500,
        )

        assert '"https://youtube.com/watch?v=test123"' in result  # URLs are quoted
        assert "type: youtube_transcript" in result
        assert "video_id: test123" in result
        assert "duration: 180" in result
        assert "language: en" in result
        assert "word_count: 500" in result
        assert '"2025-10-03T00:00:00Z"' in result  # Timestamps are quoted (contain :)

    @patch("gobbler_core.utils.frontmatter.get_iso8601_timestamp")
    def test_create_youtube_frontmatter_with_optionals(self, mock_timestamp):
        """Test YouTube frontmatter with all optional fields."""
        mock_timestamp.return_value = "2025-10-03T00:00:00Z"

        result = create_youtube_frontmatter(
            video_url="https://youtube.com/watch?v=test123",
            video_id="test123",
            duration=180,
            language="en",
            word_count=500,
            title="Test Video",
            channel="Test Channel",
            thumbnail="https://example.com/thumb.jpg",
            description="Test description",
        )

        assert "title: Test Video" in result
        assert "channel: Test Channel" in result
        assert '"https://example.com/thumb.jpg"' in result  # URLs are quoted
        assert "description: Test description" in result


class TestWebpageFrontmatter:
    """Test webpage-specific frontmatter generation."""

    @patch("gobbler_core.utils.frontmatter.get_iso8601_timestamp")
    def test_create_webpage_frontmatter(self, mock_timestamp):
        """Test webpage frontmatter generation."""
        mock_timestamp.return_value = "2025-10-03T00:00:00Z"

        result = create_webpage_frontmatter(
            url="https://example.com/article",
            title="Test Article",
            word_count=1200,
            conversion_time_ms=5000,
        )

        assert '"https://example.com/article"' in result  # URLs are quoted
        assert "type: webpage" in result
        assert "title: Test Article" in result
        assert "word_count: 1200" in result
        assert "conversion_time_ms: 5000" in result
        assert '"2025-10-03T00:00:00Z"' in result  # Timestamps are quoted


class TestDocumentFrontmatter:
    """Test document-specific frontmatter generation."""

    @patch("gobbler_core.utils.frontmatter.get_iso8601_timestamp")
    def test_create_document_frontmatter(self, mock_timestamp):
        """Test document frontmatter generation."""
        mock_timestamp.return_value = "2025-10-03T00:00:00Z"

        result = create_document_frontmatter(
            file_path="/path/to/document.pdf",
            doc_format="pdf",
            pages=10,
            word_count=3000,
            conversion_time_ms=15000,
        )

        assert "source: /path/to/document.pdf" in result
        assert "type: document" in result
        assert "format: pdf" in result
        assert "pages: 10" in result
        assert "word_count: 3000" in result
        assert "conversion_time_ms: 15000" in result
        assert '"2025-10-03T00:00:00Z"' in result  # Timestamps are quoted


class TestAudioFrontmatter:
    """Test audio-specific frontmatter generation."""

    @patch("gobbler_core.utils.frontmatter.get_iso8601_timestamp")
    def test_create_audio_frontmatter(self, mock_timestamp):
        """Test audio frontmatter generation."""
        mock_timestamp.return_value = "2025-10-03T00:00:00Z"

        result = create_audio_frontmatter(
            file_path="/path/to/audio.mp3",
            duration=240,
            language="en",
            model="small",
            word_count=800,
            conversion_time_ms=12000,
        )

        assert "source: /path/to/audio.mp3" in result
        assert "type: audio_transcript" in result
        assert "duration: 240" in result
        assert "language: en" in result
        assert "model: small" in result
        assert "word_count: 800" in result
        assert "conversion_time_ms: 12000" in result
        assert '"2025-10-03T00:00:00Z"' in result  # Timestamps are quoted
