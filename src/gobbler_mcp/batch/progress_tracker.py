"""Progress tracking for batch operations using Redis."""

import json
import logging
from datetime import datetime
from typing import Optional

import redis

from ..config import get_config

logger = logging.getLogger(__name__)


class ProgressTracker:
    """Track batch operation progress in Redis."""

    def __init__(self, batch_id: str):
        """
        Initialize progress tracker.

        Args:
            batch_id: Unique identifier for batch operation
        """
        self.batch_id = batch_id
        self.redis_key = f"batch:progress:{batch_id}"
        self._redis: Optional[redis.Redis] = None

    @property
    def redis(self) -> redis.Redis:
        """
        Get or create Redis connection with retry logic.

        Returns:
            Redis connection instance
        """
        if self._redis is None:
            config = get_config()
            redis_config = config.data.get("redis", {})
            host = redis_config.get("host", "localhost")
            port = redis_config.get("port", 6380)
            db = redis_config.get("db", 0)

            self._redis = redis.Redis(
                host=host,
                port=port,
                db=db,
                decode_responses=True,
                socket_connect_timeout=5,
                socket_timeout=5,
                retry_on_timeout=True,
                health_check_interval=30,
            )
        return self._redis

    async def initialize(self, total_items: int, operation_type: str = "batch") -> None:
        """
        Initialize progress tracking.

        Args:
            total_items: Total number of items in batch
            operation_type: Type of operation (e.g., 'youtube_playlist', 'webpage_batch')
        """
        data = {
            "batch_id": self.batch_id,
            "operation_type": operation_type,
            "total_items": total_items,
            "processed": 0,
            "successful": 0,
            "failed": 0,
            "skipped": 0,
            "current_item": None,
            "started_at": datetime.utcnow().isoformat(),
            "status": "running",
            "errors": [],
        }

        try:
            self.redis.setex(
                self.redis_key,
                3600 * 24,  # Expire after 24 hours
                json.dumps(data),
            )
            logger.info(f"Initialized progress tracking for batch {self.batch_id}")
        except redis.RedisError as e:
            logger.warning(f"Failed to initialize progress tracking: {e}")

    async def update_current_item(self, item: str) -> None:
        """
        Update currently processing item.

        Args:
            item: Identifier or name of current item
        """
        try:
            data_str = self.redis.get(self.redis_key)
            if not data_str:
                logger.warning(f"Batch {self.batch_id} not found in Redis")
                return

            data = json.loads(data_str)
            data["current_item"] = item
            data["processed"] = data.get("processed", 0) + 1

            self.redis.setex(self.redis_key, 3600 * 24, json.dumps(data))
        except redis.RedisError as e:
            logger.warning(f"Failed to update current item: {e}")
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse progress data: {e}")

    async def increment_success(self) -> None:
        """Increment success counter."""
        try:
            data_str = self.redis.get(self.redis_key)
            if not data_str:
                return

            data = json.loads(data_str)
            data["successful"] = data.get("successful", 0) + 1

            self.redis.setex(self.redis_key, 3600 * 24, json.dumps(data))
        except (redis.RedisError, json.JSONDecodeError) as e:
            logger.warning(f"Failed to increment success counter: {e}")

    async def increment_failure(self, error: str, item: Optional[str] = None) -> None:
        """
        Increment failure counter and log error.

        Args:
            error: Error message
            item: Optional item identifier that failed
        """
        try:
            data_str = self.redis.get(self.redis_key)
            if not data_str:
                return

            data = json.loads(data_str)
            data["failed"] = data.get("failed", 0) + 1

            error_entry = {
                "error": error,
                "timestamp": datetime.utcnow().isoformat(),
            }
            if item:
                error_entry["item"] = item

            data["errors"].append(error_entry)

            # Keep only last 100 errors to prevent unbounded growth
            if len(data["errors"]) > 100:
                data["errors"] = data["errors"][-100:]

            self.redis.setex(self.redis_key, 3600 * 24, json.dumps(data))
        except (redis.RedisError, json.JSONDecodeError) as e:
            logger.warning(f"Failed to increment failure counter: {e}")

    async def increment_skipped(self, reason: str, item: Optional[str] = None) -> None:
        """
        Increment skipped counter.

        Args:
            reason: Reason for skipping
            item: Optional item identifier that was skipped
        """
        try:
            data_str = self.redis.get(self.redis_key)
            if not data_str:
                return

            data = json.loads(data_str)
            data["skipped"] = data.get("skipped", 0) + 1

            self.redis.setex(self.redis_key, 3600 * 24, json.dumps(data))
        except (redis.RedisError, json.JSONDecodeError) as e:
            logger.warning(f"Failed to increment skipped counter: {e}")

    async def mark_complete(self) -> None:
        """Mark batch as complete."""
        try:
            data_str = self.redis.get(self.redis_key)
            if not data_str:
                return

            data = json.loads(data_str)
            data["status"] = "completed"
            data["completed_at"] = datetime.utcnow().isoformat()

            self.redis.setex(self.redis_key, 3600 * 24, json.dumps(data))
            logger.info(f"Marked batch {self.batch_id} as complete")
        except (redis.RedisError, json.JSONDecodeError) as e:
            logger.warning(f"Failed to mark batch complete: {e}")

    async def mark_failed(self, error: str) -> None:
        """
        Mark batch as failed.

        Args:
            error: Error message describing why batch failed
        """
        try:
            data_str = self.redis.get(self.redis_key)
            if data_str:
                data = json.loads(data_str)
            else:
                # Create minimal data if not exists
                data = {
                    "batch_id": self.batch_id,
                    "started_at": datetime.utcnow().isoformat(),
                }

            data["status"] = "failed"
            data["failed_at"] = datetime.utcnow().isoformat()
            data["error"] = error

            self.redis.setex(self.redis_key, 3600 * 24, json.dumps(data))
            logger.error(f"Marked batch {self.batch_id} as failed: {error}")
        except (redis.RedisError, json.JSONDecodeError) as e:
            logger.error(f"Failed to mark batch as failed: {e}")

    async def get_progress(self) -> Optional[dict]:
        """
        Get current progress.

        Returns:
            Progress data dictionary, or None if not found
        """
        try:
            data_str = self.redis.get(self.redis_key)
            if not data_str:
                return None

            return json.loads(data_str)
        except (redis.RedisError, json.JSONDecodeError) as e:
            logger.error(f"Failed to get progress: {e}")
            return None

    def format_progress_report(self, progress: dict) -> str:
        """
        Format progress data as human-readable report.

        Args:
            progress: Progress data dictionary

        Returns:
            Formatted progress report
        """
        if not progress:
            return "Batch not found"

        status = progress.get("status", "unknown")
        total = progress.get("total_items", 0)
        processed = progress.get("processed", 0)
        successful = progress.get("successful", 0)
        failed = progress.get("failed", 0)
        skipped = progress.get("skipped", 0)
        current = progress.get("current_item", "N/A")

        # Status icon
        status_icon = {
            "running": "🔄",
            "completed": "✅",
            "failed": "❌",
        }.get(status, "❓")

        lines = [
            f"# Batch Progress Report\n",
            f"**Batch ID:** {progress.get('batch_id')}",
            f"**Operation:** {progress.get('operation_type', 'unknown')}",
            f"**Status:** {status_icon} {status.upper()}\n",
            "## Progress",
            f"- **Processed:** {processed}/{total}",
            f"- **Successful:** {successful}",
            f"- **Failed:** {failed}",
            f"- **Skipped:** {skipped}",
        ]

        if status == "running":
            lines.append(f"- **Current Item:** {current}")

            # Calculate percentage
            if total > 0:
                percent = (processed / total) * 100
                lines.append(f"- **Progress:** {percent:.1f}%")

        # Show recent errors if any
        errors = progress.get("errors", [])
        if errors:
            lines.append("\n## Recent Errors")
            for error_entry in errors[-5:]:  # Show last 5 errors
                error_msg = error_entry.get("error", "Unknown error")
                item = error_entry.get("item", "")
                if item:
                    lines.append(f"- {item}: {error_msg}")
                else:
                    lines.append(f"- {error_msg}")

        # Timing info
        started_at = progress.get("started_at")
        if started_at:
            lines.append(f"\n**Started:** {started_at}")

        completed_at = progress.get("completed_at")
        if completed_at:
            lines.append(f"**Completed:** {completed_at}")

        return "\n".join(lines)
