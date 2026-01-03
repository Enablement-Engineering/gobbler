"""Metrics helper utilities for MCP tools and batch processing."""

from collections.abc import Callable


def get_metrics_callback() -> Callable[[str, int], None] | None:
    """Get metrics callback if metrics are enabled.

    Returns a callback function that records conversion size metrics,
    or None if metrics are not available or disabled.

    Returns:
        Callable[[str, int], None] or None: Callback accepting (converter_type, size_bytes)

    Example:
        callback = get_metrics_callback()
        if callback:
            callback("youtube", len(markdown_content))
    """
    try:
        from ..metrics import conversion_size  # noqa: PLC0415

        return lambda converter_type, size: conversion_size.labels(
            converter_type=converter_type
        ).observe(size)
    except Exception:
        # Metrics not available or disabled
        return None
