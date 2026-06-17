"""Tests for the agent-friendly doctor command."""

from __future__ import annotations

import json
import threading
from pathlib import Path
from typing import Any

from typer.testing import CliRunner

from gobbler_cli.commands import doctor
from gobbler_core.config import Config
from gobbler_core.utils.redaction import REDACTED


def make_config(tmp_path: Path, data: dict[str, Any]) -> Config:
    """Create a Config instance without reading user files."""
    config = Config.__new__(Config)
    config._lock = threading.RLock()
    config.config_path = tmp_path / "config.yml"
    config.data = data
    return config


def test_collect_doctor_report_shape_and_next_actions(monkeypatch, tmp_path: Path) -> None:
    """Doctor JSON includes stable diagnostics and actionable remediation."""
    config = make_config(
        tmp_path,
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
    )
    monkeypatch.setattr(doctor, "get_config", lambda: config)
    monkeypatch.setattr(doctor, "get_ffmpeg_status", lambda: {"available": False, "path": None})
    monkeypatch.setattr(
        doctor,
        "get_docker_status",
        lambda: {"available": True, "path": "/usr/bin/docker", "daemon_available": False},
    )

    def service_down(_url: str) -> tuple[bool, str]:
        return False, "connection refused"

    monkeypatch.setattr(doctor, "_check_service_health", service_down)

    report = doctor.collect_doctor_report()

    assert report["status"] == "degraded"
    assert report["can_use"] is True
    assert report["version"]
    assert report["python"]["executable"]
    assert report["tools"]["ffmpeg"]["available"] is False
    assert report["tools"]["docker"]["daemon_available"] is False
    assert report["config"]["path"].endswith("config.yml")
    assert report["config"]["exists"] is False
    assert set(report["services"]) == {"youtube", "audio", "document", "webpage"}
    assert report["services"]["youtube"]["status"] == "ready"
    assert report["services"]["audio"]["status"] == "unavailable"
    assert any("Install ffmpeg" in action for action in report["next_actions"])
    assert any("Start Docling" in action for action in report["next_actions"])
    assert any("Start Crawl4AI" in action for action in report["next_actions"])
    assert any("Docker daemon" in action for action in report["next_actions"])


def test_ready_services_do_not_recommend_docker_install(monkeypatch, tmp_path: Path) -> None:
    """Healthy document/webpage services should not produce Docker remediation."""
    config = make_config(
        tmp_path,
        {
            "providers": {
                "youtube": {"default": "youtube-transcript-api"},
                "transcription": {"default": "whisper-local", "whisper-local": {"model": "tiny"}},
            },
            "services": {
                "docling": {"host": "remote-docling.example", "port": 5001},
                "crawl4ai": {"host": "remote-crawl.example", "port": 11235},
            },
        },
    )
    monkeypatch.setattr(doctor, "get_config", lambda: config)
    monkeypatch.setattr(
        doctor,
        "get_ffmpeg_status",
        lambda: {"available": True, "path": "/usr/bin/ffmpeg"},
    )
    monkeypatch.setattr(
        doctor,
        "get_docker_status",
        lambda: {"available": False, "path": None, "daemon_available": False},
    )

    def service_ready(_url: str) -> tuple[bool, None]:
        return True, None

    monkeypatch.setattr(doctor, "_check_service_health", service_ready)

    report = doctor.collect_doctor_report()

    assert report["status"] == "ready"
    assert report["services"]["document"]["status"] == "ready"
    assert report["services"]["webpage"]["status"] == "ready"
    assert not any("Docker" in action for action in report["next_actions"])
    assert report["next_actions"] == [
        "Gobbler is ready. Run a conversion command such as `gobbler youtube URL`."
    ]


def test_collect_doctor_report_redacts_config_secrets(monkeypatch, tmp_path: Path) -> None:
    """Doctor JSON redacts config secrets while preserving config shape."""
    config = make_config(
        tmp_path,
        {
            "providers": {
                "youtube": {"default": "transcriptapi", "transcriptapi": {"api_key": "secret"}},
                "transcription": {"default": "whisper-local", "whisper-local": {"model": "tiny"}},
            },
            "proxy_services": {
                "webshare": {
                    "type": "webshare",
                    "username": "proxy-user",
                    "password": "proxy-pass",
                    "url": "http://user:pass@example.com:8080?token=abc&region=us",
                }
            },
            "services": {
                "docling": {"host": "localhost", "port": 5001},
                "crawl4ai": {"host": "localhost", "port": 11235, "api_token": "local-token"},
            },
        },
    )
    monkeypatch.setattr(doctor, "get_config", lambda: config)
    monkeypatch.setattr(
        doctor,
        "get_ffmpeg_status",
        lambda: {"available": True, "path": "/usr/bin/ffmpeg"},
    )
    monkeypatch.setattr(
        doctor,
        "get_docker_status",
        lambda: {"available": True, "path": "/usr/bin/docker", "daemon_available": True},
    )

    def service_ready(_url: str) -> tuple[bool, None]:
        return True, None

    monkeypatch.setattr(doctor, "_check_service_health", service_ready)

    values = doctor.collect_doctor_report()["config"]["values"]

    assert values["providers"]["youtube"]["transcriptapi"]["api_key"] == REDACTED
    assert values["proxy_services"]["webshare"]["username"] == REDACTED
    assert values["proxy_services"]["webshare"]["password"] == REDACTED
    assert REDACTED in values["proxy_services"]["webshare"]["url"]
    assert "pass" not in values["proxy_services"]["webshare"]["url"]
    assert values["services"]["crawl4ai"]["api_token"] == REDACTED


def test_doctor_json_command_outputs_valid_json(monkeypatch, tmp_path: Path) -> None:
    """The command emits parseable JSON for agents."""
    config = make_config(
        tmp_path,
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
    )
    monkeypatch.setattr(doctor, "get_config", lambda: config)
    monkeypatch.setattr(
        doctor,
        "get_ffmpeg_status",
        lambda: {"available": True, "path": "/usr/bin/ffmpeg"},
    )
    monkeypatch.setattr(
        doctor,
        "get_docker_status",
        lambda: {"available": False, "path": None, "daemon_available": False},
    )

    def service_down(_url: str) -> tuple[bool, str]:
        return False, "connection refused"

    monkeypatch.setattr(doctor, "_check_service_health", service_down)

    result = CliRunner().invoke(doctor.app, ["--json"])

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["status"] == "degraded"
    assert payload["services"]["document"]["fix"]
    assert payload["next_actions"]
