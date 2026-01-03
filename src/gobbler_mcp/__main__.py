"""Entry point for Gobbler MCP server."""

import logging
import sys

from .server import mcp

logger = logging.getLogger(__name__)


def main() -> None:
    """Run the MCP server."""
    try:
        mcp.run()
    except KeyboardInterrupt:
        logger.info("Shutting down...")
        sys.exit(0)
    except Exception:
        logger.exception("Error running MCP server")
        sys.exit(1)


if __name__ == "__main__":
    main()
