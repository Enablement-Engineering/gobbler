"""Reusable helpers for smoke-testing Gobbler's public CLI contract."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

import typer
from typer.testing import CliRunner, Result


@dataclass(frozen=True)
class CliContractHarness:
    """Invoke a Typer CLI and assert its process and JSON output contracts."""

    app: typer.Typer
    runner: CliRunner

    def invoke(
        self,
        args: list[str],
        *,
        expected_exit_code: int,
        stdin: str | None = None,
    ) -> Result:
        """Invoke the CLI and assert the expected process exit code.

        Args:
            args: CLI arguments excluding the executable name.
            expected_exit_code: Exit code required by the public CLI contract.
            stdin: Optional text provided to stdin.

        Returns:
            The Typer test result for additional command-specific assertions.
        """
        result = self.runner.invoke(self.app, args, input=stdin)
        assert result.exit_code == expected_exit_code, result.output
        return result

    def invoke_json(
        self,
        args: list[str],
        *,
        expected_exit_code: int,
        stdin: str | None = None,
    ) -> tuple[Result, dict[str, Any]]:
        """Invoke a command and require stdout to contain exactly one JSON object."""
        result = self.invoke(args, expected_exit_code=expected_exit_code, stdin=stdin)
        payload = json.loads(result.output)
        assert isinstance(payload, dict), "JSON stdout must be a single object"
        return result, payload

    def invoke_json_lines(
        self,
        args: list[str],
        *,
        expected_exit_code: int,
        stdin: str | None = None,
    ) -> tuple[Result, list[dict[str, Any]]]:
        """Invoke a command and require each non-empty stdout line to be a JSON object."""
        result = self.invoke(args, expected_exit_code=expected_exit_code, stdin=stdin)
        records = [json.loads(line) for line in result.output.splitlines() if line]
        assert records, "JSON-lines stdout must contain at least one object"
        assert all(isinstance(record, dict) for record in records)
        return result, records
