"""Output formatting utilities for the Gobbler CLI."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Any, BinaryIO

from rich.console import Console
from rich.table import Table

console = Console()
error_console = Console(stderr=True)

JSON_SCHEMA_VERSION = 1


def _fsync_directory(path: Path) -> None:
    """Fsync a directory after an atomic output rename where supported."""
    if os.name == "nt":
        return
    descriptor = os.open(path, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


@dataclass
class _OutputPathLock:
    """Cross-process advisory lock held for an entire output transaction."""

    handle: BinaryIO
    released: bool = False

    def release(self) -> None:
        """Release the platform lock exactly once and close its descriptor."""
        if self.released:
            return
        try:
            if os.name == "nt":
                import msvcrt

                self.handle.seek(0)
                msvcrt.locking(  # type: ignore[attr-defined]
                    self.handle.fileno(),
                    msvcrt.LK_UNLCK,  # type: ignore[attr-defined]
                    1,
                )
            else:
                import fcntl

                fcntl.flock(self.handle.fileno(), fcntl.LOCK_UN)
        finally:
            self.released = True
            self.handle.close()


def _acquire_output_path_lock(target_path: Path) -> _OutputPathLock:
    """Acquire a blocking cross-process lock for one canonical output path."""
    lock_path = target_path.parent / f".{target_path.name}.gobbler-output.lock"
    handle = lock_path.open("a+b")
    try:
        if os.name == "nt":
            import msvcrt

            handle.seek(0)
            if handle.read(1) == b"":
                handle.seek(0)
                handle.write(b"0")
                handle.flush()
            handle.seek(0)
            msvcrt.locking(  # type: ignore[attr-defined]
                handle.fileno(),
                msvcrt.LK_LOCK,  # type: ignore[attr-defined]
                1,
            )
        else:
            import fcntl

            fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        return _OutputPathLock(handle)
    except BaseException:
        handle.close()
        raise


def _canonical_output_path(output_path: Path) -> Path:
    """Resolve an output's actual file target while preserving symlink objects."""
    if output_path.exists() or output_path.is_symlink():
        return output_path.resolve(strict=True)
    return output_path.parent.resolve(strict=False) / output_path.name


@dataclass
class AtomicOutputTransaction:
    """Persisted output that can be restored until a frame bundle commits."""

    path: Path | None
    backup_path: Path | None = None
    created_new: bool = False
    stdout_content: str | None = None
    output_lock: _OutputPathLock | None = None
    completed: bool = False

    def rollback(self) -> None:
        """Restore the prior output after a failed frame bundle commit."""
        if self.completed:
            return
        try:
            if self.path is not None:
                if self.backup_path is not None:
                    self.backup_path.replace(self.path)
                elif self.created_new:
                    self.path.unlink(missing_ok=True)
                _fsync_directory(self.path.parent)
        finally:
            self.stdout_content = None
            self.completed = True
            if self.output_lock is not None:
                self.output_lock.release()

    def finalize(self) -> None:
        """Remove the prior-output backup after the whole transaction succeeds."""
        if self.completed:
            return
        try:
            if self.path is None and self.stdout_content is not None:
                sys.stdout.write(self.stdout_content)
                if not self.stdout_content.endswith("\n"):
                    sys.stdout.write("\n")
                sys.stdout.flush()
            elif self.backup_path is not None:
                self.backup_path.unlink(missing_ok=True)
                _fsync_directory(self.backup_path.parent)
        finally:
            self.stdout_content = None
            self.completed = True
            if self.output_lock is not None:
                self.output_lock.release()


def persist_text_transactionally(content: str, output_path: Path | None) -> AtomicOutputTransaction:
    """Durably emit output and retain a rollback copy until explicitly finalized."""
    if output_path is None:
        return AtomicOutputTransaction(path=None, stdout_content=content)

    target_path = _canonical_output_path(output_path)
    output_parent = target_path.parent
    output_parent.mkdir(parents=True, exist_ok=True)
    output_lock = _acquire_output_path_lock(target_path)
    try:
        temp_descriptor, temp_name = tempfile.mkstemp(
            prefix=f".{target_path.name}.gobbler-output-", dir=output_parent
        )
    except BaseException:
        output_lock.release()
        raise
    temp_path = Path(temp_name)
    backup_path: Path | None = None
    replaced = False
    try:
        with os.fdopen(temp_descriptor, "w", encoding="utf-8") as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        if target_path.exists() or target_path.is_symlink():
            backup_descriptor, backup_name = tempfile.mkstemp(
                prefix=f".{target_path.name}.gobbler-backup-", dir=output_parent
            )
            os.close(backup_descriptor)
            backup_path = Path(backup_name)
            shutil.copy2(target_path, backup_path, follow_symlinks=True)
            with backup_path.open("rb") as backup_stream:
                os.fsync(backup_stream.fileno())
        temp_path.replace(target_path)
        replaced = True
        _fsync_directory(output_parent)
        return AtomicOutputTransaction(
            path=target_path,
            backup_path=backup_path,
            created_new=backup_path is None,
            output_lock=output_lock,
        )
    except BaseException:
        try:
            temp_path.unlink(missing_ok=True)
            if replaced:
                try:
                    if backup_path is not None:
                        backup_path.replace(target_path)
                    else:
                        target_path.unlink(missing_ok=True)
                    _fsync_directory(output_parent)
                except OSError:
                    # Preserve the backup as the only recoverable prior copy.
                    pass
            elif backup_path is not None:
                backup_path.unlink(missing_ok=True)
        finally:
            output_lock.release()
        raise


def _open_command(output_path: Path, platform: str = sys.platform) -> list[str]:
    """Build the platform-native command used to open an output file."""
    if platform == "darwin":
        return ["open", str(output_path)]
    if platform.startswith(("linux", "freebsd")):
        return ["xdg-open", str(output_path)]
    if platform == "win32":
        return ["explorer", str(output_path)]
    msg = f"Opening output files is not supported on platform {platform!r}."
    raise RuntimeError(msg)


def validate_open_request(
    open_requested: bool,
    output_path: Path | None,
    output_format: OutputFormat,
    *,
    interactive: bool | None = None,
) -> None:
    """Validate that an output-open request is safe for an interactive CLI session."""
    if not open_requested:
        return
    if output_path is None:
        message = "--open requires an output file; provide --output PATH."
        raise ValueError(message)
    if output_format == OutputFormat.JSON:
        message = "--open cannot be used with --format json; JSON mode is noninteractive."
        raise ValueError(message)
    if os.environ.get("CI"):
        message = "--open cannot be used in CI; it would launch a desktop application."
        raise ValueError(message)
    is_interactive = sys.stdout.isatty() if interactive is None else interactive
    if not is_interactive:
        message = "--open requires an interactive terminal; omit it for scripts and automation."
        raise ValueError(message)


def open_output_file(
    output_path: Path,
    *,
    platform: str = sys.platform,
    opener: Any = subprocess.Popen,
) -> None:
    """Open a completed conversion output with the platform-native application."""
    command = _open_command(output_path, platform)
    try:
        opener(command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except OSError as exc:
        msg = f"Could not open {output_path}: {exc}"
        raise RuntimeError(msg) from exc


class OutputFormat(StrEnum):
    """Supported output formats."""

    MARKDOWN = "markdown"
    JSON = "json"
    TABLE = "table"


def add_json_contract(data: dict[str, Any]) -> dict[str, Any]:
    """Return data with the current CLI JSON schema marker."""
    return {**data, "schema_version": JSON_SCHEMA_VERSION}


def write_output(
    content: str,
    output_path: Path | None = None,
    output_format: OutputFormat = OutputFormat.MARKDOWN,  # noqa: ARG001
) -> None:
    """Write content to file or stdout.

    Args:
        content: The content to write
        output_path: Optional file path to write to (stdout if None)
        output_format: Output format (only used for display, not file writing)
    """
    if output_path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(content, encoding="utf-8")
        console.print(f"[green]✓[/green] Written to {output_path}")
    else:
        # Write to stdout
        sys.stdout.write(content)
        if not content.endswith("\n"):
            sys.stdout.write("\n")


def write_json(
    data: dict[str, Any],
    output_path: Path | None = None,
) -> None:
    """Write JSON data to file or stdout.

    Args:
        data: Dictionary to serialize as JSON
        output_path: Optional file path to write to (stdout if None)
    """
    json_str = json.dumps(data, indent=2, ensure_ascii=False)
    write_output(json_str, output_path, OutputFormat.JSON)


def format_json_success(
    markdown: str,
    metadata: dict[str, Any],
    source: str | None = None,
) -> dict[str, Any]:
    """Format a successful conversion result as JSON.

    Args:
        markdown: The converted markdown content
        metadata: Metadata from the converter
        source: Optional source identifier (URL, file path, etc.)

    Returns:
        Standardized JSON response dict
    """
    response: dict[str, Any] = add_json_contract(
        {
            "success": True,
            "markdown": markdown,
            "metadata": metadata,
        }
    )
    if source:
        response["metadata"]["source"] = source
    return response


def format_json_error(
    error: str,
    error_code: str = "CONVERSION_ERROR",
    source: str | None = None,
    suggestion: str | None = None,
) -> dict[str, Any]:
    """Format an error result as JSON.

    Args:
        error: Error message
        error_code: Error code identifier
        source: Optional source identifier
        suggestion: Optional suggestion for fixing the error (auto-detected if not provided)

    Returns:
        Standardized JSON error response dict
    """
    response: dict[str, Any] = add_json_contract(
        {
            "success": False,
            "error": error,
            "error_code": error_code,
        }
    )
    if source:
        response["source"] = source

    # Auto-detect suggestion from consolidated knowledge base
    if suggestion is None:
        from gobbler_cli.knowledge import get_suggestion_for_error

        suggestion = get_suggestion_for_error(error_code, error)

    if suggestion:
        response["suggestion"] = suggestion

    return response


def write_json_result(
    result: dict[str, Any],
    output_path: Path | None = None,
) -> None:
    """Write a JSON result to file or stdout without decoration.

    Unlike write_output, this doesn't add any status messages.
    Suitable for piping to other tools.

    Args:
        result: Dictionary to serialize as JSON
        output_path: Optional file path to write to (stdout if None)
    """
    json_str = json.dumps(result, indent=2, ensure_ascii=False)
    if output_path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json_str, encoding="utf-8")
    else:
        sys.stdout.write(json_str)
        sys.stdout.write("\n")


def print_error(message: str) -> None:
    """Print an error message to stderr."""
    error_console.print(f"[red]Error:[/red] {message}")


def print_success(message: str) -> None:
    """Print a success message."""
    console.print(f"[green]✓[/green] {message}")


def print_info(message: str) -> None:
    """Print an info message."""
    console.print(f"[blue]i[/blue] {message}")


def print_warning(message: str) -> None:
    """Print a warning message."""
    console.print(f"[yellow]⚠[/yellow] {message}")


def create_table(
    title: str,
    columns: list[str],
    rows: list[list[str]],
) -> Table:
    """Create a rich table for display.

    Args:
        title: Table title
        columns: Column headers
        rows: List of row data

    Returns:
        A rich Table object
    """
    table = Table(title=title, show_header=True, header_style="bold magenta")

    for column in columns:
        table.add_column(column)

    for row in rows:
        table.add_row(*row)

    return table


def print_table(
    title: str,
    columns: list[str],
    rows: list[list[str]],
) -> None:
    """Print a formatted table.

    Args:
        title: Table title
        columns: Column headers
        rows: List of row data
    """
    table = create_table(title, columns, rows)
    console.print(table)
