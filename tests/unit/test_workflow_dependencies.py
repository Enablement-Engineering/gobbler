"""Static contracts for GitHub Actions dependency versions."""

import tomllib
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
WORKFLOW_DIR = ROOT / ".github" / "workflows"
DEPENDABOT_PATH = ROOT / ".github" / "dependabot.yml"
PYPROJECT_PATH = ROOT / "pyproject.toml"


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


def test_integration_tests_are_required_and_run_on_pull_requests() -> None:
    """Relay integration tests should execute as a required, untolerated job."""
    workflow = yaml.safe_load((WORKFLOW_DIR / "test.yml").read_text())
    integration_job = workflow["jobs"]["integration"]

    assert "if" not in integration_job
    assert "services" not in integration_job
    test_steps = [
        step for step in integration_job["steps"] if step.get("name") == "Run integration tests"
    ]
    assert len(test_steps) == 1
    assert test_steps[0]["run"] == "uv run pytest tests/integration/ -v -m integration"
    assert "continue-on-error" not in test_steps[0]


def test_typer_excludes_broken_0270_wheel() -> None:
    """The CLI dependency should avoid Typer's incomplete 0.27.0 wheel."""
    config = tomllib.loads(PYPROJECT_PATH.read_text())
    typer_requirements = [
        requirement
        for requirement in config["project"]["dependencies"]
        if requirement.startswith("typer")
    ]

    assert typer_requirements == ["typer>=0.26.8,!=0.27.0"]
