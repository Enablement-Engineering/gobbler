"""Ensure release version metadata remains synchronized."""

import json
import re
import tomllib
from pathlib import Path

import gobbler_cli
import gobbler_core
import gobbler_queue

ROOT = Path(__file__).resolve().parents[2]


def test_release_versions_are_synchronized() -> None:
    """Package and extension metadata should share one release version."""
    project_version = tomllib.loads((ROOT / "pyproject.toml").read_text())["project"]["version"]
    manifest_version = json.loads((ROOT / "browser-extension" / "manifest.json").read_text())[
        "version"
    ]
    background = (ROOT / "browser-extension" / "background.js").read_text()
    match = re.search(r"extension_version:\s*'([^']+)'", background)

    assert match is not None
    assert {
        project_version,
        gobbler_cli.__version__,
        gobbler_core.__version__,
        gobbler_queue.__version__,
        manifest_version,
        match.group(1),
    } == {project_version}
