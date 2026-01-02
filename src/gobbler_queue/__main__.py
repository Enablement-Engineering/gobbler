"""Entry point for running the gobbler_queue worker.

Allows running the worker via:
    python -m gobbler_queue

This is equivalent to running:
    python -m gobbler_queue.worker
"""

from .worker import main

if __name__ == "__main__":
    main()
