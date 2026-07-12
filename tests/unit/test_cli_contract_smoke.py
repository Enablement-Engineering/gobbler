"""CI-safe smoke tests for Gobbler's public CLI process and JSON contracts.

Run this focused harness with ``make test-cli-contract``. External services are
replaced with local fixtures so contributors can run it without Docker or a worker.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest
from typer.testing import CliRunner

from gobbler_cli import __version__
from gobbler_cli.commands import batch, status
from gobbler_cli.main import app
from gobbler_cli.output import JSON_SCHEMA_VERSION
from tests.cli_contract import CliContractHarness


def _register_contract_commands() -> None:
    """Register only the command groups exercised by the contract harness."""
    registered_names = {group.name for group in app.registered_groups}
    if "status" not in registered_names:
        app.add_typer(status.app, name="status", help="Check service status and health")
    if "batch" not in registered_names:
        app.add_typer(batch.app, name="batch", help="Batch processing operations")


@pytest.fixture(scope="module")
def cli_contract() -> CliContractHarness:
    """Return the reusable CLI contract harness with smoke-test commands registered."""
    _register_contract_commands()
    return CliContractHarness(app=app, runner=CliRunner())


def test_cli_contract_version_reports_version_and_success(
    cli_contract: CliContractHarness,
) -> None:
    """The public --version probe remains a successful, one-line command."""
    result = cli_contract.invoke(["--version"], expected_exit_code=0)

    assert result.output == f"gobbler version {__version__}\n"


def test_cli_contract_status_json_is_payload_only(
    cli_contract: CliContractHarness,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Status JSON remains parseable without Rich headings or human preambles."""
    monkeypatch.setattr(
        status,
        "get_service_status",
        lambda: {
            "schema_version": JSON_SCHEMA_VERSION,
            "status": "ready",
            "services": {},
            "config_path": "test-config.yml",
            "proxy": {"configured": False},
        },
    )

    result, payload = cli_contract.invoke_json(["status", "--json"], expected_exit_code=0)

    assert payload["schema_version"] == JSON_SCHEMA_VERSION
    assert payload["status"] == "ready"
    assert "Gobbler Status" not in result.output


def test_cli_contract_invalid_input_json_exits_nonzero_before_dispatch(
    cli_contract: CliContractHarness,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Invalid batch input emits one diagnostic JSON record and exits nonzero."""
    urls_file = tmp_path / "urls.txt"
    urls_file.write_text("ftp://example.com/private\n", encoding="utf-8")
    convert = MagicMock()
    monkeypatch.setattr(
        "gobbler_core.converters.webpage.convert_webpage_to_markdown",
        convert,
    )

    result, records = cli_contract.invoke_json_lines(
        [
            "batch",
            "webpages",
            str(urls_file),
            "--output-dir",
            str(tmp_path / "output"),
            "--json",
        ],
        expected_exit_code=1,
    )

    assert records == [
        {
            "schema_version": JSON_SCHEMA_VERSION,
            "type": "invalid_input",
            "success": False,
            "error_code": "WEBPAGE_INVALID_URL",
            "error": "Invalid webpage URL: expected an absolute http:// or https:// URL.",
            "url": "ftp://example.com/private",
            "source": "ftp://example.com/private",
            "suggestion": "Provide a URL like https://example.com.",
        }
    ]
    assert "Error:" not in result.output
    convert.assert_not_called()


def test_cli_contract_queued_batch_webpage_json_is_single_payload(
    cli_contract: CliContractHarness,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Queued webpage batches emit one job payload without worker or Rich output."""
    urls_file = tmp_path / "urls.txt"
    urls_file.write_text("https://example.com/one\nhttps://example.com/two\n", encoding="utf-8")
    manager = MagicMock()
    manager.create_job.return_value.id = "job-smoke-123"
    monkeypatch.setattr("gobbler_queue.manager.JobManager", lambda: manager)

    result, payload = cli_contract.invoke_json(
        [
            "batch",
            "webpages",
            str(urls_file),
            "--output-dir",
            str(tmp_path / "output"),
            "--queue",
            "--json",
        ],
        expected_exit_code=0,
    )

    assert payload["schema_version"] == JSON_SCHEMA_VERSION
    assert payload["type"] == "job_queued"
    assert payload["job_id"] == "job-smoke-123"
    assert payload["total_urls"] == 2
    assert "Queued batch webpage job" not in result.output
    manager.create_job.assert_called_once()


def test_cli_contract_dry_run_assigns_unique_output_paths(
    cli_contract: CliContractHarness,
    tmp_path: Path,
) -> None:
    """Dry-run JSON exposes deterministic unique paths for colliding URLs."""
    urls_file = tmp_path / "urls.txt"
    urls_file.write_text("https://example.com\nhttps://example.com\n", encoding="utf-8")
    output_dir = tmp_path / "output"

    result, payload = cli_contract.invoke_json(
        [
            "batch",
            "webpages",
            str(urls_file),
            "--output-dir",
            str(output_dir),
            "--dry-run",
            "--json",
        ],
        expected_exit_code=0,
    )

    output_names = [Path(item["output"]).name for item in payload["urls"]]
    assert payload["type"] == "dry_run"
    assert output_names == ["example.com.md", "example.com-2.md"]
    assert len(output_names) == len(set(output_names))
    assert not output_dir.exists()
    assert "Dry Run Preview" not in result.output
