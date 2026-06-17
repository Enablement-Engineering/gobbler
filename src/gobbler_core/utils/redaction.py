"""Helpers for safe diagnostic output.

These utilities preserve the shape of configuration/status data while masking
values that are likely to contain credentials. They are intended for human and
JSON/YAML diagnostic output, not for transport-layer configuration.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

REDACTED = "[REDACTED]"

_SECRET_KEY_PARTS = (
    "api_key",
    "apikey",
    "api-token",
    "api_token",
    "auth",
    "bearer",
    "credential",
    "passwd",
    "password",
    "secret",
    "token",
)

# Usernames are not always secret, but proxy service usernames are frequently
# paired credentials. Mask them in known credential-bearing contexts.
_USERNAME_PARENT_KEYS = {"proxy", "proxies", "proxy_services", "webshare", "static"}
_EMBEDDED_URL_WITH_USERINFO = re.compile(r"(?P<url>https?://[^\s<>'\")]+@[^\s<>'\")]+)")


def is_sensitive_key(key: str, parent_keys: tuple[str, ...] = ()) -> bool:
    """Return True when a mapping key should be masked in diagnostics."""
    normalized = key.lower().replace("-", "_")
    if any(part in normalized for part in _SECRET_KEY_PARTS):
        return True

    if normalized in {"user", "username"}:
        return any(parent.lower() in _USERNAME_PARENT_KEYS for parent in parent_keys)

    return False


def redact_url_userinfo(value: str) -> str:
    """Mask username/password userinfo in URLs.

    Non-URL strings are returned unchanged. Query string parameters with
    secret-shaped keys are masked while non-sensitive query parameters are
    preserved.
    """
    try:
        parts = urlsplit(value)
    except ValueError:
        return value

    if not parts.scheme or not parts.netloc:
        return value

    netloc = parts.netloc
    if "@" in parts.netloc:
        host = parts.hostname or ""
        if ":" in host and not host.startswith("["):
            host = f"[{host}]"

        netloc = f"{REDACTED}@{host}"
        if parts.port is not None:
            netloc = f"{netloc}:{parts.port}"

    query = parts.query
    if query:
        query_items = [
            (key, REDACTED if is_sensitive_key(key) else val)
            for key, val in parse_qsl(query, keep_blank_values=True)
        ]
        query = urlencode(query_items, doseq=True, safe="[]")

    return urlunsplit((parts.scheme, netloc, parts.path, query, parts.fragment))


def _redact_string(value: str) -> str:
    """Redact credentials embedded in string diagnostics."""
    redacted = redact_url_userinfo(value)

    # `redact_url_userinfo` handles strings that are exactly URLs. Error
    # messages often embed credential-bearing proxy URLs inside surrounding
    # prose, so scrub those URL substrings too.
    redacted = _EMBEDDED_URL_WITH_USERINFO.sub(
        lambda match: redact_url_userinfo(match.group("url")), redacted
    )

    # Common header/value style fragments that may appear in errors or stdout.
    lowered = redacted.lower()
    if lowered.startswith(("bearer ", "basic ")):
        return REDACTED

    return redacted


def redact_value(value: Any, parent_keys: tuple[str, ...] = ()) -> Any:
    """Recursively redact sensitive data while preserving container shape."""
    if isinstance(value, Mapping):
        redacted: dict[Any, Any] = {}
        for key, child in value.items():
            key_text = str(key)
            if is_sensitive_key(key_text, parent_keys):
                redacted[key] = REDACTED
            else:
                redacted[key] = redact_value(child, (*parent_keys, key_text))
        return redacted

    if isinstance(value, list):
        return [redact_value(item, parent_keys) for item in value]

    if isinstance(value, tuple):
        return tuple(redact_value(item, parent_keys) for item in value)

    if isinstance(value, str):
        return _redact_string(value)

    return value
