"""Tests for the status command diagnostics."""

from __future__ import annotations

import json
import threading
from pathlib import Path
from typing import Any

from typer.testing import CliRunner

from gobbler_cli.commands import status as status_commands
from gobbler_cli.output import JSON_SCHEMA_VERSION
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
            "advice": (
                "A proxy is configured for Crawl4AI; retry the single-page CLI without "
                "the proxy to isolate degraded proxy paths: "
                "gobbler webpage https://example.com/ --no-proxy. Also verify proxy "
                "credentials, network reachability, and Crawl4AI container logs."
            ),
            "suggested_command_fragment": "gobbler webpage https://example.com/ --no-proxy",
        },
    )

    status_data = status_commands.get_service_status()
    webpage = status_data["services"]["webpage"]
    redacted = redact_value(status_data)
    dumped = json.dumps(redacted)

    assert status_data["schema_version"] == JSON_SCHEMA_VERSION
    assert status_data["status"] == "degraded"
    assert webpage["status"] == "degraded"
    assert webpage["service_health"]["status"] == "ready"
    assert webpage["conversion_probe"]["status"] == "failed"
    assert webpage["provider_readiness"] == "degraded"
    assert webpage["fix"] == webpage["conversion_probe"]["advice"]
    assert "gobbler webpage https://example.com/ --no-proxy" in webpage["fix"]
    assert REDACTED in dumped
    assert "proxy-user" not in dumped
    assert "proxy-pass" not in dumped
    assert "secret-token" not in dumped


def test_status_loopback_proxy_probe_failure_keeps_generic_fix(
    monkeypatch,
    tmp_path: Path,
) -> None:
    """Proxy-configured loopback probe failures do not suggest proxy bypass at top level."""
    _install_config(
        {
            "providers": {
                "youtube": {"default": "youtube-transcript-api"},
                "transcription": {"default": "whisper-local", "whisper-local": {"model": "tiny"}},
            },
            "services": {
                "docling": {"host": "localhost", "port": 5001},
                "crawl4ai": {"host": "localhost", "port": 11235},
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
            "error": "Crawl4AI /crawl returned HTTP 500 for http://localhost:3000/",
            "proxy_configured": True,
            "advice": (
                "A proxy is configured for Crawl4AI; verify proxy credentials, network "
                "reachability, and Crawl4AI container logs."
            ),
        },
    )

    webpage = status_commands.get_service_status()["services"]["webpage"]

    assert webpage["status"] == "degraded"
    assert webpage["fix"] == status_commands.WEBPAGE_PROBE_GENERIC_FIX
    assert "--no-proxy" not in webpage["fix"]


def test_status_non_proxy_probe_failure_keeps_generic_fix(monkeypatch, tmp_path: Path) -> None:
    """Direct Crawl4AI probe failures keep generic service/log top-level advice."""
    _install_config(
        {
            "providers": {
                "youtube": {"default": "youtube-transcript-api"},
                "transcription": {"default": "whisper-local", "whisper-local": {"model": "tiny"}},
            },
            "services": {
                "docling": {"host": "localhost", "port": 5001},
                "crawl4ai": {"host": "localhost", "port": 11235},
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
            "error": "Crawl4AI /crawl returned HTTP 500 during crawl_probe.",
            "proxy_configured": False,
            "advice": (
                "Crawl4AI /health only confirms the service is reachable; inspect the "
                "Crawl4AI container logs and proxy settings for /crawl failures."
            ),
        },
    )

    webpage = status_commands.get_service_status()["services"]["webpage"]

    assert webpage["status"] == "degraded"
    assert webpage["fix"] == status_commands.WEBPAGE_PROBE_GENERIC_FIX
    assert "--no-proxy" not in webpage["fix"]


def test_status_json_exits_zero_when_ready(monkeypatch) -> None:
    """Status JSON exits successfully when the reported status is ready."""
    monkeypatch.setattr(
        status_commands,
        "get_service_status",
        lambda: {
            "status": "ready",
            "services": {},
            "config_path": "gobbler.yml",
            "proxy": {"configured": False},
            "schema_version": JSON_SCHEMA_VERSION,
        },
    )

    result = CliRunner().invoke(status_commands.app, ["--json"])

    assert result.exit_code == 0
    assert json.loads(result.output)["status"] == "ready"


def test_status_json_exits_nonzero_when_degraded(monkeypatch) -> None:
    """Status JSON preserves the payload but exits nonzero when degraded."""
    monkeypatch.setattr(
        status_commands,
        "get_service_status",
        lambda: {
            "status": "degraded",
            "services": {"webpage": {"status": "degraded", "fix": "retry later"}},
            "config_path": "gobbler.yml",
            "proxy": {"configured": False},
            "schema_version": JSON_SCHEMA_VERSION,
        },
    )

    result = CliRunner().invoke(status_commands.app, ["--json"])

    assert result.exit_code == 1
    payload = json.loads(result.output)
    assert payload["status"] == "degraded"
    assert payload["services"]["webpage"]["fix"] == "retry later"
