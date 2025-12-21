"""Unit tests for queue management utilities."""

import subprocess
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import fakeredis
import pytest
from rq import Queue
from rq.job import Job


class TestEstimateTaskDuration:
    """Test task duration estimation functions."""

    def test_transcribe_audio_model_speed_tiny(self):
        """Test transcription estimate for tiny model."""
        from gobbler_mcp.utils.queue import estimate_task_duration

        with patch("gobbler_mcp.utils.queue.get_media_duration", return_value=600):
            # 600s audio * 0.15 (tiny) + 30s overhead = 120s
            result = estimate_task_duration(
                "transcribe_audio", file_path="/test/audio.mp3", model="tiny"
            )
            assert result == 120

    def test_transcribe_audio_model_speed_small(self):
        """Test transcription estimate for small model."""
        from gobbler_mcp.utils.queue import estimate_task_duration

        with patch("gobbler_mcp.utils.queue.get_media_duration", return_value=600):
            # 600s audio * 0.33 (small) + 30s overhead = 228s
            result = estimate_task_duration(
                "transcribe_audio", file_path="/test/audio.mp3", model="small"
            )
            assert result == 228

    def test_transcribe_audio_model_speed_large(self):
        """Test transcription estimate for large model."""
        from gobbler_mcp.utils.queue import estimate_task_duration

        with patch("gobbler_mcp.utils.queue.get_media_duration", return_value=600):
            # 600s audio * 0.80 (large) + 30s overhead = 510s
            result = estimate_task_duration(
                "transcribe_audio", file_path="/test/audio.mp3", model="large"
            )
            assert result == 510

    def test_transcribe_audio_fallback_to_file_size(self):
        """Test fallback to file size when duration unavailable."""
        from gobbler_mcp.utils.queue import estimate_task_duration

        with patch("gobbler_mcp.utils.queue.get_media_duration", return_value=0):
            # 50MB * 6 = 300s
            result = estimate_task_duration(
                "transcribe_audio", file_path="/test/audio.mp3", file_size_mb=50
            )
            assert result == 300

    def test_transcribe_audio_default_estimate(self):
        """Test default estimate when no info available."""
        from gobbler_mcp.utils.queue import estimate_task_duration

        with patch("gobbler_mcp.utils.queue.get_media_duration", return_value=0):
            result = estimate_task_duration("transcribe_audio")
            assert result == 120

    def test_download_youtube_quality_360p(self):
        """Test download estimate for 360p quality."""
        from gobbler_mcp.utils.queue import estimate_task_duration

        result = estimate_task_duration("download_youtube", quality="360p")
        assert result == 60

    def test_download_youtube_quality_1080p(self):
        """Test download estimate for 1080p quality."""
        from gobbler_mcp.utils.queue import estimate_task_duration

        result = estimate_task_duration("download_youtube", quality="1080p")
        assert result == 180

    def test_download_youtube_quality_best(self):
        """Test download estimate for best quality."""
        from gobbler_mcp.utils.queue import estimate_task_duration

        result = estimate_task_duration("download_youtube", quality="best")
        assert result == 180

    def test_unknown_task_type_returns_default(self):
        """Test that unknown task types return default estimate."""
        from gobbler_mcp.utils.queue import estimate_task_duration

        result = estimate_task_duration("unknown_task")
        assert result == 120


class TestShouldQueueTask:
    """Test task queueing decision logic."""

    def test_auto_queue_disabled_returns_false(self):
        """Test that auto_queue=False always returns False."""
        from gobbler_mcp.utils.queue import should_queue_task

        result = should_queue_task("transcribe_audio", auto_queue=False, file_size_mb=1000)
        assert result is False

    def test_auto_queue_below_threshold(self):
        """Test short tasks don't get queued."""
        from gobbler_mcp.utils.queue import should_queue_task

        with patch("gobbler_mcp.utils.queue.estimate_task_duration", return_value=60):
            result = should_queue_task("transcribe_audio", auto_queue=True)
            assert result is False

    def test_auto_queue_above_threshold(self):
        """Test long tasks get queued."""
        from gobbler_mcp.utils.queue import should_queue_task

        with patch("gobbler_mcp.utils.queue.estimate_task_duration", return_value=200):
            result = should_queue_task("transcribe_audio", auto_queue=True)
            assert result is True

    def test_auto_queue_at_threshold(self):
        """Test tasks at exactly threshold don't get queued."""
        from gobbler_mcp.utils.queue import should_queue_task

        # Threshold is 105 seconds, at threshold should not queue
        with patch("gobbler_mcp.utils.queue.estimate_task_duration", return_value=105):
            result = should_queue_task("transcribe_audio", auto_queue=True)
            assert result is False


class TestGetMediaDuration:
    """Test media duration extraction."""

    def test_successful_duration_extraction(self):
        """Test successful ffprobe duration extraction."""
        from gobbler_mcp.utils.queue import get_media_duration

        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "123.456"

        with patch("gobbler_mcp.utils.queue.subprocess.run", return_value=mock_result):
            result = get_media_duration("/test/audio.mp3")
            assert result == 123.456

    def test_ffprobe_failure_returns_zero(self):
        """Test ffprobe failure returns 0."""
        from gobbler_mcp.utils.queue import get_media_duration

        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stderr = "error"

        with patch("gobbler_mcp.utils.queue.subprocess.run", return_value=mock_result):
            result = get_media_duration("/test/audio.mp3")
            assert result == 0

    def test_ffprobe_timeout_returns_zero(self):
        """Test ffprobe timeout returns 0."""
        from gobbler_mcp.utils.queue import get_media_duration

        with patch(
            "gobbler_mcp.utils.queue.subprocess.run",
            side_effect=subprocess.TimeoutExpired(cmd="ffprobe", timeout=10),
        ):
            result = get_media_duration("/test/audio.mp3")
            assert result == 0

    def test_ffprobe_not_found_raises(self):
        """Test ffprobe not found raises RuntimeError."""
        from gobbler_mcp.utils.queue import get_media_duration

        with patch("gobbler_mcp.utils.queue.subprocess.run", side_effect=FileNotFoundError()):
            with pytest.raises(RuntimeError, match="ffprobe not found"):
                get_media_duration("/test/audio.mp3")

    def test_empty_output_returns_zero(self):
        """Test empty ffprobe output returns 0."""
        from gobbler_mcp.utils.queue import get_media_duration

        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = ""

        with patch("gobbler_mcp.utils.queue.subprocess.run", return_value=mock_result):
            result = get_media_duration("/test/audio.mp3")
            assert result == 0


class TestRedisConnection:
    """Test Redis connection management."""

    def test_get_redis_connection_creates_connection(self):
        """Test that get_redis_connection creates a new connection."""
        from gobbler_mcp.utils import queue as queue_module

        # Reset global connection
        queue_module._redis_conn = None

        fake_redis = fakeredis.FakeRedis()

        with patch("gobbler_mcp.utils.queue.get_config") as mock_config:
            mock_config.return_value.data = {"redis": {"host": "localhost", "port": 6379, "db": 0}}
            with patch("gobbler_mcp.utils.queue.redis.Redis", return_value=fake_redis):
                conn = queue_module.get_redis_connection()
                assert conn is not None

    def test_get_redis_connection_reuses_connection(self):
        """Test that subsequent calls reuse existing connection."""
        from gobbler_mcp.utils import queue as queue_module

        fake_redis = fakeredis.FakeRedis()
        queue_module._redis_conn = fake_redis

        conn = queue_module.get_redis_connection()
        assert conn is fake_redis

    def test_get_redis_connection_failure_raises(self):
        """Test that connection failure raises ConnectionError."""
        import redis

        from gobbler_mcp.utils import queue as queue_module

        # Reset global connection
        queue_module._redis_conn = None

        with patch("gobbler_mcp.utils.queue.get_config") as mock_config:
            mock_config.return_value.data = {"redis": {"host": "localhost", "port": 6379, "db": 0}}
            with patch(
                "gobbler_mcp.utils.queue.redis.Redis",
                side_effect=redis.ConnectionError("Connection refused"),
            ):
                with pytest.raises(ConnectionError, match="Redis connection failed"):
                    queue_module.get_redis_connection()


class TestGetQueue:
    """Test queue retrieval."""

    def test_get_queue_returns_queue(self):
        """Test get_queue returns an RQ Queue."""
        from gobbler_mcp.utils import queue as queue_module

        fake_redis = fakeredis.FakeRedis()
        queue_module._redis_conn = fake_redis

        with patch("gobbler_mcp.utils.queue.get_redis_connection", return_value=fake_redis):
            q = queue_module.get_queue("test_queue")
            assert isinstance(q, Queue)
            assert q.name == "test_queue"

    def test_get_queue_default_name(self):
        """Test get_queue uses default name."""
        from gobbler_mcp.utils import queue as queue_module

        fake_redis = fakeredis.FakeRedis()
        queue_module._redis_conn = fake_redis

        with patch("gobbler_mcp.utils.queue.get_redis_connection", return_value=fake_redis):
            q = queue_module.get_queue()
            assert q.name == "default"


class TestJobInfo:
    """Test job information retrieval."""

    def test_get_job_info_not_found(self):
        """Test get_job_info handles missing jobs."""
        from gobbler_mcp.utils import queue as queue_module

        fake_redis = fakeredis.FakeRedis()

        with patch("gobbler_mcp.utils.queue.get_redis_connection", return_value=fake_redis):
            result = queue_module.get_job_info("nonexistent-job-id")
            assert result["status"] == "not_found"
            assert "error" in result

    def test_get_job_info_finished_job(self):
        """Test get_job_info for finished job."""
        from gobbler_mcp.utils import queue as queue_module

        fake_redis = fakeredis.FakeRedis()

        mock_job = MagicMock(spec=Job)
        mock_job.get_status.return_value = "finished"
        mock_job.created_at = datetime(2024, 1, 1, tzinfo=timezone.utc)
        mock_job.started_at = datetime(2024, 1, 1, 0, 0, 1, tzinfo=timezone.utc)
        mock_job.ended_at = datetime(2024, 1, 1, 0, 0, 10, tzinfo=timezone.utc)
        mock_job.is_finished = True
        mock_job.is_failed = False
        mock_job.is_started = False
        mock_job.result = {"success": True}

        with patch("gobbler_mcp.utils.queue.get_redis_connection", return_value=fake_redis):
            with patch("gobbler_mcp.utils.queue.Job.fetch", return_value=mock_job):
                result = queue_module.get_job_info("test-job-id")
                assert result["status"] == "finished"
                assert result["result"] == {"success": True}

    def test_get_job_info_failed_job(self):
        """Test get_job_info for failed job."""
        from gobbler_mcp.utils import queue as queue_module

        fake_redis = fakeredis.FakeRedis()

        mock_job = MagicMock(spec=Job)
        mock_job.get_status.return_value = "failed"
        mock_job.created_at = datetime(2024, 1, 1, tzinfo=timezone.utc)
        mock_job.started_at = datetime(2024, 1, 1, 0, 0, 1, tzinfo=timezone.utc)
        mock_job.ended_at = datetime(2024, 1, 1, 0, 0, 10, tzinfo=timezone.utc)
        mock_job.is_finished = False
        mock_job.is_failed = True
        mock_job.is_started = False
        mock_job.exc_info = "ValueError: test error"

        with patch("gobbler_mcp.utils.queue.get_redis_connection", return_value=fake_redis):
            with patch("gobbler_mcp.utils.queue.Job.fetch", return_value=mock_job):
                result = queue_module.get_job_info("test-job-id")
                assert result["status"] == "failed"
                assert "error" in result


class TestFormatJobResponse:
    """Test job response formatting."""

    def test_format_job_response_basic(self):
        """Test basic job response formatting."""
        from gobbler_mcp.utils.queue import format_job_response

        mock_job = MagicMock()
        mock_job.id = "test-job-123"
        mock_job.origin = "transcription"

        with patch("gobbler_mcp.utils.queue.estimate_task_duration", return_value=120):
            result = format_job_response(mock_job, "transcribe_audio")

            assert "test-job-123" in result
            assert "transcription" in result
            assert "2 minutes" in result
            assert "get_job_status" in result

    def test_format_job_response_singular_minute(self):
        """Test job response with singular minute."""
        from gobbler_mcp.utils.queue import format_job_response

        mock_job = MagicMock()
        mock_job.id = "test-job-456"
        mock_job.origin = "default"

        with patch("gobbler_mcp.utils.queue.estimate_task_duration", return_value=60):
            result = format_job_response(mock_job, "download_youtube")

            assert "1 minute" in result
            assert "1 minutes" not in result


class TestListJobsInQueue:
    """Test queue job listing."""

    def test_list_jobs_empty_queue(self):
        """Test listing jobs from empty queue."""
        from gobbler_mcp.utils import queue as queue_module

        fake_redis = fakeredis.FakeRedis()

        mock_queue = MagicMock()
        mock_queue.jobs = []

        with patch("gobbler_mcp.utils.queue.get_queue", return_value=mock_queue):
            result = queue_module.list_jobs_in_queue("default")
            assert result == []

    def test_list_jobs_with_jobs(self):
        """Test listing jobs from queue with jobs."""
        from gobbler_mcp.utils import queue as queue_module

        mock_job = MagicMock()
        mock_job.id = "job-123"
        mock_job.get_status.return_value = "queued"
        mock_job.created_at = datetime(2024, 1, 1, tzinfo=timezone.utc)
        mock_job.func_name = "transcribe_audio"

        mock_queue = MagicMock()
        mock_queue.jobs = [mock_job]

        with patch("gobbler_mcp.utils.queue.get_queue", return_value=mock_queue):
            result = queue_module.list_jobs_in_queue("default", limit=10)

            assert len(result) == 1
            assert result[0]["job_id"] == "job-123"
            assert result[0]["status"] == "queued"

    def test_list_jobs_handles_error(self):
        """Test list_jobs handles errors gracefully."""
        from gobbler_mcp.utils import queue as queue_module

        with patch("gobbler_mcp.utils.queue.get_queue", side_effect=Exception("Queue error")):
            result = queue_module.list_jobs_in_queue("default")
            assert result == []


@pytest.fixture(autouse=True)
def reset_redis_connection():
    """Reset global Redis connection between tests."""
    from gobbler_mcp.utils import queue as queue_module

    queue_module._redis_conn = None
    yield
    queue_module._redis_conn = None
