"""Unit tests for opening completed single-item conversion outputs."""

from inspect import signature
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from gobbler_cli.commands import convert
from gobbler_cli.output import OutputFormat, _open_command, open_output_file, validate_open_request


@pytest.mark.parametrize(
    ("platform", "expected"),
    [
        ("darwin", ["open", "result.md"]),
        ("linux", ["xdg-open", "result.md"]),
        ("freebsd14", ["xdg-open", "result.md"]),
        ("win32", ["explorer", "result.md"]),
    ],
)
def test_open_command_is_platform_aware(platform: str, expected: list[str]) -> None:
    """Each supported platform uses an argument vector without shell interpolation."""
    assert _open_command(Path("result.md"), platform) == expected


def test_open_command_rejects_unknown_platform() -> None:
    """Unknown platforms fail with actionable guidance."""
    with pytest.raises(RuntimeError, match="not supported on platform"):
        _open_command(Path("result.md"), "plan9")


@pytest.mark.parametrize(
    ("path", "output_format", "interactive", "message"),
    [
        (None, OutputFormat.MARKDOWN, True, "requires an output file"),
        (Path("result.json"), OutputFormat.JSON, True, "cannot be used with --format json"),
        (Path("result.md"), OutputFormat.MARKDOWN, False, "interactive terminal"),
    ],
)
def test_validate_open_request_guards_automation(
    path: Path | None, output_format: OutputFormat, interactive: bool, message: str
) -> None:
    """Opening is blocked for stdout, JSON, and noninteractive conversion modes."""
    opener = MagicMock()
    with pytest.raises(ValueError, match=message):
        validate_open_request(True, path, output_format, interactive=interactive)
    opener.assert_not_called()


def test_validate_open_request_is_noop_when_not_requested() -> None:
    """Normal automation behavior is unchanged when --open is absent."""
    validate_open_request(False, None, OutputFormat.JSON, interactive=False)


@pytest.mark.parametrize(
    "command",
    [convert.youtube, convert.audio, convert.document, convert.webpage],
)
def test_supported_single_item_commands_expose_open_option(command: object) -> None:
    """Every supported single-item conversion command explicitly exposes --open."""
    parameter = signature(command).parameters["open_result"]
    assert "--open" in repr(parameter.annotation)


def test_open_output_file_uses_mocked_opener() -> None:
    """The helper launches the constructed command without invoking a real application."""
    opener = MagicMock()
    open_output_file(Path("result with spaces.md"), platform="darwin", opener=opener)
    assert opener.call_args.args[0] == ["open", "result with spaces.md"]


def test_open_output_file_reports_launcher_failure() -> None:
    """A missing platform opener produces clear, path-specific guidance."""
    opener = MagicMock(side_effect=FileNotFoundError("missing"))
    with pytest.raises(RuntimeError, match=r"Could not open result\.md: missing"):
        open_output_file(Path("result.md"), platform="linux", opener=opener)
