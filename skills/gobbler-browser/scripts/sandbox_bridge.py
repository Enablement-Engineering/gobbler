#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""
Sandbox Bridge for Claude Desktop

Detects if running in a sandboxed environment (like Claude Desktop's code execution)
and provides a bridge to execute commands on the host macOS via AppleScript.

Sandbox Detection:
- Claude Desktop sandbox typically has restricted $HOME (e.g., /mnt/user or similar)
- Cannot access localhost network services
- Limited filesystem access

Usage:
    from sandbox_bridge import is_sandboxed, run_on_host

    if is_sandboxed():
        result = run_on_host("uv run browser_api.py check")
    else:
        # Run directly
        ...
"""

import os
import shutil
import subprocess
import sys
from pathlib import Path


def is_sandboxed() -> bool:
    """Detect if running in a sandboxed environment.

    Checks multiple indicators:
    1. CLAUDE_DESKTOP_SANDBOX env var (explicit)
    2. HOME doesn't start with /Users (macOS native)
    3. Running from /mnt/ path (common sandbox mount)
    4. Cannot connect to localhost:4625 (network restricted) - most reliable

    Returns:
        True if likely running in a sandbox, False otherwise.
    """
    # Check 1: Explicit env var (most reliable if set)
    if os.environ.get("CLAUDE_DESKTOP_SANDBOX"):
        return True

    home = os.environ.get("HOME", "")

    # Check 2: HOME path indicator
    # Native macOS: /Users/username
    # Sandbox: /mnt/user, /home/user, /tmp/..., etc.
    if not home.startswith("/Users/"):
        return True

    # Check 3: Running from sandbox mount path
    cwd = os.getcwd()
    if cwd.startswith("/mnt/"):
        return True

    # Check 4: Network connectivity test (most reliable detection)
    # If we can't reach localhost:4625, we're likely sandboxed
    # This is slower but catches cases where HOME looks normal
    try:
        import socket

        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(1)
        result = sock.connect_ex(("127.0.0.1", 4625))
        sock.close()
        # If connection refused (111) or success (0), we CAN reach localhost
        # If timeout or other error, we're likely sandboxed
        if result not in (0, 111):  # 111 = connection refused (server not running but reachable)
            return True
    except Exception:
        # Any socket error suggests sandbox
        return True

    return False


def get_project_root():
    """Get project root directory dynamically."""
    from pathlib import Path
    import os

    # Walk up from this script to find pyproject.toml
    current = Path(__file__).resolve()
    for parent in current.parents:
        if (parent / "pyproject.toml").exists():
            return str(parent)
    # Fallback to environment variable
    return os.environ.get("GOBBLER_ROOT", str(Path.home() / "Projects" / "gobbler"))


def get_host_project_path() -> str:
    """Get the Gobbler project path on the host machine.

    This is used when running via AppleScript to know where to execute commands.
    Can be overridden via GOBBLER_PROJECT_PATH env var.
    """
    # Allow explicit override
    if path := os.environ.get("GOBBLER_PROJECT_PATH"):
        return path

    # Use dynamic detection
    return get_project_root()


def run_on_host(command: str, cwd: str | None = None, timeout: int = 120) -> tuple[int, str, str]:
    """Execute a command on the host macOS via AppleScript.

    Args:
        command: Shell command to execute
        cwd: Working directory (defaults to Gobbler project root)
        timeout: Command timeout in seconds

    Returns:
        Tuple of (exit_code, stdout, stderr)

    Raises:
        RuntimeError: If AppleScript execution fails
    """
    if cwd is None:
        cwd = get_host_project_path()

    # Build the shell command with cd
    full_command = f'cd "{cwd}" && {command}'

    # Use AppleScript to execute on host
    # Note: 'do shell script' runs in sh, not bash
    applescript = f'''
        do shell script "{full_command.replace('"', '\\"')}"
    '''

    try:
        result = subprocess.run(
            ["osascript", "-e", applescript],
            capture_output=True,
            text=True,
            timeout=timeout,
        )

        # AppleScript 'do shell script' returns stdout on success
        # On failure, it raises an error which osascript captures in stderr
        return result.returncode, result.stdout.strip(), result.stderr.strip()

    except subprocess.TimeoutExpired:
        return 124, "", f"Command timed out after {timeout} seconds"
    except FileNotFoundError:
        raise RuntimeError("osascript not found - AppleScript bridge requires macOS")
    except Exception as e:
        raise RuntimeError(f"AppleScript execution failed: {e}")


def run_browser_command(args: list[str], timeout: int = 120) -> tuple[int, str, str]:
    """Run a browser_api.py command, using AppleScript bridge if sandboxed.

    Args:
        args: Arguments to pass to browser_api.py (e.g., ["check"] or ["tabs"])
        timeout: Command timeout in seconds

    Returns:
        Tuple of (exit_code, stdout, stderr)
    """
    script_path = "skills/gobbler-browser/scripts/browser_api.py"
    command = f"uv run {script_path} {' '.join(args)}"

    if is_sandboxed():
        return run_on_host(command, timeout=timeout)
    else:
        # Run directly
        try:
            result = subprocess.run(
                ["uv", "run", str(Path(__file__).parent / "browser_api.py")] + args,
                capture_output=True,
                text=True,
                timeout=timeout,
            )
            return result.returncode, result.stdout, result.stderr
        except subprocess.TimeoutExpired:
            return 124, "", f"Command timed out after {timeout} seconds"


def run_notebooklm_command(args: list[str], timeout: int = 120) -> tuple[int, str, str]:
    """Run a notebooklm.py command, using AppleScript bridge if sandboxed.

    Args:
        args: Arguments to pass to notebooklm.py (e.g., ["query", "What is X?"])
        timeout: Command timeout in seconds

    Returns:
        Tuple of (exit_code, stdout, stderr)
    """
    script_path = "skills/gobbler-browser/scripts/notebooklm.py"

    # Quote arguments that contain spaces
    quoted_args = []
    for arg in args:
        if " " in arg:
            quoted_args.append(f'"{arg}"')
        else:
            quoted_args.append(arg)

    command = f"uv run {script_path} {' '.join(quoted_args)}"

    if is_sandboxed():
        return run_on_host(command, timeout=timeout)
    else:
        # Run directly
        try:
            result = subprocess.run(
                ["uv", "run", str(Path(__file__).parent / "notebooklm.py")] + args,
                capture_output=True,
                text=True,
                timeout=timeout,
            )
            return result.returncode, result.stdout, result.stderr
        except subprocess.TimeoutExpired:
            return 124, "", f"Command timed out after {timeout} seconds"


# CLI for testing
if __name__ == "__main__":
    import json

    print("=== Sandbox Bridge Diagnostics ===\n")

    print(f"Is sandboxed: {is_sandboxed()}")
    print(f"HOME: {os.environ.get('HOME', 'not set')}")
    print(f"PWD: {os.getcwd()}")
    print(f"Host project path: {get_host_project_path()}")

    print("\n=== Testing AppleScript Bridge ===\n")

    try:
        exit_code, stdout, stderr = run_on_host("echo 'Hello from host'")
        print(f"Exit code: {exit_code}")
        print(f"Stdout: {stdout}")
        if stderr:
            print(f"Stderr: {stderr}")
        print("\nAppleScript bridge is working!")
    except Exception as e:
        print(f"AppleScript bridge failed: {e}")

    print("\n=== Testing Browser Command ===\n")

    exit_code, stdout, stderr = run_browser_command(["check"])
    print(f"Exit code: {exit_code}")
    print(f"Output:\n{stdout}")
    if stderr:
        print(f"Stderr:\n{stderr}")
