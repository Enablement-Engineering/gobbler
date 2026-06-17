"""CLI integration helpers for the job queue system.

This module provides helper functions for CLI commands to interact with
the job queue system, including job creation, formatting, and worker
daemon management.
"""

import json
import os
import shlex
import signal
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

from .manager import JobManager
from .models import Job, JobSummary, JobType

# PID file location for the worker daemon
WORKER_PID_FILE = Path.home() / ".cache" / "gobbler" / "worker.pid"


def queue_job(job_type: str, command: list[str], args: dict[str, Any]) -> str:
    """Create a job and return its ID.

    Args:
        job_type: String name of the job type (e.g., 'youtube', 'audio').
        command: List of command arguments to execute.
        args: Additional arguments to store with the job.

    Returns:
        The unique job ID.

    Raises:
        ValueError: If job_type is not a valid JobType.

    Example:
        job_id = queue_job(
            "youtube",
            ["gobbler", "youtube", "https://youtube.com/watch?v=..."],
            {"url": "https://youtube.com/watch?v=..."}
        )
    """
    # Validate and convert job type
    try:
        jtype = JobType(job_type.lower())
    except ValueError as err:
        valid_types = [t.value for t in JobType]
        msg = f"Invalid job type '{job_type}'. Valid types: {', '.join(valid_types)}"
        raise ValueError(msg) from err

    command_argv = list(command)
    command_str = shlex.join(command_argv)

    manager = JobManager()
    job = manager.create_job(job_type=jtype, command=command_str, args=args, argv=command_argv)

    return job.id


def format_job_table(jobs: list[JobSummary]) -> str:
    """Format a list of jobs as an ASCII table.

    Args:
        jobs: List of JobSummary objects to format.

    Returns:
        Formatted ASCII table string.

    Example output:
        ID                                   | Type     | Status    | Progress | Created
        -------------------------------------|----------|-----------|----------|--------------------
        abc123...                            | youtube  | running   | 45%      | 2024-01-15 10:30:00
        def456...                            | audio    | completed | 100%     | 2024-01-15 10:25:00
    """
    if not jobs:
        return "No jobs found."

    # Column definitions: (header, width, getter)
    columns = [
        ("ID", 36, lambda j: j.id[:36]),
        ("Type", 14, lambda j: j.job_type.value),
        ("Status", 10, lambda j: j.status.value),
        ("Progress", 8, lambda j: f"{j.progress}%"),
        ("Created", 19, lambda j: j.created_at.strftime("%Y-%m-%d %H:%M:%S")),
    ]

    # Build header
    header = " | ".join(h.ljust(w) for h, w, _ in columns)
    separator = "-|-".join("-" * w for _, w, _ in columns)

    # Build rows
    rows = []
    for job in jobs:
        row = " | ".join(getter(job).ljust(w) for _, w, getter in columns)
        rows.append(row)

    # Add error column if any jobs have errors
    if any(j.error for j in jobs):
        error_jobs = [j for j in jobs if j.error]
        if error_jobs:
            rows.append("")
            rows.append("Errors:")
            for job in error_jobs:
                rows.append(f"  {job.id[:8]}...: {job.error}")

    return "\n".join([header, separator, *rows])


def format_job_detail(job: Job) -> str:  # noqa: C901, PLR0912
    """Format a single job as a detailed view.

    Args:
        job: Job object to format.

    Returns:
        Formatted detailed view string.

    Example output:
        Job Details
        ===========
        ID:       abc123-def456-...
        Type:     youtube
        Status:   running
        Progress: 45% - Downloading video...
        Command:  gobbler youtube https://...
        ...
    """
    lines = [
        "Job Details",
        "===========",
        f"ID:       {job.id}",
        f"Type:     {job.job_type.value}",
        f"Status:   {job.status.value}",
    ]

    # Progress
    if job.progress_message:
        lines.append(f"Progress: {job.progress}% - {job.progress_message}")
    else:
        lines.append(f"Progress: {job.progress}%")

    # Command
    lines.append(f"Command:  {job.command}")
    if job.argv is not None:
        lines.append(f"Argv:     {json.dumps(job.argv)}")

    # Arguments (if any)
    if job.args:
        lines.append(f"Args:     {json.dumps(job.args, indent=2)}")

    # Timestamps
    lines.append("")
    lines.append("Timestamps")
    lines.append("----------")
    lines.append(f"Created:   {_format_timestamp(job.created_at)}")

    if job.started_at:
        lines.append(f"Started:   {_format_timestamp(job.started_at)}")

    if job.completed_at:
        lines.append(f"Completed: {_format_timestamp(job.completed_at)}")

    # Duration
    if job.duration:
        total_seconds = int(job.duration.total_seconds())
        hours, remainder = divmod(total_seconds, 3600)
        minutes, seconds = divmod(remainder, 60)
        if hours:
            duration_str = f"{hours}h {minutes}m {seconds}s"
        elif minutes:
            duration_str = f"{minutes}m {seconds}s"
        else:
            duration_str = f"{seconds}s"
        lines.append(f"Duration:  {duration_str}")

    # Worker info
    if job.worker_pid:
        lines.append(f"Worker:    PID {job.worker_pid}")

    # Error (if any)
    if job.error:
        lines.append("")
        lines.append("Error")
        lines.append("-----")
        lines.append(job.error)

    # Result (if any)
    if job.result:
        lines.append("")
        lines.append("Result")
        lines.append("------")
        # Show stdout preview
        stdout = job.result.get("stdout", "")
        if stdout:
            max_preview_len = 500
            preview = stdout[:max_preview_len]
            if len(stdout) > max_preview_len:
                preview += "\n... (truncated)"
            lines.append(preview)

    return "\n".join(lines)


def start_worker_daemon() -> int:
    """Start the worker as a background daemon.

    The worker process is started detached from the current terminal
    and its PID is written to ~/.cache/gobbler/worker.pid.

    Returns:
        The PID of the started worker process.

    Raises:
        RuntimeError: If a worker is already running.
    """
    if is_worker_running():
        pid = _read_pid_file()
        msg = f"Worker is already running (PID: {pid})"
        raise RuntimeError(msg)

    # Ensure cache directory exists
    WORKER_PID_FILE.parent.mkdir(parents=True, exist_ok=True)

    # Start the worker as a daemon process
    # Use nohup-like behavior by redirecting stdout/stderr
    log_file = WORKER_PID_FILE.parent / "worker.log"

    # Build the command to run the worker module
    cmd = [
        sys.executable,
        "-m",
        "gobbler_queue",
        "--log-level",
        "INFO",
    ]

    # Open log file for output
    with log_file.open("a") as log:
        # Start process in background, detached from terminal
        # cmd is built from sys.executable and module paths (not user input)
        process = subprocess.Popen(  # nosec B603
            cmd,
            stdout=log,
            stderr=subprocess.STDOUT,
            stdin=subprocess.DEVNULL,
            start_new_session=True,  # Detach from terminal
        )

    # Write PID to file
    WORKER_PID_FILE.write_text(str(process.pid))

    return process.pid


def stop_worker_daemon() -> bool:
    """Stop the worker daemon.

    Sends SIGTERM to the worker process to allow graceful shutdown.

    Returns:
        True if the worker was stopped, False if no worker was running.
    """
    pid = _read_pid_file()
    if pid is None:
        return False

    try:
        # Send SIGTERM for graceful shutdown
        os.kill(pid, signal.SIGTERM)

        # Remove PID file
        if WORKER_PID_FILE.exists():
            WORKER_PID_FILE.unlink()
    except ProcessLookupError:
        # Process already exited, clean up PID file
        if WORKER_PID_FILE.exists():
            WORKER_PID_FILE.unlink()
        return False
    except PermissionError:
        # Can't kill the process (owned by different user?)
        return False
    else:
        return True


def is_worker_running() -> bool:
    """Check if the worker daemon is running.

    Returns:
        True if the worker is running, False otherwise.
    """
    pid = _read_pid_file()
    if pid is None:
        return False

    try:
        # Check if process exists (signal 0 doesn't send a signal)
        os.kill(pid, 0)
    except ProcessLookupError:
        # Process doesn't exist, clean up stale PID file
        if WORKER_PID_FILE.exists():
            WORKER_PID_FILE.unlink()
        return False
    except PermissionError:
        # Process exists but we can't signal it (different user)
        return True
    else:
        return True


def get_worker_pid() -> int | None:
    """Get the PID of the running worker daemon.

    Returns:
        The worker PID if running, None otherwise.
    """
    if is_worker_running():
        return _read_pid_file()
    return None


def _read_pid_file() -> int | None:
    """Read the PID from the PID file.

    Returns:
        The PID as an integer, or None if the file doesn't exist
        or contains invalid data.
    """
    if not WORKER_PID_FILE.exists():
        return None

    try:
        content = WORKER_PID_FILE.read_text().strip()
        return int(content)
    except (ValueError, OSError):
        return None


def _format_timestamp(dt: datetime | None) -> str:
    """Format a datetime for display.

    Args:
        dt: Datetime to format, or None.

    Returns:
        Formatted string or '-' if None.
    """
    if dt is None:
        return "-"
    return dt.strftime("%Y-%m-%d %H:%M:%S")
