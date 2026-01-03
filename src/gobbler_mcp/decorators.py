"""Decorators for MCP tool error handling.

Provides consistent error handling across all MCP tools.
"""

import logging
from collections.abc import Callable
from functools import wraps

import httpx

logger = logging.getLogger(__name__)


def handle_tool_errors(operation_name: str, service_name: str | None = None) -> Callable:
    """Decorator for consistent MCP tool error handling.

    Args:
        operation_name: Human-readable operation name for error messages
        service_name: Optional service name for connection error messages

    Returns:
        Decorated function with consistent error handling
    """

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs) -> str:
            try:
                return await func(*args, **kwargs)
            except httpx.ConnectError as e:
                service_msg = f" Is {service_name} running?" if service_name else ""
                logger.error(f"Connection error in {operation_name}: {e}")
                return f"❌ Connection failed: {e}.{service_msg}"
            except ValueError as e:
                logger.warning(f"Validation error in {operation_name}: {e}")
                return str(e)
            except FileNotFoundError as e:
                logger.error(f"File not found in {operation_name}: {e}")
                return f"Error: File not found: {e}"
            except Exception as e:
                logger.error(f"Unexpected error in {operation_name}: {e}", exc_info=True)
                return f"Failed to {operation_name}: {e!s}"

        return wrapper

    return decorator
