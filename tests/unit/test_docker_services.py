"""Tests for Docker service startup preflight logic."""

from __future__ import annotations

import json
import subprocess
from collections.abc import Sequence
from io import StringIO

from gobbler_cli import docker_services


def inspect_payload(*, running: bool, status: str, health: str | None) -> str:
    """Build Docker inspect JSON for a container state."""
    state: dict[str, object] = {
        "Running": running,
        "Status": status,
    }
    if health is not None:
        state["Health"] = {"Status": health}
    return json.dumps([{"State": state}])


class FakeDockerRunner:
    """Fake Docker command runner that never touches real containers."""

    def __init__(self, states: dict[str, str | None], *, compose_command: str = "docker-compose"):
        self.states = states
        self.compose_command = compose_command
        self.calls: list[list[str]] = []

    def __call__(self, args: Sequence[str]) -> subprocess.CompletedProcess[str]:
        self.calls.append(list(args))

        if list(args[:3]) == ["docker", "container", "inspect"]:
            return self._inspect(args[3])

        if list(args) == ["docker-compose", "version"]:
            return self._complete(
                args, returncode=0 if self.compose_command == "docker-compose" else 127
            )

        if list(args) == ["docker", "compose", "version"]:
            return self._complete(
                args, returncode=0 if self.compose_command == "docker compose" else 127
            )

        if list(args[:3]) in (["docker-compose", "up", "-d"], ["docker", "compose", "up"]):
            return self._complete(args)

        return self._complete(args, returncode=1, stderr="unexpected command")

    def _inspect(self, name: str) -> subprocess.CompletedProcess[str]:
        payload = self.states.get(name)
        if payload is None:
            return self._complete(
                ["docker", "container", "inspect", name],
                returncode=1,
                stdout="[]\n",
                stderr=f"Error response from daemon: No such container: {name}",
            )
        return self._complete(["docker", "container", "inspect", name], stdout=payload)

    @staticmethod
    def _complete(
        args: Sequence[str],
        *,
        returncode: int = 0,
        stdout: str = "",
        stderr: str = "",
    ) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(
            args=list(args), returncode=returncode, stdout=stdout, stderr=stderr
        )


def test_start_services_skips_compose_when_named_containers_are_healthy() -> None:
    """Existing healthy named containers satisfy startup."""
    runner = FakeDockerRunner(
        {
            "gobbler-crawl4ai": inspect_payload(running=True, status="running", health="healthy"),
            "gobbler-docling": inspect_payload(running=True, status="running", health="healthy"),
        }
    )
    output = StringIO()

    exit_code = docker_services.start_services(runner=runner, stdout=output)

    assert exit_code == 0
    assert "Docker services already available" in output.getvalue()
    assert not any("up" in call for call in runner.calls)


def test_start_services_starts_only_missing_services() -> None:
    """A healthy named container is left alone while missing services are created."""
    runner = FakeDockerRunner(
        {
            "gobbler-crawl4ai": inspect_payload(running=True, status="running", health="healthy"),
            "gobbler-docling": None,
        }
    )
    output = StringIO()

    exit_code = docker_services.start_services(runner=runner, stdout=output)

    assert exit_code == 0
    assert ["docker-compose", "up", "-d", "docling"] in runner.calls
    assert all("gobbler-crawl4ai" not in call for call in runner.calls if "up" in call)
    assert "Started missing Docker services: Docling" in output.getvalue()


def test_start_services_blocks_stopped_named_container() -> None:
    """Stopped existing containers require explicit remediation before startup."""
    runner = FakeDockerRunner(
        {
            "gobbler-crawl4ai": inspect_payload(running=True, status="running", health="healthy"),
            "gobbler-docling": inspect_payload(running=False, status="exited", health=None),
        }
    )
    output = StringIO()

    exit_code = docker_services.start_services(runner=runner, stdout=output)

    assert exit_code == 2
    assert not any("up" in call for call in runner.calls)
    assert "Docling: exited" in output.getvalue()
    assert "docker logs gobbler-docling --tail 50" in output.getvalue()
    assert "docker rm gobbler-docling" in output.getvalue()


def test_start_services_blocks_unhealthy_named_container() -> None:
    """Unhealthy existing containers are reported without destructive action."""
    runner = FakeDockerRunner(
        {
            "gobbler-crawl4ai": inspect_payload(running=True, status="running", health="unhealthy"),
            "gobbler-docling": inspect_payload(running=True, status="running", health="healthy"),
        }
    )
    output = StringIO()

    exit_code = docker_services.start_services(runner=runner, stdout=output)

    assert exit_code == 2
    assert not any("up" in call for call in runner.calls)
    assert "Crawl4AI: running/unhealthy" in output.getvalue()
    assert "docker stop gobbler-crawl4ai && docker rm gobbler-crawl4ai" in output.getvalue()


def test_show_status_reports_named_container_and_endpoint_health() -> None:
    """Status uses named containers and health endpoints, not Compose project state."""
    runner = FakeDockerRunner(
        {
            "gobbler-crawl4ai": inspect_payload(running=True, status="running", health="healthy"),
            "gobbler-docling": None,
        }
    )
    output = StringIO()

    exit_code = docker_services.show_status(
        runner=runner,
        health_checker=lambda url: url.endswith(":11235/health"),
        stdout=output,
    )

    assert exit_code == 0
    text = output.getvalue()
    assert "Crawl4AI: running/healthy (gobbler-crawl4ai)" in text
    assert "Docling: not found (gobbler-docling)" in text
    assert "Crawl4AI: healthy (http://localhost:11235)" in text
    assert "Docling: unavailable (http://localhost:5001)" in text
