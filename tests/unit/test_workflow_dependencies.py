"""Static contracts for GitHub Actions dependency versions."""

from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
WORKFLOW_DIR = ROOT / ".github" / "workflows"
DEPENDABOT_PATH = ROOT / ".github" / "dependabot.yml"


def test_dependabot_groups_all_python_update_types() -> None:
    """Python dependency updates should stay in one bounded weekly group."""
    config = yaml.safe_load(DEPENDABOT_PATH.read_text())
    python_updates = next(
        update
        for update in config["updates"]
        if update["package-ecosystem"] == "pip" and update["directory"] == "/"
    )
    groups = python_updates["groups"]

    assert set(groups) == {"python-updates"}
    assert groups["python-updates"]["patterns"] == ["*"]
    assert set(groups["python-updates"]["update-types"]) == {"major", "minor", "patch"}


def test_checkout_action_uses_supported_major_everywhere() -> None:
    """Every workflow checkout step should use the current supported major."""
    checkout_uses: list[str] = []

    workflow_paths = sorted(
        path for path in WORKFLOW_DIR.iterdir() if path.suffix in {".yml", ".yaml"}
    )
    for workflow_path in workflow_paths:
        workflow = yaml.safe_load(workflow_path.read_text())
        for job in workflow.get("jobs", {}).values():
            for step in job.get("steps", []):
                uses = step.get("uses")
                if isinstance(uses, str) and uses.startswith("actions/checkout@"):
                    checkout_uses.append(uses)

    assert checkout_uses
    assert set(checkout_uses) == {"actions/checkout@v7"}


def test_codecov_v7_uses_supported_files_input() -> None:
    """Codecov v7 uploads should use the supported plural files input."""
    codecov_steps: list[dict[str, object]] = []

    workflow_paths = sorted(
        path for path in WORKFLOW_DIR.iterdir() if path.suffix in {".yml", ".yaml"}
    )
    for workflow_path in workflow_paths:
        workflow = yaml.safe_load(workflow_path.read_text())
        for job in workflow.get("jobs", {}).values():
            for step in job.get("steps", []):
                uses = step.get("uses")
                if isinstance(uses, str) and uses.startswith("codecov/codecov-action@v7"):
                    codecov_steps.append(step)

    assert codecov_steps
    for step in codecov_steps:
        inputs = step.get("with")
        assert isinstance(inputs, dict)
        assert inputs.get("files") == "./coverage.xml"
        assert "file" not in inputs
