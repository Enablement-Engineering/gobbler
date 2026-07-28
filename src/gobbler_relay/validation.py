"""Runtime validation for payloads exchanged with the browser relay."""

from typing import Any, TypeGuard


def is_string_keyed_dict(value: Any) -> TypeGuard[dict[str, Any]]:
    """Return whether a value is a dictionary with only string keys."""
    return isinstance(value, dict) and all(isinstance(key, str) for key in value)


def require_string_keyed_dict(value: Any, context: str) -> dict[str, Any]:
    """Validate and return a JSON-object-like dictionary.

    Args:
        value: Value to validate.
        context: Human-readable payload location used in errors.

    Returns:
        The validated dictionary.

    Raises:
        RuntimeError: If the value is not a string-keyed dictionary.
    """
    if not is_string_keyed_dict(value):
        msg = f"Malformed relay payload: {context} must be a string-keyed dictionary"
        raise RuntimeError(msg)
    return value


def require_string_field(payload: dict[str, Any], field: str, context: str) -> str:
    """Validate and return a required string field from a relay payload."""
    value = payload.get(field)
    if not isinstance(value, str):
        msg = f"Malformed relay payload: {context}.{field} must be a string"
        raise RuntimeError(msg)  # noqa: TRY004 - protocol failures use one public error type
    return value


def validate_health_payload(value: Any) -> tuple[dict[str, Any], int]:
    """Validate a relay health response and return it with its connection count."""
    payload = require_string_keyed_dict(value, "health response")
    connection_count = payload.get("websocket_connections")
    if type(connection_count) is not int:
        msg = "Malformed relay payload: health response.websocket_connections must be an integer"
        raise RuntimeError(msg)
    return payload, connection_count


def validate_error_payload(value: Any) -> str:
    """Validate a relay service-unavailable response and return its error."""
    payload = require_string_keyed_dict(value, "503 error response")
    return require_string_field(payload, "error", "503 error response")
