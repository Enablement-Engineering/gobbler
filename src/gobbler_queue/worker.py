"""Background worker for executing queued jobs.

This module provides the Worker class that polls for pending jobs,
executes them via subprocess, and handles progress updates and errors.
"""

import argparse
import logging
import os
import re
import shlex
import signal
import subprocess
import time
from datetime import timedelta
from typing import TYPE_CHECKING, Optional

from .models import Job

if TYPE_CHECKING:
    from .manager import JobManager

logger = logging.getLogger(__name__)

# Maximum job execution time (1 hour)
MAX_JOB_TIMEOUT = 3600
STALE_RUNNING_JOB_TIMEOUT = timedelta(seconds=MAX_JOB_TIMEOUT * 2)

# Progress line pattern: PROGRESS:<percent>:<message>
PROGRESS_PATTERN = re.compile(r"^PROGRESS:(\d+):(.*)$")


def _command_args(job: Job) -> list[str]:
    """Return structured argv for a job, falling back to the legacy command string."""
    if job.argv is not None:
        return list(job.argv)
    return shlex.split(job.command)


class Worker:
    """Background worker that processes queued jobs.

    The worker polls for pending jobs at a configurable interval,
    executes them via subprocess, and captures output including
    progress updates in the format PROGRESS:<percent>:<message>.

    Attributes:
        manager: JobManager instance for job operations.
        poll_interval: Seconds between polling for new jobs.
        running: Whether the worker loop is active.
        current_process: Currently executing subprocess, if any.
    """

    def __init__(
        self,
        manager: Optional["JobManager"] = None,
        poll_interval: float = 2.0,
    ) -> None:
        """Initialize the worker.

        Args:
            manager: JobManager instance for job operations. If None,
                a new JobManager with default database will be created.
            poll_interval: Seconds between polling for new jobs.
                Defaults to 2.0 seconds.
        """
        if manager is None:
            # Lazy import to avoid circular imports
            from .manager import JobManager

            self.manager = JobManager()
        else:
            self.manager = manager

        self.poll_interval = poll_interval
        self.running = False
        self.current_process: subprocess.Popen | None = None
        self._current_job_id: str | None = None
        self._stop_after_current = False

    def start(self) -> None:
        """Start the worker loop (blocking).

        Continuously polls for pending jobs and processes them.
        The loop runs until stop() is called or a signal is received.

        This method sets up signal handlers for graceful shutdown:
        - SIGTERM: Finish current job, then exit
        - SIGINT: Immediate stop (terminate current job)
        """
        self.running = True
        self._stop_after_current = False
        self._setup_signal_handlers()

        logger.info(
            "Worker started (PID: %d, poll_interval: %.1fs)",
            os.getpid(),
            self.poll_interval,
        )

        try:
            while self.running:
                try:
                    processed = self.run_once()
                    if not processed:
                        # No job found, wait before polling again
                        time.sleep(self.poll_interval)

                    # Check if we should stop after current job
                    if self._stop_after_current and not self.current_process:
                        logger.info("Graceful shutdown after completing current job")
                        self.running = False
                        break

                except Exception:
                    logger.exception("Error in worker loop")
                    time.sleep(self.poll_interval)
        finally:
            logger.info("Worker stopped")

    def stop(self) -> None:
        """Signal the worker to stop gracefully.

        The worker will finish processing the current job (if any)
        before exiting the loop.
        """
        logger.info("Stop requested, will finish current job")
        self._stop_after_current = True

        # If no job is running, stop immediately
        if not self.current_process:
            self.running = False

    def run_once(self) -> bool:
        """Process one pending job.

        Claims the next pending job, executes it, and updates status.
        This method is useful for testing individual job execution.

        Returns:
            True if a job was processed, False if no pending jobs.
        """
        # Get and claim a pending job
        job = self._claim_next_job()
        if job is None:
            return False

        logger.info("Processing job %s (type: %s)", job.id, job.job_type.value)
        self._current_job_id = job.id

        try:
            self._execute_job(job)
        except Exception:
            logger.exception("Failed to execute job %s", job.id)
            self._fail_job(job.id, "Job execution failed")
        finally:
            self._current_job_id = None
            self.current_process = None

        return True

    def _claim_next_job(self) -> Job | None:
        """Claim the next pending job for processing.

        Atomically sets the job status to 'running' and records
        the worker PID.

        Returns:
            The claimed Job, or None if no pending jobs.
        """
        recovered = self.manager.recover_stale_running_jobs(stale_after=STALE_RUNNING_JOB_TIMEOUT)
        if recovered:
            logger.warning("Requeued %d stale running job(s)", recovered)

        # Get pending jobs (oldest first)
        pending_jobs = self.manager.get_pending_jobs(limit=1)
        if not pending_jobs:
            return None

        job = pending_jobs[0]

        # Claim the job by setting it to running with our PID
        if self.manager.start_job(job.id, os.getpid()):
            # Refresh job state after update
            return self.manager.get_job(job.id)

        # Another worker may have claimed it
        return None

    def _execute_job(self, job: Job) -> None:
        """Execute a job's command via subprocess.

        Spawns the job's argv, captures stdout/stderr, parses
        progress updates, and updates job status on completion.

        Args:
            job: The Job to execute.
        """
        stdout_lines: list[str] = []
        stderr_lines: list[str] = []

        try:
            cmd_args = _command_args(job)

            # Start the subprocess
            self.current_process = subprocess.Popen(  # nosec B603
                cmd_args,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1,  # Line buffered
            )

            start_time = time.time()

            # Read stdout line by line for progress updates
            while True:
                # Check for timeout
                elapsed = time.time() - start_time
                if elapsed > MAX_JOB_TIMEOUT:
                    logger.warning(
                        "Job %s timed out after %d seconds",
                        job.id,
                        MAX_JOB_TIMEOUT,
                    )
                    self.current_process.kill()
                    self.current_process.wait()
                    self._fail_job(
                        job.id,
                        f"Job timed out after {MAX_JOB_TIMEOUT} seconds",
                    )
                    return

                # Check if process has ended
                if self.current_process.poll() is not None:
                    break

                # Read available output (non-blocking would be better but complex)
                if self.current_process.stdout:
                    line = self.current_process.stdout.readline()
                    if line:
                        line = line.rstrip("\n")
                        self._process_output_line(job.id, line, stdout_lines)

            # Read any remaining stdout
            if self.current_process.stdout:
                for remaining_line in self.current_process.stdout:
                    stripped_line = remaining_line.rstrip("\n")
                    self._process_output_line(job.id, stripped_line, stdout_lines)

            # Read all stderr
            if self.current_process.stderr:
                stderr_lines = [line.rstrip("\n") for line in self.current_process.stderr]

            # Check return code
            return_code = self.current_process.returncode
            if return_code == 0:
                result = {
                    "stdout": "\n".join(stdout_lines),
                    "stderr": "\n".join(stderr_lines) if stderr_lines else None,
                    "return_code": return_code,
                }
                self._complete_job(job.id, result)
            else:
                error_msg = "\n".join(stderr_lines) if stderr_lines else f"Exit code: {return_code}"
                self._fail_job(job.id, error_msg)

        except Exception:
            logger.exception("Error executing job %s", job.id)
            self._fail_job(job.id, "Error during job execution")

    def _process_output_line(
        self,
        job_id: str,
        line: str,
        stdout_lines: list[str],
    ) -> None:
        """Process a line of stdout, checking for progress updates.

        Lines matching PROGRESS:<percent>:<message> are parsed and
        used to update job progress. Other lines are appended to stdout.

        Args:
            job_id: The job ID for progress updates.
            line: The output line to process.
            stdout_lines: List to append non-progress lines to.
        """
        match = PROGRESS_PATTERN.match(line)
        if match:
            try:
                percent = int(match.group(1))
                message = match.group(2)
                self.manager.update_progress(job_id, percent, message)
                logger.debug("Job %s progress: %d%% - %s", job_id, percent, message)
            except (ValueError, TypeError) as e:
                logger.warning("Failed to parse progress line '%s': %s", line, e)
                stdout_lines.append(line)
        else:
            stdout_lines.append(line)

    def _complete_job(self, job_id: str, result: dict) -> None:
        """Mark a job as completed with result.

        Args:
            job_id: The job ID to complete.
            result: Result data dictionary.
        """
        if self.manager.complete_job(job_id, result):
            logger.info("Job %s completed successfully", job_id)
        else:
            logger.info("Job %s completion skipped because status changed", job_id)

    def _fail_job(self, job_id: str, error: str) -> None:
        """Mark a job as failed with error message.

        Args:
            job_id: The job ID to fail.
            error: Error message describing the failure.
        """
        if self.manager.fail_job(job_id, error):
            logger.error("Job %s failed: %s", job_id, error)
        else:
            logger.info("Job %s failure skipped because status changed", job_id)

    def _setup_signal_handlers(self) -> None:
        """Set up signal handlers for graceful shutdown."""
        signal.signal(signal.SIGTERM, self._handle_sigterm)
        signal.signal(signal.SIGINT, self._handle_sigint)

    def _handle_sigterm(self, signum: int, frame) -> None:  # noqa: ARG002
        """Handle SIGTERM - finish current job, then exit.

        Args:
            signum: Signal number (unused).
            frame: Current stack frame (unused).
        """
        logger.info("Received SIGTERM, finishing current job before exit")
        self._stop_after_current = True

        # If no job is running, stop immediately
        if not self.current_process:
            self.running = False

    def _handle_sigint(self, signum: int, frame) -> None:  # noqa: ARG002
        """Handle SIGINT (Ctrl+C) - immediate stop.

        Terminates any running subprocess and exits immediately.

        Args:
            signum: Signal number (unused).
            frame: Current stack frame (unused).
        """
        logger.info("Received SIGINT, stopping immediately")
        self.running = False

        # Terminate current process if running
        if self.current_process and self.current_process.poll() is None:
            logger.warning("Terminating current job process")
            self.current_process.terminate()
            try:
                self.current_process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.current_process.kill()

            # Mark the current job as failed
            if self._current_job_id:
                self._fail_job(self._current_job_id, "Job terminated by SIGINT")


def main() -> None:
    """Entry point for running the worker from command line.

    Usage:
        python -m gobbler_queue.worker [--poll-interval SECONDS]
    """
    parser = argparse.ArgumentParser(
        description="Gobbler background job worker",
    )
    parser.add_argument(
        "--poll-interval",
        type=float,
        default=2.0,
        help="Seconds between polling for new jobs (default: 2.0)",
    )
    parser.add_argument(
        "--log-level",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        default="INFO",
        help="Logging level (default: INFO)",
    )

    args = parser.parse_args()

    # Configure logging
    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # Reduce noise from other loggers
    logging.getLogger("urllib3").setLevel(logging.WARNING)

    logger.info("Starting Gobbler worker with poll interval %.1fs", args.poll_interval)

    worker = Worker(poll_interval=args.poll_interval)
    worker.start()


if __name__ == "__main__":
    main()
