"""RQ worker for processing queued tasks."""

import logging
import os
import sys

from rq import SimpleWorker

from .utils.queue import get_queue, get_redis_connection

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler()],
)

logger = logging.getLogger(__name__)


def main():
    """Start RQ worker to process queued tasks."""
    # Get queue names from command line or use defaults
    queue_names = sys.argv[1:] if len(sys.argv) > 1 else ["default", "transcription", "download"]

    logger.info(f"Starting Gobbler worker for queues: {', '.join(queue_names)}")

    # Get Redis connection
    conn = get_redis_connection()

    # Get queues
    queues = [get_queue(name) for name in queue_names]

    # Create and start worker
    # Use SimpleWorker (no forking) - CoreML/Metal are not fork-safe on macOS
    worker = SimpleWorker(queues, connection=conn)

    logger.info("Worker started (SimpleWorker - no forking). Waiting for jobs...")
    worker.work()


if __name__ == "__main__":
    main()
