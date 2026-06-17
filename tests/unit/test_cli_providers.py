"""Unit tests for CLI providers command."""

import contextlib
import json

import pytest
from typer.testing import CliRunner

from gobbler_cli.commands import convert, providers
from gobbler_cli.main import app


@pytest.fixture
def runner() -> CliRunner:
    """Create CLI runner."""
    return CliRunner()


@pytest.fixture
def cli_app():
    """Create and configure the CLI app for testing."""
    # Add command groups (may already be registered, but typer handles duplicates)
    with contextlib.suppress(Exception):
        app.add_typer(convert.app, name="convert", help="Convert individual content items")
    with contextlib.suppress(Exception):
        app.add_typer(providers.app, name="providers", help="Manage content conversion providers")

    # Also register convert commands at the top level for convenience
    with contextlib.suppress(Exception):
        app.command("youtube", help="Convert YouTube video to markdown")(convert.youtube)
    with contextlib.suppress(Exception):
        app.command("audio", help="Transcribe audio file to markdown")(convert.audio)
    with contextlib.suppress(Exception):
        app.command("document", help="Convert document to markdown")(convert.document)
    with contextlib.suppress(Exception):
        app.command("webpage", help="Convert web page to markdown")(convert.webpage)

    return app


@pytest.fixture(autouse=True)
def setup_providers():
    """Ensure providers are registered before tests."""
    # Import triggers provider registration
    from gobbler_core import providers as core_providers  # noqa: F401


class TestProvidersListCommand:
    """Test gobbler providers list command."""

    def test_list_all_providers(self, runner: CliRunner, cli_app) -> None:
        """Test listing all providers."""
        result = runner.invoke(cli_app, ["providers", "list"])
        assert result.exit_code == 0
        # Should show table with providers
        assert "Category" in result.output or "category" in result.output.lower()

    def test_list_providers_by_category(self, runner: CliRunner, cli_app) -> None:
        """Test listing providers filtered by category."""
        result = runner.invoke(cli_app, ["providers", "list", "--category", "transcription"])
        assert result.exit_code == 0
        # Should show transcription providers
        assert "transcription" in result.output.lower()

    def test_list_providers_json_format(self, runner: CliRunner, cli_app) -> None:
        """Test listing providers with JSON output."""
        result = runner.invoke(cli_app, ["providers", "list", "--format", "json"])
        assert result.exit_code == 0
        # Should be valid JSON
        data = json.loads(result.output)
        assert isinstance(data, list)
        if data:
            assert "category" in data[0]
            assert "name" in data[0]
            assert "description" in data[0]

    def test_list_providers_invalid_category(self, runner: CliRunner, cli_app) -> None:
        """Test listing providers with invalid category shows error."""
        result = runner.invoke(cli_app, ["providers", "list", "--category", "invalid_category"])
        assert result.exit_code == 1
        assert "Unknown category" in result.output or "Error" in result.output


class TestProvidersInfoCommand:
    """Test gobbler providers info command."""

    def test_info_whisper_local(self, runner: CliRunner, cli_app) -> None:
        """Test getting info for whisper-local provider."""
        result = runner.invoke(cli_app, ["providers", "info", "transcription", "whisper-local"])
        assert result.exit_code == 0
        assert "whisper-local" in result.output.lower()
        assert "transcription" in result.output.lower()

    def test_info_json_format(self, runner: CliRunner, cli_app) -> None:
        """Test getting provider info with JSON output."""
        result = runner.invoke(
            cli_app, ["providers", "info", "transcription", "whisper-local", "--format", "json"]
        )
        assert result.exit_code == 0
        # Should be valid JSON
        data = json.loads(result.output)
        assert data["category"] == "transcription"
        assert data["name"] == "whisper-local"
        assert "class" in data
        assert "module" in data
        assert "doc" in data

    def test_info_provider_not_found(self, runner: CliRunner, cli_app) -> None:
        """Test getting info for non-existent provider shows error."""
        result = runner.invoke(
            cli_app, ["providers", "info", "transcription", "nonexistent-provider"]
        )
        assert result.exit_code == 1
        assert "not found" in result.output.lower() or "Error" in result.output

    def test_info_category_not_found(self, runner: CliRunner, cli_app) -> None:
        """Test getting info for non-existent category shows error."""
        result = runner.invoke(cli_app, ["providers", "info", "invalid_category", "some-provider"])
        assert result.exit_code == 1
        assert "not found" in result.output.lower() or "Error" in result.output


class TestConvertCommandProviderOption:
    """Test --provider option on convert commands."""

    def test_audio_command_has_provider_option(self, runner: CliRunner, cli_app) -> None:
        """Test that audio command has --provider option in help."""
        result = runner.invoke(cli_app, ["audio", "--help"])
        assert result.exit_code == 0
        assert "--provider" in result.output or "-p" in result.output

    def test_document_command_has_provider_option(self, runner: CliRunner, cli_app) -> None:
        """Test that document command has --provider option in help."""
        result = runner.invoke(cli_app, ["document", "--help"])
        assert result.exit_code == 0
        assert "--provider" in result.output or "-p" in result.output

    def test_webpage_command_has_provider_option(self, runner: CliRunner, cli_app) -> None:
        """Test that webpage command has --provider option in help."""
        result = runner.invoke(cli_app, ["webpage", "--help"])
        assert result.exit_code == 0
        assert "--provider" in result.output or "-p" in result.output

    def test_webpage_command_accepts_no_proxy_option(self, runner: CliRunner, cli_app) -> None:
        """Test that webpage command accepts --no-proxy as an option."""
        result = runner.invoke(
            cli_app,
            [
                "webpage",
                "https://example.com",
                "--provider",
                "nonexistent-provider",
                "--no-proxy",
            ],
        )
        assert result.exit_code == 1
        assert "No such option" not in result.output
        assert "not found" in result.output.lower() or "Error" in result.output

    def test_audio_invalid_provider(self, runner: CliRunner, cli_app, tmp_path) -> None:
        """Test that audio command with invalid provider shows error."""
        # Create a dummy audio file
        audio_file = tmp_path / "test.mp3"
        audio_file.write_bytes(b"dummy audio content")

        result = runner.invoke(
            cli_app, ["audio", str(audio_file), "--provider", "nonexistent-provider"]
        )
        assert result.exit_code == 1
        assert "not found" in result.output.lower() or "Error" in result.output

    def test_document_invalid_provider(self, runner: CliRunner, cli_app, tmp_path) -> None:
        """Test that document command with invalid provider shows error."""
        # Create a dummy PDF file
        pdf_file = tmp_path / "test.pdf"
        pdf_file.write_bytes(b"%PDF-1.4 dummy content")

        result = runner.invoke(
            cli_app, ["document", str(pdf_file), "--provider", "nonexistent-provider"]
        )
        assert result.exit_code == 1
        assert "not found" in result.output.lower() or "Error" in result.output

    def test_webpage_invalid_provider(self, runner: CliRunner, cli_app) -> None:
        """Test that webpage command with invalid provider shows error."""
        result = runner.invoke(
            cli_app, ["webpage", "https://example.com", "--provider", "nonexistent-provider"]
        )
        assert result.exit_code == 1
        assert "not found" in result.output.lower() or "Error" in result.output
