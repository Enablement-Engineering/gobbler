"""Tests for the status command diagnostics."""

from __future__ import annotations

import json
import threading
from pathlib import Path
from typing import Any

from gobbler_cli.commands import status as status_commands
from gobbler_core.config import Config
from gobbler_core.utils.redaction import REDACTED, redact_value


def _install_config(data: dict[str, Any], config_path: Path) -> Config:
    """Install a test config singleton."""
    config = Config.__new__(Config)
    config._lock = threading.RLock()
    config.config_path = config_path
    config.data = data

    import gobbler_core.config as config_module

    config_module._config = config
    return config


def test_status_separates_webpage_health_from_probe_failure(monkeypatch, tmp_path: Path) -> None:
    """Status JSON distinguishes Crawl4AI /health from /crawl readiness."""
    _install_config(
        {
            "providers": {
                "youtube": {"default": "youtube-transcript-api"},
                "transcription": {"default": "whisper-local", "whisper-local": {"model": "tiny"}},
            },
            "services": {
                "docling": {"host": "localhost", "port": 5001},
                "crawl4ai": {
                    "host": "localhost",
                    "port": 11235,
                    "api_token": "secret-token",
                },
            },
        },
        tmp_path / "config.yml",
    )
    monkeypatch.setattr(status_commands, "check_service_health", lambda _url: (True, None))
    monkeypatch.setattr(
        status_commands,
        "_webpage_conversion_probe",
        lambda *_args, **_kwargs: {
            "status": "failed",
            "ok": False,
            "provider": "crawl4ai",
            "stage": "crawl_probe",
            "status_code": 500,
            "error": (
                "Crawl4AI /crawl returned HTTP 500 for "
                "http://proxy-user:proxy-pass@proxy.example:8080"
            ),
            "proxy_configured": True,
        },
    )

    status_data = status_commands.get_service_status()
    webpage = status_data["services"]["webpage"]
    redacted = redact_value(status_data)
    dumped = json.dumps(redacted)

    assert status_data["status"] == "degraded"
    assert webpage["status"] == "degraded"
    assert webpage["service_health"]["status"] == "ready"
    assert webpage["conversion_probe"]["status"] == "failed"
    assert webpage["provider_readiness"] == "degraded"
    assert REDACTED in dumped
    assert "proxy-user" not in dumped
    assert "proxy-pass" not in dumped
    assert "secret-token" not in dumped
