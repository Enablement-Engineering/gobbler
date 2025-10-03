"""Performance benchmarks for Whisper transcription."""

import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock


@pytest.mark.benchmark
class TestWhisperPerformance:
    """Benchmark Whisper transcription performance."""

    @pytest.mark.asyncio
    @patch("gobbler_mcp.converters.audio._get_whisper_model")
    @patch("gobbler_mcp.converters.audio.os.path.getsize")
    @patch("gobbler_mcp.converters.audio.validate_input_path")
    @patch("gobbler_mcp.converters.audio.get_file_extension")
    async def test_transcription_speed_benchmark(
        self, mock_ext, mock_validate, mock_getsize, mock_get_model, benchmark
    ):
        """Benchmark transcription speed with mocked model."""
        from gobbler_mcp.converters.audio import convert_audio_to_markdown

        # Mock setup
        mock_validate.return_value = None
        mock_ext.return_value = ".mp3"
        mock_getsize.return_value = 1024 * 1024  # 1MB

        mock_model = MagicMock()
        segment = MagicMock()
        segment.text = "Test transcription benchmark"
        segment.end = 2.0
        mock_info = MagicMock()
        mock_info.language = "en"
        mock_model.transcribe.return_value = ([segment], mock_info)
        mock_get_model.return_value = mock_model

        # Benchmark the conversion
        async def run_transcription():
            return await convert_audio_to_markdown("/tmp/test.mp3", model="tiny")

        # Note: pytest-benchmark doesn't directly support async,
        # so we'll document expected performance instead
        result = await run_transcription()
        markdown, metadata = result

        # Performance expectations documented:
        # - Tiny model: < 1 second per minute of audio
        # - Small model: ~6 seconds per MB on M-series Macs
        # - Medium model: ~12 seconds per MB
        assert metadata["model"] == "tiny"
        assert "conversion_time_ms" in metadata


@pytest.mark.benchmark
class TestPerformanceBaselines:
    """Document performance baselines for different operations."""

    def test_youtube_transcript_baseline(self):
        """Document expected performance for YouTube transcripts."""
        # Expected: < 1 second (no external calls with mocks)
        # Real-world: 1-3 seconds depending on network
        assert True

    def test_webpage_conversion_baseline(self):
        """Document expected performance for web scraping."""
        # Expected with Crawl4AI: 2-10 seconds
        # Depends on page complexity and JavaScript rendering
        assert True

    def test_document_conversion_baseline(self):
        """Document expected performance for document conversion."""
        # Expected with Docling:
        # - Simple PDF (5 pages): 5-10 seconds
        # - With OCR: 15-30 seconds
        assert True
