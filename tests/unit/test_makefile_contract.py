"""Static contracts for public Makefile entry points."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MAKEFILE_PATH = ROOT / "Makefile"


def _target_recipe(makefile: str, target: str) -> list[str]:
    """Return the command lines belonging to one simple Make target."""
    lines = makefile.splitlines()
    start = lines.index(f"{target}:") + 1
    recipe: list[str] = []
    for line in lines[start:]:
        if line.startswith("\t"):
            recipe.append(line.removeprefix("\t"))
        elif recipe:
            break
    return recipe


def test_worker_targets_use_sqlite_job_cli() -> None:
    """Worker targets should delegate to the supported SQLite job CLI."""
    makefile = MAKEFILE_PATH.read_text()
    start_recipe = _target_recipe(makefile, "start")
    worker_recipe = _target_recipe(makefile, "worker")
    stop_recipe = _target_recipe(makefile, "worker-stop")

    assert "RQ worker" not in makefile
    assert "RQ workers" not in makefile
    assert "SQLite job worker" in makefile
    assert ".worker.pid" not in makefile
    assert "pkill" not in makefile
    for recipe in (start_recipe, worker_recipe):
        assert "@uv run gobbler jobs worker start" in recipe
        assert "@sleep 2" in recipe
        assert '@uv run gobbler jobs worker status | grep -F "Worker is running"' in recipe
        assert not any("python -m gobbler_queue" in command for command in recipe)
        assert not any(command.startswith("-") for command in recipe)
    assert "@uv run gobbler jobs worker stop" in stop_recipe
    assert not any(command.startswith("-") for command in stop_recipe)
