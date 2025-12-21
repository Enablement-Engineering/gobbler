"""Gobbler API - REST API server for content conversion.

FastAPI-based REST API for converting YouTube videos, audio files, documents,
and web pages to markdown format. Provides synchronous and asynchronous
processing with job queue support.

Usage:
    Run the API server:
    ```bash
    python -m gobbler_api.server
    ```

    Or with uvicorn:
    ```bash
    uvicorn gobbler_api.server:app --host 0.0.0.0 --port 4600
    ```

Environment Variables:
    GOBBLER_API_KEY: Optional API key for authentication
"""

from .server import app, create_app

__version__ = "0.1.0"
__all__ = ["app", "create_app"]
