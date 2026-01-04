"""Job management commands."""

from __future__ import annotations

from typing import Annotated

import typer

from gobbler_cli.output import print_error, print_info, print_success, print_warning
from gobbler_queue import JobManager, JobStatus
from gobbler_queue.cli_integration import (
    format_job_detail,
    format_job_table,
    get_worker_pid,
    is_worker_running,
    start_worker_daemon,
    stop_worker_daemon,
)

app = typer.Typer(help="Job management")
worker_app = typer.Typer(help="Worker daemon management")
app.add_typer(worker_app, name="worker")


def _get_worker_status_line() -> str:
    """Get a formatted worker status line."""
    if is_worker_running():
        pid = get_worker_pid()
        return f"Worker: running (PID {pid})"
    return "Worker: stopped"


def _parse_status(status_str: str | None) -> JobStatus | None:
    """Parse a status string to JobStatus enum."""
    if status_str is None:
        return None
    try:
        return JobStatus(status_str.lower())
    except ValueError as err:
        valid = ", ".join(s.value for s in JobStatus)
        msg = f"Invalid status '{status_str}'. Valid: {valid}"
        raise typer.BadParameter(msg) from err


@app.command("list")
def list_jobs_cmd(
    status_filter: Annotated[
        str | None,
        typer.Option(
            "--status",
            "-s",
            help="Filter by status (pending/running/completed/failed/cancelled)",
        ),
    ] = None,
    limit: Annotated[
        int,
        typer.Option("--limit", "-l", help="Maximum number of jobs to show"),
    ] = 20,
) -> None:
    """List jobs.

    Examples:
        gobbler jobs list
        gobbler jobs list --status running
        gobbler jobs list --limit 10
    """
    try:
        # Show worker status
        print_info(_get_worker_status_line())
        print_info("")  # Blank line

        # Parse status filter
        status = _parse_status(status_filter)

        # Get jobs from manager
        manager = JobManager()
        jobs = manager.list_jobs(status=status, limit=limit)

        # Format and display
        table_output = format_job_table(jobs)
        print_info(table_output)

    except typer.BadParameter:
        raise
    except Exception as e:
        print_error(f"Failed to list jobs: {e}")
        raise typer.Exit(1) from None


@app.command()
def get(
    job_id: Annotated[str, typer.Argument(help="Job ID")],
    show_result: Annotated[  # noqa: ARG001 - Reserved for future use
        bool,
        typer.Option("--result/--no-result", help="Show job result if completed"),
    ] = False,
) -> None:
    """Get details about a specific job.

    Examples:
        gobbler jobs get abc123
        gobbler jobs get abc123 --result
    """
    try:
        manager = JobManager()
        job = manager.get_job(job_id)

        if job is None:
            print_error(f"Job not found: {job_id}")
            raise typer.Exit(1)

        # Format and display job details
        detail_output = format_job_detail(job)
        print_info(detail_output)

    except typer.Exit:
        raise
    except Exception as e:
        print_error(f"Failed to get job: {e}")
        raise typer.Exit(1) from None


@app.command()
def cancel(
    job_id: Annotated[str, typer.Argument(help="Job ID to cancel")],
    force: Annotated[
        bool,
        typer.Option("--force", "-f", help="Force cancellation without confirmation"),
    ] = False,
) -> None:
    """Cancel a running job.

    Examples:
        gobbler jobs cancel abc123
        gobbler jobs cancel abc123 --force
    """
    try:
        manager = JobManager()

        # Check if job exists first
        job = manager.get_job(job_id)
        if job is None:
            print_error(f"Job not found: {job_id}")
            raise typer.Exit(1)

        # Check if job is already terminal
        if job.is_terminal:
            print_warning(f"Job {job_id} is already {job.status.value}")
            return

        # Check if worker is running for running jobs
        if job.status == JobStatus.RUNNING and not is_worker_running():
            print_warning("Worker is not running. Job may be orphaned.")

        # Confirm cancellation unless forced
        if not force:
            confirm = typer.confirm(f"Are you sure you want to cancel job {job_id}?")
            if not confirm:
                print_info("Cancellation aborted")
                return

        # Cancel the job
        success = manager.cancel_job(job_id)

        if success:
            print_success(f"Job {job_id} cancelled successfully")
        else:
            print_error(f"Failed to cancel job {job_id}")
            raise typer.Exit(1)

    except typer.Exit:
        raise
    except Exception as e:
        print_error(f"Failed to cancel job: {e}")
        raise typer.Exit(1) from None


@app.command()
def clear(
    status_filter: Annotated[
        str | None,
        typer.Option(
            "--status",
            "-s",
            help="Clear jobs with specific status (completed/failed/cancelled)",
        ),
    ] = "completed",
    older_than_days: Annotated[
        int | None,
        typer.Option(
            "--older-than-days",
            "-d",
            help="Only clear jobs older than this many days",
        ),
    ] = None,
    force: Annotated[
        bool,
        typer.Option("--force", "-f", help="Clear without confirmation"),
    ] = False,
) -> None:
    """Clear completed or failed jobs.

    Examples:
        gobbler jobs clear
        gobbler jobs clear --status failed
        gobbler jobs clear --older-than-days 7
        gobbler jobs clear --force
    """
    try:
        # Parse status filter
        status = _parse_status(status_filter)

        # Build confirmation message
        status_desc = status.value if status else "all"
        age_desc = f" older than {older_than_days} days" if older_than_days else ""
        message = f"Are you sure you want to clear {status_desc} jobs{age_desc}?"

        # Confirm clearing unless forced
        if not force:
            confirm = typer.confirm(message)
            if not confirm:
                print_info("Clear operation aborted")
                return

        # Clear jobs
        manager = JobManager()
        count = manager.clear_jobs(status=status, older_than_days=older_than_days)

        if count > 0:
            print_success(f"Cleared {count} job(s)")
        else:
            print_info("No jobs to clear")

    except typer.BadParameter:
        raise
    except Exception as e:
        print_error(f"Failed to clear jobs: {e}")
        raise typer.Exit(1) from None


@app.command()
def count() -> None:
    """Show job counts by status.

    Examples:
        gobbler jobs count
    """
    try:
        manager = JobManager()
        counts = manager.count_jobs()

        # Show worker status
        print_info(_get_worker_status_line())
        print_info("")  # Blank line

        # Display counts
        print_info("Job Counts")
        print_info("==========")
        for status in JobStatus:
            count_val = counts.get(status.value, 0)
            print_info(f"  {status.value.capitalize():12} {count_val:>5}")
        print_info(f"  {'Total':12} {counts.get('total', 0):>5}")

    except Exception as e:
        print_error(f"Failed to count jobs: {e}")
        raise typer.Exit(1) from None


# Worker subcommand group


@worker_app.command("start")
def worker_start() -> None:
    """Start the worker daemon.

    Examples:
        gobbler jobs worker start
    """
    try:
        if is_worker_running():
            pid = get_worker_pid()
            print_warning(f"Worker is already running (PID {pid})")
            return

        pid = start_worker_daemon()
        print_success(f"Worker started (PID {pid})")

    except RuntimeError as e:
        print_error(str(e))
        raise typer.Exit(1) from None
    except Exception as e:
        print_error(f"Failed to start worker: {e}")
        raise typer.Exit(1) from None


@worker_app.command("stop")
def worker_stop() -> None:
    """Stop the worker daemon.

    Examples:
        gobbler jobs worker stop
    """
    try:
        if not is_worker_running():
            print_info("Worker is not running")
            return

        stopped = stop_worker_daemon()

        if stopped:
            print_success("Worker stopped")
        else:
            print_error("Failed to stop worker")
            raise typer.Exit(1)

    except Exception as e:
        print_error(f"Failed to stop worker: {e}")
        raise typer.Exit(1) from None


@worker_app.command("status")
def worker_status() -> None:
    """Show worker daemon status.

    Examples:
        gobbler jobs worker status
    """
    if is_worker_running():
        pid = get_worker_pid()
        print_success(f"Worker is running (PID {pid})")
    else:
        print_info("Worker is not running")
