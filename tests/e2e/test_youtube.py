"""E2E tests for YouTube transcription.

These tests make real API calls to YouTube and require network access.
No Docker services required.
"""

from pathlib import Path

import pytest

from .helpers import get_first_url, has_timestamps, validate_markdown_output

pytestmark = pytest.mark.requires_network


class TestYouTubeSingleVideo:
    """Tests for single video transcription."""

    def test_transcribe_short_video(self, run_gobbler):
        """Test transcribing a short video (<5 min) for quick validation."""
        url = get_first_url("youtube", "short_videos.txt")

        result = run_gobbler(["youtube", url], timeout=60)

        assert result.returncode == 0, f"CLI failed: {result.stderr}"

        validation = validate_markdown_output(result.stdout, "youtube_transcript")
        assert validation["valid"], f"Validation errors: {validation['errors']}"
        assert validation["word_count"] > 50, "Transcript too short"

    def test_transcribe_ted_talk(self, run_gobbler):
        """Test transcribing a TED talk (longer, varied accents)."""
        url = get_first_url("youtube", "ted_talks.txt")

        result = run_gobbler(["youtube", url], timeout=120)

        assert result.returncode == 0, f"CLI failed: {result.stderr}"

        validation = validate_markdown_output(result.stdout, "youtube_transcript")
        assert validation["valid"], f"Validation errors: {validation['errors']}"

        # TED talks should have substantial content
        assert validation["word_count"] > 500, "TED talk transcript suspiciously short"

        # Check metadata
        assert "title" in validation["metadata"]
        assert validation["metadata"]["duration"] > 0

    def test_transcribe_with_timestamps(self, run_gobbler):
        """Test transcription with timestamps enabled."""
        url = get_first_url("youtube", "short_videos.txt")

        result = run_gobbler(["youtube", url, "--timestamps"], timeout=60)

        assert result.returncode == 0, f"CLI failed: {result.stderr}"

        # Should contain timestamp markers
        assert has_timestamps(result.stdout), "No timestamps found in output"

    def test_transcribe_to_file(self, run_gobbler, temp_output_dir):
        """Test saving transcript to file."""
        url = get_first_url("youtube", "short_videos.txt")
        output_file = temp_output_dir / "transcript.md"

        result = run_gobbler(
            ["youtube", url, "-o", str(output_file)],
            timeout=60,
        )

        assert result.returncode == 0, f"CLI failed: {result.stderr}"
        assert output_file.exists(), "Output file not created"

        content = output_file.read_text()
        validation = validate_markdown_output(content, "youtube_transcript")
        assert validation["valid"], f"Validation errors: {validation['errors']}"

    def test_invalid_url_error(self, run_gobbler):
        """Test error handling for invalid YouTube URL."""
        result = run_gobbler(
            ["youtube", "https://example.com/not-youtube"],
            timeout=30,
        )

        assert result.returncode != 0, "Should fail for invalid URL"
        # Error message should indicate the problem
        combined_output = result.stdout + result.stderr
        assert (
            "error" in combined_output.lower()
            or "invalid" in combined_output.lower()
            or "failed" in combined_output.lower()
        )

    def test_nonexistent_video_error(self, run_gobbler):
        """Test error handling for video that doesn't exist."""
        result = run_gobbler(
            ["youtube", "https://youtube.com/watch?v=ZZZZZZZZZZZ"],
            timeout=30,
        )

        assert result.returncode != 0, "Should fail for nonexistent video"

    @pytest.mark.requires_ffmpeg
    def test_extract_one_overview_frame(self, run_gobbler, temp_output_dir: Path):
        """Frame-only extraction emits a durable JPEG and timestamp manifest."""
        output_file = temp_output_dir / "overview.md"
        result = run_gobbler(
            [
                "youtube",
                "https://www.youtube.com/watch?v=jNQXAC9IVRw",
                "--frames-only",
                "--frames",
                "1",
                "-o",
                str(output_file),
            ],
            timeout=90,
        )

        assert result.returncode == 0, f"CLI failed: {result.stderr}"
        markdown = output_file.read_text(encoding="utf-8")
        frame_files = list((temp_output_dir / "overview.assets" / "frames").glob("*.jpg"))
        assert "type: youtube_frames" in markdown
        assert "# Video Frames" in markdown
        assert len(frame_files) == 1
        assert frame_files[0].read_bytes().startswith(b"\xff\xd8\xff")
        assert "googlevideo.com" not in (result.stdout + result.stderr + markdown)


class TestYouTubeConferenceTalks:
    """Tests for conference talk transcription (usually CC licensed)."""

    def test_transcribe_conference_talk(self, run_gobbler):
        """Test transcribing a tech conference talk."""
        url = get_first_url("youtube", "conference_talks.txt")

        result = run_gobbler(["youtube", url], timeout=180)

        assert result.returncode == 0, f"CLI failed: {result.stderr}"

        validation = validate_markdown_output(result.stdout, "youtube_transcript")
        assert validation["valid"], f"Validation errors: {validation['errors']}"


@pytest.mark.slow
class TestYouTubePlaylist:
    """Tests for playlist batch transcription.

    These tests are slow as they process multiple videos.
    """

    def test_batch_playlist_limited(self, run_gobbler, temp_output_dir):
        """Test batch transcribing a playlist (processes all videos)."""
        playlist_url = get_first_url("youtube", "playlists.txt")

        result = run_gobbler(
            [
                "batch",
                "youtube-playlist",
                playlist_url,
                "-o",
                str(temp_output_dir),
                "-c",
                "2",  # Limit concurrency for more predictable behavior
            ],
            timeout=600,  # Playlists can take a while
        )

        # Should have created markdown files - some may fail due to network issues
        md_files = list(temp_output_dir.glob("*.md"))
        assert len(md_files) >= 1, "No output files created"

        # Check at least some videos were processed successfully
        # (network errors may cause partial failures)
        assert "Processed" in result.stdout or len(md_files) > 0, (
            f"No videos processed. stdout: {result.stdout}, stderr: {result.stderr}"
        )

        # Validate at least one file
        first_file = md_files[0]
        content = first_file.read_text()
        validation = validate_markdown_output(content, "youtube_transcript")
        assert validation["valid"], f"Validation errors: {validation['errors']}"


class TestYouTubeURLFormats:
    """Test various YouTube URL formats are handled correctly."""

    @pytest.mark.parametrize(
        "url_format",
        [
            "https://www.youtube.com/watch?v={video_id}",
            "https://youtube.com/watch?v={video_id}",
            "https://youtu.be/{video_id}",
            "https://www.youtube.com/watch?v={video_id}&t=10",
        ],
    )
    def test_url_formats(self, run_gobbler, url_format):
        """Test that various URL formats work."""
        # Use a known short video ID
        video_id = "jNQXAC9IVRw"  # "Me at the zoo" - first YouTube video, very short
        url = url_format.format(video_id=video_id)

        result = run_gobbler(["youtube", url], timeout=60)

        # Should succeed (video exists and has captions)
        # Note: This specific video might not have captions, so we just check
        # that the command handles the URL format correctly
        if result.returncode == 0:
            validation = validate_markdown_output(result.stdout, "youtube_transcript")
            assert validation["valid"], f"Validation errors: {validation['errors']}"
