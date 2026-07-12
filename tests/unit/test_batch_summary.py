"""Batch outcome summary contract tests."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from gobbler_cli.commands.batch import app


@pytest.fixture
def mixed_directory_fixture(tmp_path: Path) -> tuple[Path, Path]:
    """Create inputs representing completed, skipped, provider, and output outcomes."""
    input_dir = tmp_path / "input"
    input_dir.mkdir()
    for name in ("completed.pdf", "provider.docx", "filesystem.xlsx", "skipped.txt"):
        (input_dir / name).write_bytes(b"fixture")
    return input_dir, tmp_path / "output"


def test_directory_json_mixed_outcomes_have_parseable_categorized_summary(
    mixed_directory_fixture: tuple[Path, Path],
) -> None:
    """A direct batch smoke reports every mixed outcome in the terminal JSON event."""
    input_dir, output_dir = mixed_directory_fixture
    original_write_text = Path.write_text

    async def fake_convert(file_path: str, **_kwargs: object) -> tuple[str, dict[str, str]]:
        if Path(file_path).name == "provider.docx":
            message = "provider unavailable for https://user:secret@example.com/?token=secret"
            raise RuntimeError(message)
        return "# converted\n", {"provider": "fixture"}

    def guarded_write_text(
        path: Path,
        data: str,
        encoding: str | None = None,
        errors: str | None = None,
        newline: str | None = None,
    ) -> int:
        if path.name == "filesystem.md":
            message = "fixture output denied"
            raise PermissionError(message)
        return original_write_text(
            path,
            data,
            encoding=encoding,
            errors=errors,
            newline=newline,
        )

    with (
        patch(
            "gobbler_core.converters.document.convert_document_to_markdown",
            side_effect=fake_convert,
        ),
        patch.object(Path, "write_text", new=guarded_write_text),
    ):
        result = CliRunner().invoke(
            app,
            [
                "directory",
                str(input_dir),
                "--output",
                str(output_dir),
                "--json",
            ],
        )

    records = [json.loads(line) for line in result.stdout.splitlines()]
    summary = records[-1]["summary"]

    assert result.exit_code == 1
    assert records[-1]["type"] == "batch_complete"
    assert summary["total"] == 4
    assert summary["successful"] == 1
    assert summary["failed"] == 2
    assert summary["skipped"] == 1
    assert summary["outcomes"] == {
        "completed": 1,
        "skipped": 1,
        "invalid_input": 0,
        "provider_service": 1,
        "filesystem_output": 1,
        "queue_submission": 0,
    }
    assert {item["category"] for item in summary["retry_guidance"]} == {
        "provider_service",
        "filesystem_output",
    }
    assert "secret" not in json.dumps(summary)
