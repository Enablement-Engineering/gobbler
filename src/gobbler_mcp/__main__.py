"""Entry point for Gobbler MCP server."""

import sys

from .server import mcp


def main() -> None:
    """Run the MCP server."""
    try:
        mcp.run()
    except KeyboardInterrupt:
        print("\nShutting down...", file=sys.stderr)
        sys.exit(0)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
