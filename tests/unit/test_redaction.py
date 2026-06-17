"""Tests for safe diagnostic redaction."""

from __future__ import annotations

import contextlib
import json
import threading
from pathlib import Path
from types import SimpleNamespace

import yaml

from gobbler_cli.commands import config as config_commands, status as status_commands
from gobbler_core.config import Config
from gobbler_core.utils.redaction import REDACTED, redact_url_userinfo, redact_value

RAW_PASSWORD = "super-secret-password"  # noqa: S105
RAW_TOKEN = "fake-token-value"  # noqa: S105
RAW_USERNAME = "proxy-user"
RAW_PROXY_URL = "http://proxy-user:super-secret-password@proxy.example:8080"


def _install_test_config(monkeypatch, data: dict, config_path: Path) -> Config:
    config = Config.__new__(Config)
    config._lock = threading.RLock()
    config.config_path = config_path
    config.data = data

    import gobbler_core.config as config_module

    monkeypatch.setattr(config_module, "_config", config)
    return config


def _sample_secret_config() -> dict:
    return {
        "proxy_services": {
            "webshare": {
                "type": "webshare",
                "username": RAW_USERNAME,
                "password": RAW_PASSWORD,
                "url": RAW_PROXY_URL,
            }
        },
        "services": {
            "crawl4ai": {
                "host": "localhost",
                "port": 11235,
                "api_token": RAW_TOKEN,
            }
        },
        "providers": {
            "youtube": {
                "default": "transcriptapi",
                "transcriptapi": {"api_key": RAW_TOKEN},
            }
        },
        "diagnostics": [
            {"credential": RAW_PASSWORD},
            "https://api-user:super-secret-password@example.com/path",
        ],
    }


def test_redact_value_masks_nested_secret_keys_and_url_userinfo() -> None:
    redacted = redact_value(_sample_secret_config())

    dumped = yaml.safe_dump(redacted)
    assert REDACTED in dumped
    assert RAW_PASSWORD not in dumped
    assert RAW_TOKEN not in dumped
    assert RAW_USERNAME not in dumped
    assert "proxy-user:super-secret-password@" not in dumped
    assert "https://[REDACTED]@example.com/path" in dumped


def test_redact_url_userinfo_preserves_url_without_credentials() -> None:
    assert redact_url_userinfo("https://example.com/path?x=1") == "https://example.com/path?x=1"
    assert redact_url_userinfo(RAW_PROXY_URL) == f"http://{REDACTED}@proxy.example:8080"
    assert (
        redact_url_userinfo("https://example.com/path?token=fake-token-value&ok=1")
        == f"https://example.com/path?token={REDACTED}&ok=1"
    )


def test_config_show_redacts_yaml_by_default(monkeypatch, tmp_path, capsys) -> None:
    _install_test_config(monkeypatch, _sample_secret_config(), tmp_path / "config.yml")

    config_commands.show_config(output_format="yaml")

    output = capsys.readouterr().out
    assert REDACTED in output
    assert RAW_PASSWORD not in output
    assert RAW_TOKEN not in output
    assert RAW_USERNAME not in output
    assert "proxy-user:super-secret-password@" not in output


def test_config_show_redacts_json_by_default(monkeypatch, tmp_path, capsys) -> None:
    _install_test_config(monkeypatch, _sample_secret_config(), tmp_path / "config.yml")

    config_commands.show_config(output_format="json")

    data = json.loads(capsys.readouterr().out)
    dumped = json.dumps(data)
    assert data["proxy_services"]["webshare"]["password"] == REDACTED
    assert data["services"]["crawl4ai"]["api_token"] == REDACTED
    assert RAW_PASSWORD not in dumped
    assert RAW_TOKEN not in dumped
    assert RAW_USERNAME not in dumped


def test_config_get_redacts_single_secret_value_by_default(monkeypatch, tmp_path, capsys) -> None:
    _install_test_config(monkeypatch, _sample_secret_config(), tmp_path / "config.yml")

    config_commands.get_config("proxy_services.webshare.password")

    output = capsys.readouterr().out.strip()
    assert output == REDACTED
    assert RAW_PASSWORD not in output


def test_config_show_secrets_escape_hatch_prints_raw_values(monkeypatch, tmp_path, capsys) -> None:
    _install_test_config(monkeypatch, _sample_secret_config(), tmp_path / "config.yml")

    config_commands.show_config(output_format="yaml", show_secrets=True)

    output = capsys.readouterr().out
    assert RAW_PASSWORD in output
    assert RAW_TOKEN in output


def test_status_json_redacts_credential_bearing_urls(monkeypatch, tmp_path, capsys) -> None:
    config = _sample_secret_config()
    config["services"]["crawl4ai"]["host"] = "crawl-user:crawl-pass@crawl.example"
    _install_test_config(monkeypatch, config, tmp_path / "config.yml")
    monkeypatch.setattr(
        status_commands, "check_service_health", lambda *_args, **_kwargs: (False, None)
    )

    with contextlib.suppress(SystemExit):
        status_commands.status(SimpleNamespace(invoked_subcommand=None), json_output=True)

    output = capsys.readouterr().out
    data = json.loads(output)
    dumped = json.dumps(data)
    assert "crawl-user" not in dumped
    assert "crawl-pass" not in dumped
    assert data["services"]["webpage"]["url"] == f"http://{REDACTED}@crawl.example:11235"
