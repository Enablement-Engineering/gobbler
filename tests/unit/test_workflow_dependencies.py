"""Static contracts for GitHub Actions dependency versions."""

from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
WORKFLOW_DIR = ROOT / ".github" / "workflows"


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
