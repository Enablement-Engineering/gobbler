"""Docker service startup helpers for local Gobbler dependencies."""

from __future__ import annotations

import argparse
import http.client
import json
import subprocess
import sys
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import TextIO
from urllib.parse import urlparse


@dataclass(frozen=True)
class ServiceSpec:
    """Configuration for one Docker-backed Gobbler service."""

    label: str
    compose_name: str
    container_name: str
    base_url: str
    health_url: str


@dataclass(frozen=True)
class ContainerState:
    """State reported by Docker for a named service container."""

    name: str
    exists: bool
    running: bool = False
    status: str = "not found"
    health: str | None = None


CommandRunner = Callable[[Sequence[str]], subprocess.CompletedProcess[str]]
HealthChecker = Callable[[str], bool]
HTTP_OK = 200
HTTP_REDIRECT_CEILING = 400

SERVICES: tuple[ServiceSpec, ...] = (
    ServiceSpec(
        label="Crawl4AI",
        compose_name="crawl4ai",
        container_name="gobbler-crawl4ai",
        base_url="http://localhost:11235",
        health_url="http://localhost:11235/health",
    ),
    ServiceSpec(
        label="Docling",
        compose_name="docling",
        container_name="gobbler-docling",
        base_url="http://localhost:5001",
        health_url="http://localhost:5001/health",
    ),
)


class DockerServiceError(RuntimeError):
    """Raised when Docker cannot be queried or started safely."""


def start_services(
    *,
    runner: CommandRunner | None = None,
    stdout: TextIO | None = None,
) -> int:
    """Start missing Docker services without disturbing existing containers.

    Args:
        runner: Command runner used for Docker and Compose commands.
        stdout: Stream for user-facing output.

    Returns:
        Process exit code. ``0`` means services are available or startup was
        initiated. ``2`` means an existing named container requires manual
        remediation before startup can proceed.
    """
    command_runner = runner or _run_command
    output = stdout or sys.stdout

    try:
        states = _inspect_services(command_runner)
    except DockerServiceError as exc:
        _write_line(output, f"Docker is unavailable: {exc}")
        _write_line(
            output,
            "Start Docker Desktop or the Docker daemon, then retry `make start-docker`.",
        )
        return 1

    blocking = [
        (service, states[service.container_name])
        for service in SERVICES
        if states[service.container_name].exists and not _is_ready(states[service.container_name])
    ]
    if blocking:
        _write_line(output, "Docker service containers exist but are not ready:")
        for service, state in blocking:
            _write_line(output, f"  - {service.label}: {_format_state(state)} ({state.name})")
        _write_line(output)
        _write_line(output, "Remediation:")
        for _, state in blocking:
            _write_line(output, f"  - Inspect logs: docker logs {state.name} --tail 50")
            if state.running:
                stale_command = f"docker stop {state.name} && docker rm {state.name}"
                _write_line(output, f"  - If stale: {stale_command}")
            else:
                _write_line(output, f"  - If stale: docker rm {state.name}")
        _write_line(output, "  - Retry: make start-docker")
        return 2

    missing = [service for service in SERVICES if not states[service.container_name].exists]
    if not missing:
        _write_line(output, "Docker services already available:")
        for service in SERVICES:
            _write_line(output, f"  - {service.label}: {service.base_url}")
        return 0

    try:
        compose_command = _find_compose_command(command_runner)
        command = [*compose_command, "up", "-d", *(service.compose_name for service in missing)]
        result = command_runner(command)
    except DockerServiceError as exc:
        _write_line(output, f"Docker Compose is unavailable: {exc}")
        return 1

    if result.returncode != 0:
        _write_line(output, "Docker Compose failed to start missing services:")
        _write_line(output, _command_error(result))
        return result.returncode or 1

    _write_line(
        output,
        "Started missing Docker services: " + ", ".join(service.label for service in missing),
    )
    _write_line(output, "Services:")
    for service in SERVICES:
        _write_line(output, f"  - {service.label}: {service.base_url}")
    _write_line(output, "Run `make status` to check readiness.")
    return 0


def show_status(
    *,
    runner: CommandRunner | None = None,
    health_checker: HealthChecker | None = None,
    stdout: TextIO | None = None,
) -> int:
    """Print service container and endpoint health status.

    Args:
        runner: Command runner used for Docker inspect commands.
        health_checker: Callable used to check HTTP health endpoints.
        stdout: Stream for user-facing output.

    Returns:
        Process exit code. Status reporting is best-effort and returns ``0``
        unless Docker itself cannot be queried.
    """
    command_runner = runner or _run_command
    check_health = health_checker or _check_http_health
    output = stdout or sys.stdout

    _write_line(output, "Docker service containers:")
    try:
        states = _inspect_services(command_runner)
    except DockerServiceError as exc:
        _write_line(output, f"  Docker unavailable: {exc}")
        return 1

    for service in SERVICES:
        state = states[service.container_name]
        _write_line(output, f"  - {service.label}: {_format_state(state)} ({state.name})")

    _write_line(output)
    _write_line(output, "Health endpoints:")
    for service in SERVICES:
        healthy = check_health(service.health_url)
        status = "healthy" if healthy else "unavailable"
        _write_line(output, f"  - {service.label}: {status} ({service.base_url})")

    return 0


def main(argv: Sequence[str] | None = None) -> int:
    """Run the Docker service helper CLI."""
    parser = argparse.ArgumentParser(description="Manage Gobbler Docker service startup.")
    parser.add_argument("command", choices=("start", "status"))
    args = parser.parse_args(argv)

    if args.command == "start":
        return start_services()
    return show_status()


def _run_command(args: Sequence[str]) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(args, check=False, capture_output=True, text=True)
    except FileNotFoundError as exc:
        return subprocess.CompletedProcess(args=args, returncode=127, stdout="", stderr=str(exc))


def _inspect_services(runner: CommandRunner) -> dict[str, ContainerState]:
    return {
        service.container_name: _inspect_container(service.container_name, runner)
        for service in SERVICES
    }


def _is_missing_container(result: subprocess.CompletedProcess[str]) -> bool:
    output = f"{result.stdout}\n{result.stderr}"
    return "No such object" in output or "No such container" in output


def _inspect_container(name: str, runner: CommandRunner) -> ContainerState:
    result = runner(["docker", "container", "inspect", name])
    if result.returncode != 0:
        if _is_missing_container(result):
            return ContainerState(name=name, exists=False)
        raise DockerServiceError(_command_error(result))

    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        message = f"invalid inspect output for {name}"
        raise DockerServiceError(message) from exc

    if not payload:
        return ContainerState(name=name, exists=False)

    state = payload[0].get("State", {})
    health = state.get("Health", {}).get("Status")
    return ContainerState(
        name=name,
        exists=True,
        running=bool(state.get("Running", False)),
        status=str(state.get("Status", "unknown")),
        health=str(health) if health is not None else None,
    )


def _is_ready(state: ContainerState) -> bool:
    return state.exists and state.running and state.health == "healthy"


def _format_state(state: ContainerState) -> str:
    if not state.exists:
        return "not found"
    if state.health:
        return f"{state.status}/{state.health}"
    return state.status


def _find_compose_command(runner: CommandRunner) -> list[str]:
    legacy = runner(["docker-compose", "version"])
    if legacy.returncode == 0:
        return ["docker-compose"]

    plugin = runner(["docker", "compose", "version"])
    if plugin.returncode == 0:
        return ["docker", "compose"]

    message = "install Docker Compose v2 or docker-compose"
    raise DockerServiceError(message)


def _check_http_health(url: str, timeout: float = 5.0) -> bool:
    parsed = urlparse(url)
    if parsed.hostname is None:
        return False

    connection_class = (
        http.client.HTTPSConnection if parsed.scheme == "https" else http.client.HTTPConnection
    )
    port = parsed.port
    path = parsed.path or "/"
    if parsed.query:
        path = f"{path}?{parsed.query}"

    connection = connection_class(parsed.hostname, port, timeout=timeout)
    try:
        connection.request("GET", path)
        response = connection.getresponse()
    except OSError:
        return False
    else:
        return HTTP_OK <= response.status < HTTP_REDIRECT_CEILING
    finally:
        connection.close()


def _command_error(result: subprocess.CompletedProcess[str]) -> str:
    stderr = result.stderr.strip()
    stdout = result.stdout.strip()
    if stderr:
        return stderr
    if stdout:
        return stdout
    return f"command exited with status {result.returncode}: {' '.join(result.args)}"


def _write_line(output: TextIO, line: str = "") -> None:
    output.write(f"{line}\n")


if __name__ == "__main__":
    raise SystemExit(main())
