"""Tests for the public configuration CLI."""

from pathlib import Path

from typer.testing import CliRunner

from gobbler_cli.commands.config import app

runner = CliRunner()


def test_config_init_uses_repository_example(monkeypatch, tmp_path: Path) -> None:
    """Source checkouts should install the canonical commented example."""
    monkeypatch.setenv("HOME", str(tmp_path))

    result = runner.invoke(app, ["init"])

    assert result.exit_code == 0, result.output
    generated = tmp_path / ".config" / "gobbler" / "config.yml"
    content = generated.read_text()
    assert "providers:" in content
    assert "services:" in content
    assert "monitoring:" in content
    assert "api_token: gobbler-local-token" in content
    assert "The no-flag CLI currently selects docling directly" in content
