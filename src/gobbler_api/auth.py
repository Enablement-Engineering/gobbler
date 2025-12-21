"""API key authentication middleware for FastAPI."""

import os
from typing import Optional

from fastapi import HTTPException, Security, status
from fastapi.security import APIKeyHeader

# API key header scheme
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


def get_api_key_from_env() -> Optional[str]:
    """Get API key from environment variable.

    Returns:
        API key if set, None otherwise
    """
    return os.getenv("GOBBLER_API_KEY")


async def verify_api_key(api_key: Optional[str] = Security(api_key_header)) -> str:
    """Verify API key from request header.

    Args:
        api_key: API key from request header

    Returns:
        Validated API key

    Raises:
        HTTPException: If API key is missing or invalid
    """
    # If no API key is configured, allow all requests
    configured_key = get_api_key_from_env()
    if not configured_key:
        return "no-auth-required"

    # Check if API key was provided
    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="API key required. Provide X-API-Key header.",
            headers={"WWW-Authenticate": "ApiKey"},
        )

    # Verify API key matches
    if api_key != configured_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key",
            headers={"WWW-Authenticate": "ApiKey"},
        )

    return api_key


def is_auth_enabled() -> bool:
    """Check if API key authentication is enabled.

    Returns:
        True if GOBBLER_API_KEY is set, False otherwise
    """
    return get_api_key_from_env() is not None
