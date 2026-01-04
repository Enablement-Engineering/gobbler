"""E2E tests for audio and video transcription.

These tests use local audio/video fixtures and run Whisper locally.
No Docker services required.
"""

import pytest

from .helpers import validate_markdown_output

# No network required for local file transcription


class TestAudioTranscription:
    """Tests for audio file transcription."""

    def test_transcribe_short_audio(self, run_gobbler, audio_dir):
        """Test transcribing the short test audio file."""
        audio_file = audio_dir / "test_short.wav"

        result = run_gobbler(
            ["audio", str(audio_file), "--model", "tiny"],
            timeout=60,
        )

        assert result.returncode == 0, f"CLI failed: {result.stderr}"

        validation = validate_markdown_output(result.stdout, "audio_transcript")
        assert validation["valid"], f"Validation errors: {validation['errors']}"

        # Check metadata
        assert "duration" in validation["metadata"]
        assert "language" in validation["metadata"]
        assert validation["metadata"]["model"] == "tiny"

    def test_transcribe_gettysburg_address(self, run_gobbler, audio_dir):
        """Test transcribing the Gettysburg Address (~2 min)."""
        audio_file = audio_dir / "gettysburg_address.mp3"

        result = run_gobbler(
            ["audio", str(audio_file), "--model", "tiny"],
            timeout=120,
        )

        assert result.returncode == 0, f"CLI failed: {result.stderr}"

        validation = validate_markdown_output(result.stdout, "audio_transcript")
        assert validation["valid"], f"Validation errors: {validation['errors']}"

        # Should contain recognizable content from the speech
        # Check for some expected phrases (Whisper may not be perfect)
        assert validation["word_count"] > 100, "Transcript suspiciously short"

    def test_transcribe_to_file(self, run_gobbler, audio_dir, temp_output_dir):
        """Test saving audio transcript to file."""
        audio_file = audio_dir / "test_short.wav"
        output_file = temp_output_dir / "audio_transcript.md"

        result = run_gobbler(
            ["audio", str(audio_file), "--model", "tiny", "-o", str(output_file)],
            timeout=60,
        )

        assert result.returncode == 0, f"CLI failed: {result.stderr}"
        assert output_file.exists(), "Output file not created"

        content = output_file.read_text()
        validation = validate_markdown_output(content, "audio_transcript")
        assert validation["valid"], f"Validation errors: {validation['errors']}"

    def test_transcribe_with_timestamps(self, run_gobbler, audio_dir):
        """Test audio transcription with timestamps."""
        audio_file = audio_dir / "test_short.wav"

        result = run_gobbler(
            ["audio", str(audio_file), "--model", "tiny", "--timestamps"],
            timeout=60,
        )

        assert result.returncode == 0, f"CLI failed: {result.stderr}"

        # Timestamps should be present
        assert "[" in result.stdout
        assert "]" in result.stdout

    def test_nonexistent_file_error(self, run_gobbler):
        """Test error handling for nonexistent file."""
        result = run_gobbler(
            ["audio", "/nonexistent/path/audio.mp3"],
            timeout=30,
        )

        assert result.returncode != 0, "Should fail for nonexistent file"


@pytest.mark.slow
class TestAudioLongerContent:
    """Tests for longer audio content."""

    def test_transcribe_mlk_dream(self, run_gobbler, audio_dir):
        """Test transcribing MLK 'I Have a Dream' excerpt (~3 min)."""
        audio_file = audio_dir / "mlk_dream.mp3"

        result = run_gobbler(
            ["audio", str(audio_file), "--model", "tiny"],
            timeout=180,
        )

        assert result.returncode == 0, f"CLI failed: {result.stderr}"

        validation = validate_markdown_output(result.stdout, "audio_transcript")
        assert validation["valid"], f"Validation errors: {validation['errors']}"
        assert validation["word_count"] > 200, "Transcript too short for 3 min audio"

    def test_transcribe_art_of_war(self, run_gobbler, audio_dir):
        """Test transcribing Art of War chapter (~8 min)."""
        audio_file = audio_dir / "art_of_war.mp3"

        result = run_gobbler(
            ["audio", str(audio_file), "--model", "tiny"],
            timeout=300,
        )

        assert result.returncode == 0, f"CLI failed: {result.stderr}"

        validation = validate_markdown_output(result.stdout, "audio_transcript")
        assert validation["valid"], f"Validation errors: {validation['errors']}"
        assert validation["word_count"] > 500, "Transcript too short for 8 min audio"


class TestVideoTranscription:
    """Tests for video file transcription (extracts audio and transcribes)."""

    @pytest.mark.slow
    def test_transcribe_ted_video(self, run_gobbler, video_dir):
        """Test transcribing the TED talk video file."""
        video_file = video_dir / "ted_chatgpt_language.mp4"

        result = run_gobbler(
            ["audio", str(video_file), "--model", "tiny"],
            timeout=300,
        )

        assert result.returncode == 0, f"CLI failed: {result.stderr}"

        validation = validate_markdown_output(result.stdout, "audio_transcript")
        assert validation["valid"], f"Validation errors: {validation['errors']}"

        # TED talk should have substantial content
        assert validation["word_count"] > 500, "Video transcript too short"


class TestWhisperModels:
    """Test different Whisper model sizes."""

    @pytest.mark.parametrize("model", ["tiny", "base"])
    def test_model_sizes(self, run_gobbler, audio_dir, model):
        """Test that different model sizes work."""
        audio_file = audio_dir / "test_short.wav"

        result = run_gobbler(
            ["audio", str(audio_file), "--model", model],
            timeout=120,
        )

        assert result.returncode == 0, f"CLI failed with model {model}: {result.stderr}"

        validation = validate_markdown_output(result.stdout, "audio_transcript")
        assert validation["valid"], f"Validation errors: {validation['errors']}"
        assert validation["metadata"]["model"] == model
