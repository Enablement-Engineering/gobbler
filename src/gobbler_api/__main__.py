"""Main entry point for running the Gobbler API server."""

import logging
import sys

import uvicorn

from .server import app

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
    ],
)

logger = logging.getLogger(__name__)


def main() -> None:
    """Run the Gobbler API server."""
    logger.info("Starting Gobbler API server on http://0.0.0.0:4600")
    logger.info("API documentation available at http://localhost:4600/docs")
    logger.info("OpenAPI spec available at http://localhost:4600/openapi.json")

    uvicorn.run(
        "gobbler_api.server:app",
        host="0.0.0.0",
        port=4600,
        reload=False,
        log_level="info",
    )


if __name__ == "__main__":
    main()
