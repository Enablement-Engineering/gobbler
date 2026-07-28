"""Progress bar utilities using rich."""

from __future__ import annotations

from types import TracebackType
from typing import Any

from rich.progress import (
    BarColumn,
    Progress,
    SpinnerColumn,
    TaskID,
    TextColumn,
    TimeElapsedColumn,
    TimeRemainingColumn,
)


def create_progress() -> Progress:
    """Create a progress bar with default columns.

    Returns:
        A configured Progress instance
    """
    return Progress(
        SpinnerColumn(),
        TextColumn("[bold blue]{task.description}"),
        BarColumn(bar_width=40),
        TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
        TimeElapsedColumn(),
        TimeRemainingColumn(),
        expand=False,
    )


def create_spinner() -> Progress:
    """Create a simple spinner for indeterminate progress.

    Returns:
        A configured Progress instance with just a spinner
    """
    return Progress(
        SpinnerColumn(),
        TextColumn("[bold blue]{task.description}"),
        TimeElapsedColumn(),
        expand=False,
    )


class ProgressTracker:
    """Context manager for tracking progress of operations."""

    def __init__(self, description: str, total: int | None = None):
        """Initialize progress tracker.

        Args:
            description: Description of the task
            total: Total number of steps (None for indeterminate)
        """
        self.description = description
        self.total = total
        self.progress: Progress | None = None
        self.task_id: TaskID | None = None

    def __enter__(self) -> ProgressTracker:
        """Start progress tracking."""
        if self.total is None:
            self.progress = create_spinner()
        else:
            self.progress = create_progress()

        self.progress.__enter__()
        self.task_id = self.progress.add_task(self.description, total=self.total)
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        """Stop progress tracking."""
        if self.progress:
            self.progress.__exit__(exc_type, exc_val, exc_tb)

    def update(self, advance: int = 1, description: str | None = None) -> None:
        """Update progress.

        Args:
            advance: Number of steps to advance
            description: Optional new description
        """
        if self.progress and self.task_id is not None:
            kwargs: dict[str, Any] = {"advance": advance}
            if description:
                kwargs["description"] = description
            self.progress.update(self.task_id, **kwargs)

    def set_total(self, total: int) -> None:
        """Set the total number of steps.

        Args:
            total: Total number of steps
        """
        if self.progress and self.task_id is not None:
            self.progress.update(self.task_id, total=total)
