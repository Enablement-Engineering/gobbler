"""Unit tests for audio/video transcription module."""

import os
import pytest
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch, mock_open
import subprocess

from gobbler_mcp.converters.audio import (
    _extract_audio,
    _get_whisper_model,
    convert_audio_to_markdown,
    SUPPORTED_EXTENSIONS,
    VALID_MODELS,
    MAX_FILE_SIZE_BYTES,
)


class TestAudioExtraction:
    """Test ffmpeg audio extraction from video files."""

    @pytest.mark.asyncio
    @patch("gobbler_mcp.converters.audio.subprocess.run")
    @patch("gobbler_mcp.converters.audio.tempfile.mkstemp")
    @patch("gobbler_mcp.converters.audio.os.close")
    async def test_extract_audio_success(self, mock_close, mock_mkstemp, mock_run):
        """Test successful audio extraction from video."""
        # Mock temp file creation
        mock_mkstemp.return_value = (999, "/tmp/gobbler_audio_test.mp3")

        # Mock successful ffmpeg run
        mock_run.return_value = MagicMock(returncode=0, stderr="", stdout="")

        result = await _extract_audio("/path/to/video.mp4")

        assert result == "/tmp/gobbler_audio_test.mp3"
        mock_close.assert_called_once_with(999)

        # Verify ffmpeg command
        call_args = mock_run.call_args[0][0]
        assert call_args[0] == "ffmpeg"
        assert "-i" in call_args
        assert "/path/to/video.mp4" in call_args
        assert "-vn" in call_args  # No video
        assert "-acodec" in call_args
        assert "libmp3lame" in call_args
        assert "-ar" in call_args
        assert "16000" in call_args  # 16kHz
        assert "-ac" in call_args
        assert "1" in call_args  # Mono

    @pytest.mark.asyncio
    @patch("gobbler_mcp.converters.audio.subprocess.run")
    @patch("gobbler_mcp.converters.audio.tempfile.mkstemp")
    @patch("gobbler_mcp.converters.audio.os.close")
    @patch("gobbler_mcp.converters.audio.os.path.exists")
    @patch("gobbler_mcp.converters.audio.os.unlink")
    async def test_extract_audio_ffmpeg_failure(
        self, mock_unlink, mock_exists, mock_close, mock_mkstemp, mock_run
    ):
        """Test handling of ffmpeg extraction failure."""
        mock_mkstemp.return_value = (999, "/tmp/gobbler_audio_test.mp3")
        mock_exists.return_value = True

        # Mock ffmpeg failure
        mock_run.return_value = MagicMock(
            returncode=1, stderr="ffmpeg error", stdout=""
        )

        with pytest.raises(RuntimeError, match="ffmpeg audio extraction failed"):
            await _extract_audio("/path/to/video.mp4")

        # Verify temp file cleanup (may be called multiple times in error handling)
        mock_unlink.assert_called_with("/tmp/gobbler_audio_test.mp3")

    @pytest.mark.asyncio
    @patch("gobbler_mcp.converters.audio.subprocess.run")
    @patch("gobbler_mcp.converters.audio.tempfile.mkstemp")
    @patch("gobbler_mcp.converters.audio.os.close")
    @patch("gobbler_mcp.converters.audio.os.path.exists")
    @patch("gobbler_mcp.converters.audio.os.unlink")
    async def test_extract_audio_timeout(
        self, mock_unlink, mock_exists, mock_close, mock_mkstemp, mock_run
    ):
        """Test handling of ffmpeg timeout."""
        mock_mkstemp.return_value = (999, "/tmp/gobbler_audio_test.mp3")
        mock_exists.return_value = True

        # Mock timeout
        mock_run.side_effect = subprocess.TimeoutExpired(cmd="ffmpeg", timeout=300)

        with pytest.raises(RuntimeError, match="Audio extraction timed out"):
            await _extract_audio("/path/to/video.mp4")

        mock_unlink.assert_called_once()

    @pytest.mark.asyncio
    @patch("gobbler_mcp.converters.audio.subprocess.run")
    @patch("gobbler_mcp.converters.audio.tempfile.mkstemp")
    @patch("gobbler_mcp.converters.audio.os.close")
    @patch("gobbler_mcp.converters.audio.os.path.exists")
    @patch("gobbler_mcp.converters.audio.os.unlink")
    async def test_extract_audio_ffmpeg_not_found(
        self, mock_unlink, mock_exists, mock_close, mock_mkstemp, mock_run
    ):
        """Test handling when ffmpeg is not installed."""
        mock_mkstemp.return_value = (999, "/tmp/gobbler_audio_test.mp3")
        mock_exists.return_value = True

        # Mock FileNotFoundError (ffmpeg not installed)
        mock_run.side_effect = FileNotFoundError("ffmpeg not found")

        with pytest.raises(RuntimeError, match="ffmpeg not found"):
            await _extract_audio("/path/to/video.mp4")

        mock_unlink.assert_called_once()


class TestWhisperModelLoading:
    """Test Whisper model initialization and caching."""

    @patch("gobbler_mcp.converters.audio.WhisperModel")
    def test_get_whisper_model_initialization(self, mock_whisper_class):
        """Test Whisper model is initialized correctly."""
        mock_model = MagicMock()
        mock_whisper_class.return_value = mock_model

        # Clear global cache
        import gobbler_mcp.converters.audio as audio_module
        audio_module._whisper_model = None
        audio_module._current_model_size = None

        result = _get_whisper_model("small")

        assert result == mock_model
        mock_whisper_class.assert_called_once_with(
            "small",
            device="cpu",
            compute_type="auto"
        )

    @patch("gobbler_mcp.converters.audio.WhisperModel")
    def test_get_whisper_model_caching(self, mock_whisper_class):
        """Test that Whisper model is cached and reused."""
        mock_model = MagicMock()
        mock_whisper_class.return_value = mock_model

        # Clear global cache
        import gobbler_mcp.converters.audio as audio_module
        audio_module._whisper_model = None
        audio_module._current_model_size = None

        # First call - should initialize
        result1 = _get_whisper_model("small")
        call_count_after_first = mock_whisper_class.call_count

        # Second call with same size - should use cache
        result2 = _get_whisper_model("small")
        call_count_after_second = mock_whisper_class.call_count

        assert result1 == result2
        assert call_count_after_first == call_count_after_second  # No new initialization

    @patch("gobbler_mcp.converters.audio.WhisperModel")
    def test_get_whisper_model_reload_on_size_change(self, mock_whisper_class):
        """Test that model is reloaded when size changes."""
        mock_model_small = MagicMock()
        mock_model_large = MagicMock()
        mock_whisper_class.side_effect = [mock_model_small, mock_model_large]

        # Clear global cache
        import gobbler_mcp.converters.audio as audio_module
        audio_module._whisper_model = None
        audio_module._current_model_size = None

        # First call with 'small'
        result1 = _get_whisper_model("small")

        # Second call with 'large' - should reload
        result2 = _get_whisper_model("large")

        assert result1 == mock_model_small
        assert result2 == mock_model_large
        assert mock_whisper_class.call_count == 2


class TestAudioConversion:
    """Test full audio/video to markdown conversion."""

    @pytest.mark.asyncio
    @patch("gobbler_mcp.converters.audio._get_whisper_model")
    @patch("gobbler_mcp.converters.audio.os.path.getsize")
    @patch("gobbler_mcp.converters.audio.validate_input_path")
    @patch("gobbler_mcp.converters.audio.get_file_extension")
    async def test_convert_audio_basic(
        self, mock_get_ext, mock_validate, mock_getsize, mock_get_model
    ):
        """Test basic audio conversion with mocked Whisper."""
        # Mock file validation
        mock_validate.return_value = None  # No error
        mock_get_ext.return_value = ".mp3"
        mock_getsize.return_value = 1024 * 1024  # 1MB (below threshold)

        # Mock Whisper model
        mock_model = MagicMock()

        # Mock segment objects
        segment1 = MagicMock()
        segment1.text = "Hello world"
        segment1.end = 2.5

        segment2 = MagicMock()
        segment2.text = "This is a test"
        segment2.end = 5.5

        # Mock transcribe return value
        mock_info = MagicMock()
        mock_info.language = "en"
        mock_model.transcribe.return_value = ([segment1, segment2], mock_info)

        mock_get_model.return_value = mock_model

        # Execute conversion
        markdown, metadata = await convert_audio_to_markdown(
            "/path/to/test_audio.mp3",
            model="small",
            language="auto"
        )

        # Verify markdown structure
        assert "---" in markdown  # Frontmatter
        assert "type: audio_transcript" in markdown  # Fixed: correct type name
        assert "# Audio Transcript" in markdown
        assert "Hello world This is a test" in markdown

        # Verify metadata
        assert metadata["file_path"] == "/path/to/test_audio.mp3"
        assert metadata["language"] == "en"
        assert metadata["model"] == "small"
        assert metadata["duration"] == 5
        assert metadata["word_count"] > 0

        # Verify model was called correctly
        mock_get_model.assert_called_once_with("small")
        mock_model.transcribe.assert_called_once()

    @pytest.mark.asyncio
    @patch("gobbler_mcp.converters.audio.validate_input_path")
    async def test_convert_audio_invalid_file_path(self, mock_validate):
        """Test that invalid file path raises ValueError."""
        mock_validate.return_value = "File does not exist"

        with pytest.raises(ValueError, match="File does not exist"):
            await convert_audio_to_markdown("/nonexistent/file.mp3")

    @pytest.mark.asyncio
    @patch("gobbler_mcp.converters.audio.validate_input_path")
    async def test_convert_audio_invalid_model(self, mock_validate):
        """Test that invalid model name raises ValueError."""
        mock_validate.return_value = None

        with pytest.raises(ValueError, match="Invalid model"):
            await convert_audio_to_markdown(
                "/path/to/test_audio.mp3",
                model="invalid_model"
            )

    @pytest.mark.asyncio
    @patch("gobbler_mcp.converters.audio._extract_audio")
    @patch("gobbler_mcp.converters.audio._get_whisper_model")
    @patch("gobbler_mcp.converters.audio.os.path.getsize")
    @patch("gobbler_mcp.converters.audio.validate_input_path")
    @patch("gobbler_mcp.converters.audio.get_file_extension")
    @patch("gobbler_mcp.converters.audio.os.path.exists")
    @patch("gobbler_mcp.converters.audio.os.unlink")
    async def test_convert_large_video_extracts_audio(
        self, mock_unlink, mock_exists, mock_get_ext, mock_validate,
        mock_getsize, mock_get_model, mock_extract
    ):
        """Test that large video files trigger audio extraction."""
        # Mock file validation
        mock_validate.return_value = None
        mock_get_ext.return_value = ".mp4"

        # Mock large file size (> 50MB)
        mock_getsize.side_effect = [
            MAX_FILE_SIZE_BYTES + 1,  # Original file
            1024 * 1024,  # Extracted audio
        ]

        # Mock audio extraction
        mock_extract.return_value = "/tmp/extracted_audio.mp3"
        mock_exists.return_value = True

        # Mock Whisper model
        mock_model = MagicMock()
        segment = MagicMock()
        segment.text = "Test"
        segment.end = 2.0
        mock_info = MagicMock()
        mock_info.language = "en"
        mock_model.transcribe.return_value = ([segment], mock_info)
        mock_get_model.return_value = mock_model

        # Execute conversion
        await convert_audio_to_markdown("/path/to/large_video.mp4")

        # Verify audio extraction was called
        mock_extract.assert_called_once_with("/path/to/large_video.mp4")

        # Verify transcribe was called with extracted file
        call_args = mock_model.transcribe.call_args[0]
        assert call_args[0] == "/tmp/extracted_audio.mp3"

        # Verify temp file cleanup
        mock_unlink.assert_called()

    @pytest.mark.asyncio
    @patch("gobbler_mcp.converters.audio._get_whisper_model")
    @patch("gobbler_mcp.converters.audio.os.path.getsize")
    @patch("gobbler_mcp.converters.audio.validate_input_path")
    @patch("gobbler_mcp.converters.audio.get_file_extension")
    async def test_convert_audio_empty_transcript_raises_error(
        self, mock_get_ext, mock_validate, mock_getsize, mock_get_model
    ):
        """Test that empty transcription raises RuntimeError."""
        mock_validate.return_value = None
        mock_get_ext.return_value = ".mp3"
        mock_getsize.return_value = 1024 * 1024

        # Mock Whisper model returning no segments
        mock_model = MagicMock()
        mock_info = MagicMock()
        mock_info.language = "en"
        mock_model.transcribe.return_value = ([], mock_info)
        mock_get_model.return_value = mock_model

        with pytest.raises(RuntimeError, match="Unable to detect speech"):
            await convert_audio_to_markdown("/path/to/silent_audio.mp3")

    @pytest.mark.asyncio
    @patch("gobbler_mcp.converters.audio._get_whisper_model")
    @patch("gobbler_mcp.converters.audio.os.path.getsize")
    @patch("gobbler_mcp.converters.audio.validate_input_path")
    @patch("gobbler_mcp.converters.audio.get_file_extension")
    async def test_convert_audio_with_specific_language(
        self, mock_get_ext, mock_validate, mock_getsize, mock_get_model
    ):
        """Test audio conversion with specific language code."""
        mock_validate.return_value = None
        mock_get_ext.return_value = ".mp3"
        mock_getsize.return_value = 1024 * 1024

        # Mock Whisper model
        mock_model = MagicMock()
        segment = MagicMock()
        segment.text = "Bonjour le monde"
        segment.end = 2.0
        mock_info = MagicMock()
        mock_info.language = "fr"
        mock_model.transcribe.return_value = ([segment], mock_info)
        mock_get_model.return_value = mock_model

        # Execute with French language
        markdown, metadata = await convert_audio_to_markdown(
            "/path/to/french_audio.mp3",
            language="fr"
        )

        # Verify language parameter passed to transcribe
        call_kwargs = mock_model.transcribe.call_args[1]
        assert call_kwargs["language"] == "fr"

        assert metadata["language"] == "fr"
        assert "Bonjour le monde" in markdown

    @pytest.mark.asyncio
    @patch("gobbler_mcp.converters.audio._get_whisper_model")
    @patch("gobbler_mcp.converters.audio.os.path.getsize")
    @patch("gobbler_mcp.converters.audio.validate_input_path")
    @patch("gobbler_mcp.converters.audio.get_file_extension")
    async def test_convert_audio_model_loading_failure(
        self, mock_get_ext, mock_validate, mock_getsize, mock_get_model
    ):
        """Test handling of Whisper model loading failure."""
        mock_validate.return_value = None
        mock_get_ext.return_value = ".mp3"
        mock_getsize.return_value = 1024 * 1024

        # Mock model loading failure
        mock_get_model.side_effect = Exception("Model download failed")

        with pytest.raises(RuntimeError, match="Failed to load Whisper model"):
            await convert_audio_to_markdown("/path/to/test_audio.mp3")


class TestSupportedFormats:
    """Test supported audio/video format constants."""

    def test_supported_extensions_include_audio_formats(self):
        """Test that common audio formats are supported."""
        assert ".mp3" in SUPPORTED_EXTENSIONS
        assert ".wav" in SUPPORTED_EXTENSIONS
        assert ".flac" in SUPPORTED_EXTENSIONS
        assert ".m4a" in SUPPORTED_EXTENSIONS

    def test_supported_extensions_include_video_formats(self):
        """Test that common video formats are supported."""
        assert ".mp4" in SUPPORTED_EXTENSIONS
        assert ".mov" in SUPPORTED_EXTENSIONS
        assert ".avi" in SUPPORTED_EXTENSIONS
        assert ".mkv" in SUPPORTED_EXTENSIONS

    def test_valid_models_include_all_sizes(self):
        """Test that all Whisper model sizes are valid."""
        assert "tiny" in VALID_MODELS
        assert "base" in VALID_MODELS
        assert "small" in VALID_MODELS
        assert "medium" in VALID_MODELS
        assert "large" in VALID_MODELS
